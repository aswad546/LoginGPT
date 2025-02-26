from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
import torch

# Load the model on GPU 0 explicitly by setting device_map to use only cuda:0
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    torch_dtype="auto",
    device_map={"": "cuda:0"}  # forces the model to load on GPU 0
)
# model.to("cuda")
# model.tie_weights()

# Set desired pixel limits for resizing to reduce GPU memory usage.
min_pixels = 256 * 28 * 28   # lower bound of pixels
max_pixels = 1280 * 28 * 28  # upper bound of pixels

# Load the processor with resizing parameters.
processor = AutoProcessor.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",
    min_pixels=min_pixels,
    max_pixels=max_pixels
)

# Example message using a local file URL and a text instruction.
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "file:///tmp/Workspace/SSO-Monitor-mine/worker/modules/loginpagedetection/screenshot_flows/www_hancockwhitney_com__/flow_1/page_1.png",
            },
            {"type": "text", "text": """Analyze the provided image and determine if it contains input fields associated with the login flow of a web page. Specifically, look for:

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
"NO" (if no relevant login input field is found)."""},
        ],
    }
]

# Preparation for inference:
# 1. Render the prompt using the chat template.
text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

# 2. Process vision inputs (images, videos) from the messages.
image_inputs, video_inputs = process_vision_info(messages)

# 3. Create the full set of model inputs (text and image tensors).
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
inputs = inputs.to("cuda")  # Ensure inputs are on GPU 0

# Inference: Generation of the output.
generated_ids = model.generate(**inputs, max_new_tokens=2048)

# Trim off the prompt tokens from the generated output.
generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

# Decode to obtain the output text.
output_text = processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
print("Model output:", output_text)
