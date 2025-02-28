import re
import time
import torch
import requests
from PIL import Image, ImageDraw
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor, pipeline, AutoModelForSeq2SeqLM
from qwen_vl_utils import process_vision_info
from openai import OpenAI  # vLLM via OpenAI client interface
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Setup for Transformers (local inference)
# ---------------------------
device = torch.device("cuda:0")
logger.info("Loading Transformers model and processor...")
model = Qwen2VLForConditionalGeneration.from_pretrained(
    "OS-Copilot/OS-Atlas-Base-7B", torch_dtype="auto", device_map={"": "cuda:0"}, cache_dir='/tmp/'
)
processor = AutoProcessor.from_pretrained("OS-Copilot/OS-Atlas-Base-7B")
logger.info("Transformers model loaded.")
# (Summarization is not used in this minimal example, but loaded if needed)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=0)
attention_model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn").to(device)

# ---------------------------
# Setup for vLLM via OpenAI client interface
# ---------------------------
API_KEY = "token-abc123"
client = OpenAI(
    api_key=API_KEY,
    base_url="http://127.0.0.1:8002/v1",
)

# ---------------------------
# Utility function: Convert file path to URL for vLLM inference
# ---------------------------
def convert_path_to_url(path: str) -> str:
    marker = "analyzers"
    idx = path.find(marker)
    if idx == -1:
        logger.error("Marker 'analyzers' not found in the path.")
        return None
    relative_part = path[idx + len(marker) + 1:]  # +1 to skip the '/'
    url = f"http://localhost:8001/{relative_part}"
    return url

# ---------------------------
# Utility function: Extract and scale bounding boxes from model output
# ---------------------------
def extract_scaled_boxes(output_text: str, width: int, height: int, scale_factor: float = 1000.0):
    pattern = r'Bounding Box Coordinates:\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
    matches = re.findall(pattern, output_text)
    boxes = [((int(x1), int(y1)), (int(x2), int(y2))) for x1, y1, x2, y2 in matches]
    scaled = [
        (
            (int((x1 / scale_factor) * width), int((y1 / scale_factor) * height)),
            (int((x2 / scale_factor) * width), int((y2 / scale_factor) * height))
        )
        for (x1, y1), (x2, y2) in boxes
    ]
    return scaled

# ---------------------------
# Utility function: Draw bounding boxes on an image and save it
# ---------------------------
def draw_and_save_boxes(image: Image.Image, boxes, outline_color, save_path):
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    for box in boxes:
        draw.rectangle([box[0], box[1]], outline=outline_color, width=3)
    img_copy.save(save_path)
    logger.info(f"Saved image with boxes to {save_path}")

# ---------------------------
# Main minimal example
# ---------------------------
if __name__ == '__main__':
    # Set your image path (should include 'screenshot_flows' in the path for URL conversion)
    local_img_path = "/tmp/Workspace/SSO-Monitor-mine/worker/modules/analyzers/ss.png"
    
    # Open image using PIL
    try:
        img = Image.open(local_img_path)
    except Exception as e:
        logger.error(f"Could not open image: {e}")
        exit(1)
    width, height = img.size
    logger.info(f"Image dimensions: {width}x{height}")
    
    # Define a prompt (choose one of your task prompts; here we use the login element one)
    prompt_text = """
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
    
    # --------------
    # Transformers Inference (local)
    # --------------
    # Prepare message payload for local inference (using our processor)
    image_url = convert_path_to_url(local_img_path)
    messages_transformers = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": image_url},  # Passing file path as a placeholder
                {"type": "text", "text": prompt_text},
            ],
        }
    ]
    text_for_transformers = processor.apply_chat_template(messages_transformers, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages_transformers)
    inputs = processor(
        text=[text_for_transformers],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(device if torch.cuda.is_available() else "cpu")
    start_time = time.time()
    generated_ids = model.generate(**inputs, max_new_tokens=512)
    # Trim the prompt part from the generated output:
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text_transformers = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )[0]
    elapsed_transformers = time.time() - start_time
    logger.info(f"Transformers Output: {output_text_transformers}")
    logger.info(f"Transformers inference time: {elapsed_transformers:.2f} sec")
    
    # --------------
    # vLLM Inference via OpenAI client
    # --------------
    # Convert the image path to a URL (vLLM expects a URL for the image)
    image_url = convert_path_to_url(local_img_path)
    if image_url is None:
        logger.error("Error converting image path to URL.")
        exit(1)
    
    messages_vllm = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": prompt_text}
        ]}
    ]
    
    start_time = time.time()
    try:
        chat_response = client.chat.completions.create(
            model="OS-Copilot/OS-Atlas-Base-7B",
            messages=messages_vllm,
            max_tokens=512,
            temperature=0.01,
            top_p=0.001,
        )
        output_text_vllm = chat_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"vLLM inference error: {e}")
        output_text_vllm = ""
    elapsed_vllm = time.time() - start_time
    logger.info(f"vLLM Output: {output_text_vllm}")
    logger.info(f"vLLM inference time: {elapsed_vllm:.2f} sec")
    
    # --------------
    # Extract bounding boxes from both outputs and superimpose them on the image
    # --------------
    boxes_transformers = extract_scaled_boxes(output_text_transformers, width, height)
    boxes_vllm = extract_scaled_boxes(output_text_vllm, width, height)
    
    logger.info(f"Transformers boxes: {boxes_transformers}")
    logger.info(f"vLLM boxes: {boxes_vllm}")
    
    # Save images with drawn bounding boxes:
    draw_and_save_boxes(img, boxes_transformers, outline_color="red", save_path="transformers_output.png")
    draw_and_save_boxes(img, boxes_vllm, outline_color="blue", save_path="vllm_output.png")
    
    logger.info("Comparison images saved: transformers_output.png and vllm_output.png")
