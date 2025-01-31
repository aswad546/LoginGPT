import socket
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, pipeline, AutoModelForSeq2SeqLM
from qwen_vl_utils import process_vision_info
from PIL import Image
import re
import torch
import time
import logging

logger = logging.getLogger(__name__)

logger.info(f"Loading the crawler_backend")

device = torch.device("cuda:0")  # Set to GPU 1 (indexed as cuda:0)
# Load the main model and processor
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "OS-Copilot/OS-Atlas-Base-7B", torch_dtype="auto", device_map={"": "cuda:0"}, cache_dir='/tmp/'
)
processor = AutoProcessor.from_pretrained("OS-Copilot/OS-Atlas-Base-7B")

logger.info(f"Successfully loaded model crawler_backend")

# Load summarization model and tokenizer
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=0)  # Use GPU
attention_model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn").to(device)

# Socket server setup
HOST = '0.0.0.0'
PORT = 5000

# Dictionary to maintain conversation history for each client
conversation_histories = {}
task_states = {}  # Tracks the current task state for each client
last_image = {}    # Tracks the latest image for each client

# Define utility functions
def summarize_conversation(history, max_length=100):
    """Summarizes the conversation history to reduce length."""
    conversation_text = " ".join([msg['content'] for msg in history])
    summary = summarizer(conversation_text, max_length=max_length, min_length=30, do_sample=False)
    return summary[0]['summary_text']

def get_sliding_window_segments(history, window_size=5, overlap=2):
    """Generates sliding window segments of conversation history."""
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
                task_states[addr] = "check_popups"  # Start by checking for popups or cookie banners
                last_image[addr] = None

            while True:
                # Receive the image path from the client
                data = conn.recv(1024)
                if not data:
                    break
                img_path = data.decode('utf-8').strip()
                print(f"Received image path: {img_path}")

                fixed_path = '../worker/' + '/'.join(img_path.split('/')[2:])

                print(f'Fixed path {fixed_path}')

                img_path = fixed_path

                # Open the image
                try:
                    img = Image.open(img_path)
                except Exception as e:
                    conn.sendall(f"Error: Could not open image. {str(e)}".encode('utf-8'))
                    continue

                width, height = img.size
                print("The dimensions of the image are:", width, "x", height)

                # Update the last image for this client
                last_image[addr] = img_path

                # Prepare the prompt based on the task state
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
                    task_states[addr] = "find_login"  # Move to the next task state after checking for popups
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
#                     task_states[addr] = "navigate_to_login"  # Move to the next task state
#                 else:
#                     prompt_text = (
#                         """
# After the previous click I get to the following page. Given the provided image of this page, where do I click now to get to the login page.
# Output Format:
# Element Type: Login Button
# Description: [Brief description]
# Bounding Box Coordinates: (x1, y1, x2, y2)
# Guidelines:
# - Only focus on the element necessary to proceed to the login page.
# - Provide precise bounding box coordinates.
# """
#                     )

                # Add the user's prompt to conversation history
                user_message = {
                    "role": "user",
                    "content": prompt_text,
                }
                conversation_histories[addr].append(user_message)

                # Summarize the conversation history if too long (>5)
                if len(conversation_histories[addr]) > 5:
                    summary = summarize_conversation(conversation_histories[addr])
                    conversation_histories[addr] = [{"role": "system", "content": summary}]

                # Prepare prompt with sliding window
                segments = get_sliding_window_segments(conversation_histories[addr])
                prompt = ""
                for segment in segments:
                    for message in segment:
                        prompt += f"{message['role']}: {message['content']}\n"

                # Prepare the input for the model using the entire historical context `prompt` 
                # plus the latest image and `prompt_text`.
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": last_image[addr]},  # latest image
                            {"type": "text", "text": prompt_text},  # latest instructions
                        ],
                    }
                ]
                text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(
                    text=[text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(device if torch.cuda.is_available() else "cpu")
                start = time.time()
                # Inference: Generation of the output
                generated_ids = model.generate(**inputs, max_new_tokens=512)
                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                output_text = processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=False, clean_up_tokenization_spaces=False
                )[0]
                print("Model Output:", output_text)
                end = time.time()
                print(f'Time elapsed: {end-start}')
                # Append the model's response to the conversation history
                model_response = {
                    "role": "assistant",
                    "content": output_text,
                }
                conversation_histories[addr].append(model_response)


                # Extract bounding box coordinates using regex
                pattern = r'Bounding Box Coordinates:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
                matches = re.findall(pattern, output_text)
                if not matches:
                    if 'No popups found' in output_text:
                        conn.sendall("No popups found".encode('utf-8'))
                    else:
                        conn.sendall("Error: No relevant element detected.".encode('utf-8'))
                    continue

                # Convert matches to a list of tuples with integer values
                bounding_boxes = [
                    ((int(x1), int(y1)), (int(x2), int(y2))) for x1, y1, x2, y2 in matches
                ]
                print("Original bounding boxes:", bounding_boxes)

                # Scale coordinates based on image dimensions
                scale_factor = 1000  # Adjust based on the model's coordinate system
                scaled_bounding_boxes = [
                    (
                        (int((x1 / scale_factor) * width), int((y1 / scale_factor) * height)),
                        (int((x2 / scale_factor) * width), int((y2 / scale_factor) * height))
                    )
                    for (x1, y1), (x2, y2) in bounding_boxes
                ]
                print("Scaled bounding boxes:", scaled_bounding_boxes)

                # Assume there's one element to click on
                if scaled_bounding_boxes:
                    (x1, y1), (x2, y2) = scaled_bounding_boxes[0]
                    click_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                    response = f"Click Point: {click_point[0]}, {click_point[1]}"
                    conn.sendall(response.encode('utf-8'))
                    print(f"Sent response: {response}")
                else:
                    conn.sendall("Error: No bounding box could be determined.".encode('utf-8'))
