import os
import shutil
import torch
from PIL import Image
from transformers import MllamaForConditionalGeneration, AutoProcessor

import logging

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
model.to(device)               # Move model to GPU 1
model.tie_weights()

processor = AutoProcessor.from_pretrained(model_id)

logger.info(f"Successfully loaded model classify_screenshots")

# -----------------------
# Construct the Prompt
# -----------------------
def construct_prompt():
    """Generate the instruction prompt for the model."""
    return """
Analyze the provided image and determine if it contains input fields elements 
that are associated with the login flow of a web page. Examples include:

- Username or email input fields other examples could include forms with user id, a unique user id etc.
- Password input fields

Try to detect if there is a login form on the page that contains any of these elements ignore any irrelevant elements.
For example input fields not related to the login form. Also answer yes only if there is at least one relevant visible input form field present.

If you detect such elements, respond strictly with 'Yes'.
If no such elements are detected, respond strictly with 'No'.

Output format (important): 
Yes or No
"""

# -----------------------
# Model Inference Function
# -----------------------
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

# -----------------------
# Directory Traversal and Saving
# -----------------------
def process_images(input_dir, output_dir):
    """Process all images in a directory structure and save only those with login elements."""
    if not os.path.exists(output_dir):
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
                if 'yes' in response.lower():
                    # Create corresponding directory in output
                    relative_path = os.path.relpath(root, input_dir)
                    target_dir = os.path.join(output_dir, relative_path)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Copy the image to the target directory
                    shutil.copy(image_path, os.path.join(target_dir, file))
                    print(f"Saved: {os.path.join(target_dir, file)}")

# -----------------------
# Main Script
# -----------------------
if __name__ == "__main__":
    input_directory = "/u1/a8tariq/LoginCrawler/OS-ATLAS/screenshot_flows"   # Directory containing images in subdirectories
    output_directory = "./output_images" # Directory to save images with login elements
    
    print("Starting image processing...")
    process_images(input_directory, output_directory)
    print("Processing completed.")
