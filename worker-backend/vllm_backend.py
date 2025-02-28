import socket
import json
import re
import time
import logging
from PIL import Image
import torch
import requests

# Import OpenAI client for vLLM Serve style connection.
from openai import OpenAI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("Loading the crawler_backend")

device = torch.device("cuda:0")  # Using GPU 0 here

# Load the processor for prompt formatting (used later to format the chat template if needed)
from transformers import AutoProcessor, pipeline, AutoModelForSeq2SeqLM
processor = AutoProcessor.from_pretrained("OS-Copilot/OS-Atlas-Base-7B")
logger.info("Successfully loaded model crawler_backend")

# Load summarization model and tokenizer
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=0)  # Use GPU
attention_model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn").to(device)

# ---- vLLM Serve / OpenAI Setup ----
# We assume that vLLM Serve is running on a non-default port (8002 in this case)
# and that we want to connect using the OpenAI client interface.
API_KEY = "token-abc123"
client = OpenAI(
    api_key=API_KEY,
    base_url="http://127.0.0.1:8002/v1",
)

# Socket server setup
HOST = '0.0.0.0'
PORT = 5000

# Dictionaries to maintain conversation history and task states per client
conversation_histories = {}
task_states = {}  # Tracks the current task state for each client
last_image = {}   # Tracks the latest image for each client

def convert_path_to_url(path: str) -> str:
    """
    Given a file system path, find the "screenshot_flows" marker and
    convert the remainder into an HTTP URL (using localhost on port 8001).
    Example:
      /tmp/Workspace/.../screenshot_flows/www_example_com/flow_1/page.png
    becomes:
      http://localhost:8001/www_example_com/flow_1/page.png
    """
    marker = "screenshot_flows"
    idx = path.find(marker)
    if idx == -1:
        logger.error("Marker 'screenshot_flows' not found in the path.")
        return None
    relative_part = path[idx + len(marker) + 1:]  # +1 to skip the '/'
    url = f"http://localhost:8001/{relative_part}"
    return url

def summarize_conversation(history, max_length=100):
    conversation_text = " ".join([msg['content'] for msg in history])
    summary = summarizer(conversation_text, max_length=max_length, min_length=30, do_sample=False)
    return summary[0]['summary_text']

def get_sliding_window_segments(history, window_size=5, overlap=2):
    segments = []
    for i in range(0, len(history), window_size - overlap):
        segment = history[i:i + window_size]
        segments.append(segment)
    return segments

# Start the socket server
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}...")

    while True:
        conn, addr = server_socket.accept()
        with conn:
            print(f"Connected by {addr}")

            # Initialize conversation history and task state for the new client
            if addr not in conversation_histories:
                conversation_histories[addr] = []
                task_states[addr] = "check_popups"  # Start with checking for popups or cookie banners
                last_image[addr] = None

            while True:
                # Receive the image path from the client
                data = conn.recv(1024)
                if not data:
                    break
                img_path = data.decode('utf-8').strip()
                print(f"Received image path: {img_path}")

                # Convert the path to a local file path if needed.
                # (This step may be adjusted based on your directory structure.)
                fixed_path = '../worker/' + '/'.join(img_path.split('/')[2:])
                print(f'Fixed path: {fixed_path}')
                img_path = fixed_path

                # Open the image to check its dimensions.
                try:
                    img = Image.open(img_path)
                except Exception as e:
                    conn.sendall(f"Error: Could not open image. {str(e)}".encode('utf-8'))
                    continue

                width, height = img.size
                print("The dimensions of the image are:", width, "x", height)

                # Update the last image for this client (for reference, if needed)
                last_image[addr] = img

                # Prepare the prompt based on the current task state.
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
                    task_states[addr] = "find_login"  # Move to the next task state after checking for popups.
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

                # Add the user's prompt to conversation history.
                user_message = {
                    "role": "user",
                    "content": prompt_text,
                }
                conversation_histories[addr].append(user_message)

                # Summarize conversation if too long.
                if len(conversation_histories[addr]) > 5:
                    summary = summarize_conversation(conversation_histories[addr])
                    conversation_histories[addr] = [{"role": "system", "content": summary}]

                # Optionally, include conversation history in the new prompt if needed.
                # Here, we simply use the latest instruction.
                # Prepare the image URL using our helper function.
                image_url = convert_path_to_url(img_path)
                if image_url is None:
                    conn.sendall("Error: Could not convert image path to URL.".encode('utf-8'))
                    continue

                # Build the messages payload using the OpenAI client format.
                messages = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt_text}
                    ]}
                ]

                # ---------------------------
                # <<--- vLLM Serve Inference Step using OpenAI client --->>
                start_time = time.time()
                try:
                    chat_response = client.chat.completions.create(
                        model="OS-Copilot/OS-Atlas-Base-7B",
                        messages=messages,
                        max_tokens=512,
                        temperature=0.01,
                        top_p=0.001,
                    )
                    # Use attribute access to get the text from the response.
                    output_text = chat_response.choices[0].message.content.strip()
                except Exception as e:
                    logger.error(f"Inference error: {e}")
                    conn.sendall(f"Inference error: {e}".encode('utf-8'))
                    continue
                end_time = time.time()
                print("Model Output:", output_text)
                print(f'Time elapsed: {end_time - start_time}')

                # Append the model's response to conversation history.
                model_response = {
                    "role": "assistant",
                    "content": output_text,
                }
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

                # Convert matches to a list of tuples with integer values.
                bounding_boxes = [
                    ((int(x1), int(y1)), (int(x2), int(y2))) for x1, y1, x2, y2 in matches
                ]
                print("Original bounding boxes:", bounding_boxes)

                # Scale coordinates based on image dimensions.
                scale_factor = 1000  # Adjust based on the model's coordinate system.
                scaled_bounding_boxes = [
                    (
                        (int((x1 / scale_factor) * width), int((y1 / scale_factor) * height)),
                        (int((x2 / scale_factor) * width), int((y2 / scale_factor) * height))
                    )
                    for (x1, y1), (x2, y2) in bounding_boxes
                ]
                print("Scaled bounding boxes:", scaled_bounding_boxes)

                # Assume there's one element to click on.
                if scaled_bounding_boxes:
                    (x1, y1), (x2, y2) = scaled_bounding_boxes[0]
                    click_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                    response_msg = f"Click Point: {click_point[0]}, {click_point[1]}"
                    conn.sendall(response_msg.encode('utf-8'))
                    print(f"Sent response: {response_msg}")
                else:
                    conn.sendall("Error: No bounding box could be determined.".encode('utf-8'))
