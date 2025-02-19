import os
import shutil
import torch
import socket
from PIL import Image
from transformers import MllamaForConditionalGeneration, AutoProcessor
import logging

# Setup logging
logger = logging.getLogger(__name__)

logger.info(f"Loading the classify_screenshots")

# -----------------------
# Model and Processor Setup
# -----------------------
model_id = "meta-llama/Llama-3.2-11B-Vision-Instruct"

# Explicitly set the device to GPU 1
device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")

model = MllamaForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.float16,  # Use float16 for efficiency
    device_map=None,           # Disable automatic device mapping
)
model.to(device)  # Move model to GPU 1
model.tie_weights()

processor = AutoProcessor.from_pretrained(model_id)

logger.info(f"Successfully loaded model classify_screenshots")

# -----------------------
# Utility Functions
# -----------------------
import re

def extract_final_answer(response):
    """
    Extracts the final 'YES' or 'NO' from the assistant's response,
    ensuring it does not pick up occurrences in the user's input.
    """
    # Split response into sections based on roles (User and Assistant)
    sections = response.split("assistant")  # Splitting at the assistant's response section

    if len(sections) < 2:
        return None  # No assistant response found

    assistant_response = sections[-1]  # Take the last assistant's response

    # Search for the last standalone YES or NO in the assistant's response only
    matches = re.findall(r'\b(YES|NO)\b', assistant_response.strip(), re.IGNORECASE)

    if matches:
        return matches[-1].upper()  # Return the last match in uppercase
    return None  # Return None if no valid answer is found


def construct_prompt():
    """Generate the instruction prompt for the model."""
    return """
Analyze the provided image and determine if it contains input fields associated with the login flow of a web page. Specifically, look for:

Username or email input fields (e.g., forms with user ID, unique user ID, email address, or similar fields).
Password input fields (fields intended for password entry).
Follow this structured approach:

Identify all input fields in the image.
Filter out irrelevant input fields, such as those related to search, comments, or non-login-related data collection.
Determine if at least one relevant login-related input field is present and visible on the page.
Explain your reasoning step by step (Chain of Thought) to justify your decision.
Strictly output either "YES" or "NO" at the end, based on whether a login form containing at least one relevant input field is detected.
Output Format (Important):
After explaining your reasoning, respond strictly with either:

"YES" (if a relevant login input field is present and visible).
"NO" (if no relevant login input field is found).
"""

def analyze_image(image_path):
    """Run the LLaMA model on the image and return the response."""
    # Open the image
    image = Image.open(image_path).convert("RGB")
    
    # Prepare the messages
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": construct_prompt()},
            ],
        }
    ]
    
    # Process input for the model
    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(
        image,
        input_text,
        add_special_tokens=False,
        return_tensors="pt",
    ).to(device)  # Send inputs to GPU 1
    
    # Generate output
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=512)
    response = processor.decode(output[0], skip_special_tokens=True).strip()
    
    return response

def process_images(input_dir, output_dir):
    """Process all images in a directory structure and save only those with login elements."""
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    # Traverse the input directory
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".png"):
                image_path = os.path.join(root, file)
                print(f"Processing: {image_path}")
                
                # Run inference
                response = analyze_image(image_path)
                print(f"Model Response: {response}")
                
                # Check if the response is 'Yes'
                if extract_final_answer(response) == 'YES':
                    # Create corresponding directory in output
                    relative_path = os.path.relpath(root, input_dir)
                    target_dir = os.path.join(output_dir, relative_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Copy the image to the target directory
                    shutil.copy(image_path, os.path.join(target_dir, file))
                    print(f"Saved: {os.path.join(target_dir, file)}")

def sanitize_url(url):
    """Convert a URL like bradbank.com or www.bradbank.com to bradbank_com or www_bradbank_com."""
    return url.replace(".", "_")

# -----------------------
# Socket Server Setup
# -----------------------
HOST = "0.0.0.0"  # Listen on all available interfaces
PORT = 5050        # Define a port for communication

def start_socket_server():
    """Start a socket server to accept URLs and process corresponding images."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"Socket server listening on {HOST}:{PORT}...")

        while True:
            conn, addr = server_socket.accept()
            with conn:
                print(f"Connected by {addr}")

                # Receive URL from client
                data = conn.recv(1024)
                if not data:
                    continue

                # Decode and sanitize URL
                url = data.decode("utf-8").strip()
                sanitized_url = sanitize_url(url)

                logger.info(f"Received URL: {url} -> Sanitized: {sanitized_url}")

                # Define dynamic input and output directories
                input_directory = f"/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/{sanitized_url}"
                output_directory = f"/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/output_images/{sanitized_url}"

                # Ensure directories exist
                if not os.path.exists(input_directory):
                    print(f"Input directory does not exist: {input_directory}")
                    conn.sendall(f"Error: Input directory does not exist: {input_directory}".encode("utf-8"))
                    continue

                logger.info(f"Processing images in {input_directory}, saving results to {output_directory}...")
                process_images(input_directory, output_directory)

                # Notify client that processing is complete
                conn.sendall(f"Processing completed for {sanitized_url}".encode("utf-8"))

# -----------------------
# Main Execution
# -----------------------
if __name__ == "__main__":
    print("Starting socket server for image classification...")
    start_socket_server()
