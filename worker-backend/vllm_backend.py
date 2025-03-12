import socket
import json
import re
import time
import logging
from PIL import Image
import torch
import threading

# Import OpenAI client for vLLM Serve style connection.
from openai import OpenAI

# Transformers for prompt processing and summarization
from transformers import AutoProcessor, pipeline, AutoModelForSeq2SeqLM

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

logger.info("Loading the crawler_backend")

# Use GPU 0
device = torch.device("cuda:0")

# Load the processor (for prompt formatting, etc.)
processor = AutoProcessor.from_pretrained("OS-Copilot/OS-Atlas-Base-7B")
logger.info("Successfully loaded model crawler_backend")

# Load summarization pipeline (runs on GPU)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=0)
attention_model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn").to(device)

# ---- vLLM Serve / OpenAI Setup ----
API_KEY = "token-abc123"
client = OpenAI(
    api_key=API_KEY,
    base_url="http://127.0.0.1:8002/v1",
)

# Socket server configuration
HOST = '0.0.0.0'
PORT = 5000

# Dictionaries to maintain conversation history and task states per client
conversation_histories = {}
task_states = {}  # Tracks the current task state for each client
last_image = {}   # Tracks the latest image for each client

def convert_path_to_url(path: str) -> str:
    """
    Convert a file system path to an HTTP URL.
    Looks for the 'screenshot_flows' marker in the path and then constructs
    a URL using localhost on port 8001.
    """
    marker = "screenshot_flows"
    idx = path.find(marker)
    if idx == -1:
        logger.error("Marker 'screenshot_flows' not found in the path.")
        return None
    relative_part = path[idx + len(marker) + 1:]  # Skip the marker and '/'
    url = f"http://localhost:8001/{relative_part}"
    return url

def summarize_conversation(history, max_length=100):
    conversation_text = " ".join([msg['content'] for msg in history])
    summary = summarizer(conversation_text, max_length=max_length, min_length=30, do_sample=False)
    return summary[0]['summary_text']

