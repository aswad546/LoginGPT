#!/usr/bin/env python3
import requests
import base64
import re
import sys
from io import BytesIO
from PIL import Image

# Configuration for vLLM Serve
VLLM_SERVE_URL = "http://127.0.0.1:8000/v1/completions"  # Adjust as needed
API_KEY = "token-abc123"

def encode_image_to_base64(image_path, target_size=(224, 224)):
    """Downscale the image and return its base64-encoded string."""
    img = Image.open(image_path).convert("RGB")
    img = img.resize(target_size)  # Downscale to reduce prompt size
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_vllm_inference.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    image_b64 = encode_image_to_base64(image_path)  # Downscaled image
    
    # Use the exact same "find_login" prompt as before
    prompt_text = (
        "<|im_start|>user\n"
        "<|vision_start|><|image_base64|>" + image_b64 + "<|vision_end|>\n"
        "Analyze the provided image and identify where do I click to access the login page. \n"
        "This may be an element labeled abstractly like Online Banking, My Account, Login or a person icon or even a form submit button associated with login credentials etc.\n"
        "Output Format:\n\n"
        "Element Type: Login Button\n"
        "Description: [Brief description]\n"
        "Bounding Box Coordinates: (x1, y1, x2, y2)\n"
        "Guidelines:\n"
        "- Only focus on the element that takes me to the login page.\n"
        "- Provide precise bounding box coordinates.\n"
        "<|im_end|>"
    )
    
    # Build the payload for the vLLM Serve API call
    payload = {
        "model": "OS-Copilot/OS-Atlas-Base-7B",
        "prompt": prompt_text,
        "max_tokens": 512
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print("Sending request to vLLM Serve...")
    response = requests.post(VLLM_SERVE_URL, json=payload, headers=headers)
    if response.status_code != 200:
        print("Error from vLLM Serve:", response.text)
        sys.exit(1)
    
    result = response.json()
    output_text = result.get("generated_text", "")
    print("Model Output:")
    print(output_text)
    
    # Parse bounding box coordinates from the output
    # This regex allows for optional parentheses around the numbers
    pattern = r'Bounding Box Coordinates:\s*\(?\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)?'
    matches = re.findall(pattern, output_text)
    if matches:
        bounding_boxes = [tuple(map(int, match)) for match in matches]
        print("Parsed Bounding Boxes:", bounding_boxes)
    else:
        print("No bounding boxes found.")

if __name__ == "__main__":
    main()
