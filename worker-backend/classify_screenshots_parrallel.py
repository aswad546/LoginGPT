import os
import shutil
import socket
import logging
import re
from openai import OpenAI  # Import the new OpenAI client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure OpenAI client to use your vLLM Serve instance.
client = OpenAI(
    api_key="token-abc123",
    base_url="http://localhost:8000/v1",
)

# The prompt text to send to the model.
PROMPT_TEXT = """
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

def convert_input_to_output_path(input_path: str, change_path: bool) -> str:
    """
    Convert the Docker internal path to the desired output image path.
    
    For example, if the input is:
      /app/modules/loginpagedetection/screenshot_flows/www_hancockwhitney_com/flow_0/page_1.png
    then this function will return:
      /tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/output_images/www_hancockwhitney_com/flow_0/page_1.png
    """
    # If the input path starts with "/app/", remove that prefix.
    if input_path.startswith("/app/"):
        relative_path = input_path[len("/app/"):]
    else:
        relative_path = input_path

    # Replace "screenshot_flows" with "output_images"
    if change_path:
        relative_path = relative_path.replace("screenshot_flows", "output_images")

    # Prepend the base directory for output images.
    output_path = f"/tmp/Workspace/SSO-Monitor-mine/worker/{relative_path}"
    return output_path


def sanitize_input_path(input_path: str) -> str:
    """Clean up the input path string."""
    return input_path.strip()

def convert_path_to_url(input_path: str) -> str:
    """
    Replace everything up to and including "screenshot_flows" with "http://localhost:8001".
    For example, given:
      /tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_hancockwhitney_com/flow_1/page_1.png
    it returns:
      http://localhost:8001/www_hancockwhitney_com/flow_1/page_1.png
    """
    marker = "screenshot_flows"
    idx = input_path.find(marker)
    if idx == -1:
        logger.error("Marker 'screenshot_flows' not found in the path.")
        return None
    # Calculate the position after the marker
    relative_part = input_path[idx + len(marker) + 1:]  # +1 to remove the trailing '/'
    url = f"http://localhost:8001/{relative_part}"
    return url

def clear_directory(directory: str):
    """Clears out all contents of the given directory, but does not remove the directory itself."""
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")


def classify_image(image_url: str) -> (str, str):
    """
    Send a chat completion request to vLLM Serve using the image URL.
    Returns a tuple (final_answer, full_response).
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": PROMPT_TEXT},
            ]
        }
    ]
    try:
        chat_response = client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-7B-Instruct",
            messages=messages,
            max_tokens=512,
        )
        logger.info(f"Model response: {chat_response}")
        print(f"Model response: {chat_response}")
        output_text = chat_response.choices[0].message.content.strip()
        # Extract final answer ("YES" or "NO")
        matches = re.findall(r'\b(YES|NO)\b', output_text, re.IGNORECASE)
        final_answer = matches[-1].upper() if matches else None
        return final_answer, output_text
    except Exception as e:
        logger.error(f"Error during classification: {e}")
        return None, None

def process_image(input_path: str) -> (str, str):
    """
    Given a local input path, convert it to a URL for classification, send the request,
    and return the final answer and full response.
    """
    image_url = convert_path_to_url(input_path)
    if image_url is None:
        return None, None
    logger.info(f"Using image URL: {image_url}")
    return classify_image(image_url)

def start_socket_server():
    HOST = "0.0.0.0"
    PORT = 5060
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        logger.info(f"Socket server listening on {HOST}:{PORT}...")
        while True:
            conn, addr = server_socket.accept()
            with conn:
                logger.info(f"Connected by {addr}")
                data = conn.recv(1024)
                if not data:
                    continue
                input_path = data.decode("utf-8").strip()
                logger.info(f"Received image path: {input_path}")
                input_path = sanitize_input_path(input_path) 
                final_answer, full_response = process_image(input_path)
                if final_answer is None:
                    conn.sendall("Error: Classification failed".encode("utf-8"))
                else:
                    # If classification is YES, save the image to the output path.
                    if final_answer == "YES":
                        output_path = convert_input_to_output_path(input_path, True)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        shutil.copy(convert_input_to_output_path(input_path, False), output_path)
                        response_msg = f"Classification: YES, image saved to {output_path}"
                        conn.sendall(response_msg.encode("utf-8"))
                        logger.info(response_msg)
                    else:
                        response_msg = "Classification: NO"
                        conn.sendall(response_msg.encode("utf-8"))
                        logger.info(response_msg)

if __name__ == "__main__":
    # At startup, remove the base output_images directory if it exists.
    base_output_dir = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/output_images"
    # Instead of deleting the directory, clear its contents
    if os.path.exists(base_output_dir):
        clear_directory(base_output_dir)
        logger.info(f"Cleared contents of {base_output_dir}")
    else:
        os.makedirs(base_output_dir, exist_ok=True)
    # Ensure the base output directory has proper permissions
    os.chmod(base_output_dir, 0o777)
    logger.info(f"Set permissions for {base_output_dir} to 777")
    start_socket_server()