def handle_client(conn, addr):
    """
    Handle the socket connection with a client.
    This function runs in a separate thread per client.
    """
    with conn:
        logger.info(f"Connected by {addr}")

        # Initialize conversation history and state if not already set.
        if addr not in conversation_histories:
            conversation_histories[addr] = []
            task_states[addr] = "check_popups"  # Starting state.
            last_image[addr] = None

        while True:
            try:
                data = conn.recv(1024)
            except Exception as e:
                logger.error(f"Error receiving data from {addr}: {e}")
                break

            if not data:
                break

            # Get the image path sent from the client.
            img_path = data.decode('utf-8').strip()
            logger.info(f"Received image path from {addr}: {img_path}")

            # Fix the file path if needed.
            fixed_path = '../worker/' + '/'.join(img_path.split('/')[2:])
            logger.info(f"Fixed path for {addr}: {fixed_path}")
            img_path = fixed_path

            # Open the image to verify and get its dimensions.
            try:
                img = Image.open(img_path)
            except Exception as e:
                error_msg = f"Error: Could not open image. {str(e)}"
                logger.error(error_msg)
                conn.sendall(error_msg.encode('utf-8'))
                continue

            width, height = img.size
            logger.info(f"Image dimensions from {addr}: {width} x {height}")

            # Save the last image for this client.
            last_image[addr] = img

            # Determine the prompt text based on task state.
            if task_states[addr] == "check_popups":
                prompt_text = (
                    """
Analyze the provided image and determine if there are any visible popups or cookie banners.
If a popup is detected, where do I click to close it. Give me the coordinates of a cross icon in order to close it. If this does not exist give me the coordinates of the button inside the popup that exists
If a cookie banner is detected return the position of the large Accept button inside a colored shape, for example oval or square.
If no popup or cookie banner exists Output: "No popups found".
Output Format:

Element Type: [Popup/Cookie Banner]
Description: [Brief description]
Bounding Box Coordinates: (x1, y1, x2, y2)
Guidelines:
- Only focus on popups or cookie banners.
- Provide precise bounding box coordinates.
"""
                )
                # Move to the next state.
                task_states[addr] = "find_login"
            elif task_states[addr] == "find_login":
                prompt_text = (
                    """
Analyze the provided image and identify where do I click to access the login page. 
This may be an element labeled abstractly like Online Banking, My Account, Login or a person icon or even a form submit button associated with login credentials etc.
Output Format:

Element Type: Login Button
Description: [Brief description]
Bounding Box Coordinates: (x1, y1, x2, y2)
Guidelines:
- Only focus on the element that takes me to the login page.
- Provide precise bounding box coordinates.
"""
                )

            # Add user's prompt to conversation history.
            user_message = {"role": "user", "content": prompt_text}
            conversation_histories[addr].append(user_message)

            # Optionally summarize conversation if history gets too long.
            if len(conversation_histories[addr]) > 5:
                summary = summarize_conversation(conversation_histories[addr])
                conversation_histories[addr] = [{"role": "system", "content": summary}]

            # Convert image path to a URL.
            image_url = convert_path_to_url(img_path)
            if image_url is None:
                error_msg = "Error: Could not convert image path to URL."
                conn.sendall(error_msg.encode('utf-8'))
                continue

            # Build messages payload in the expected format.
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt_text}
                ]}
            ]

            # Call the model via vLLM Serve.
            start_time = time.time()
            try:
                chat_response = client.chat.completions.create(
                    model="OS-Copilot/OS-Atlas-Base-7B",
                    messages=messages,
                    max_tokens=512,
                    temperature=0.01,
                    top_p=0.001,
                )
                output_text = chat_response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Inference error for {addr}: {e}")
                conn.sendall(f"Inference error: {e}".encode('utf-8'))
                continue
            end_time = time.time()
            logger.info(f"Model Output for {addr}: {output_text}")
            logger.info(f"Time elapsed: {end_time - start_time}")

            # Append the model's response to conversation history.
            model_response = {"role": "assistant", "content": output_text}
            conversation_histories[addr].append(model_response)

            # Extract bounding box coordinates using regex.
            pattern = r'Bounding Box Coordinates:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
            matches = re.findall(pattern, output_text)
            if not matches:
                if 'No popups found' in output_text:
                    conn.sendall("No popups found".encode('utf-8'))
                else:
                    conn.sendall("Error: No relevant element detected.".encode('utf-8'))
                continue

            # Convert regex matches into a list of bounding box tuples.
            bounding_boxes = [
                ((int(x1), int(y1)), (int(x2), int(y2))) for x1, y1, x2, y2 in matches
            ]
            logger.info(f"Original bounding boxes for {addr}: {bounding_boxes}")

            # Scale coordinates based on image dimensions.
            scale_factor = 1000  # Adjust this as necessary.
            scaled_bounding_boxes = [
                (
                    (int((x1 / scale_factor) * width), int((y1 / scale_factor) * height)),
                    (int((x2 / scale_factor) * width), int((y2 / scale_factor) * height))
                )
                for (x1, y1), (x2, y2) in bounding_boxes
            ]
            logger.info(f"Scaled bounding boxes for {addr}: {scaled_bounding_boxes}")

            # Determine the click point (using the first bounding box found).
            if scaled_bounding_boxes:
                (x1, y1), (x2, y2) = scaled_bounding_boxes[0]
                click_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                response_msg = f"Click Point: {click_point[0]}, {click_point[1]}"
                conn.sendall(response_msg.encode('utf-8'))
                logger.info(f"Sent response to {addr}: {response_msg}")
            else:
                conn.sendall("Error: No bounding box could be determined.".encode('utf-8'))

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        logger.info(f"Server listening on {HOST}:{PORT}...")

        while True:
            try:
                conn, addr = server_socket.accept()
                # Create and start a new thread for each incoming client.
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")

if __name__ == "__main__":
    main()
