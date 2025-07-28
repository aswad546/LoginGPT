from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info
import time
import torch

# Start timing the overall process
start_time_total = time.time()

# default: Load the model on the available device(s)
print("Loading model...")
start_time_model_loading = time.time()
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct", torch_dtype="auto", device_map="cuda:0"
)
model_loading_time = time.time() - start_time_model_loading
print(f"Model loading time: {model_loading_time:.2f} seconds")

# We recommend enabling flash_attention_2 for better acceleration and memory saving, especially in multi-image and video scenarios.
# model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
#     "Qwen/Qwen2.5-VL-7B-Instruct",
#     torch_dtype=torch.bfloat16,
#     attn_implementation="flash_attention_2",
#     device_map="auto",
# )

min_pixels = 128*28*28
max_pixels = 512*28*28

# default processor loading
print("Loading processor...")
start_time_processor_loading = time.time()
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-7B-Instruct", min_pixels=min_pixels, max_pixels=max_pixels)
processor_loading_time = time.time() - start_time_processor_loading
print(f"Processor loading time: {processor_loading_time:.2f} seconds")

# The default range for the number of visual tokens per image in the model is 4-16384.
# You can set min_pixels and max_pixels according to your needs, such as a token range of 256-1280, to balance performance and cost.


messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "http://localhost:8001/www_fbonline_biz/flow_0/page_1.png",
                "min_pixels": min_pixels,  # 256*28*28
                "max_pixels": max_pixels,  # 512*28*28
            },
            {"type": "text", "text":
"""
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
 """},
        ],
    }
]

# Measure text template processing time
print("Applying chat template...")
start_time_template = time.time()
text = processor.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
template_time = time.time() - start_time_template
print(f"Chat template processing time: {template_time:.2f} seconds")

# Measure image processing time
print("Processing vision info...")
start_time_vision = time.time()
image_inputs, video_inputs = process_vision_info(messages)
vision_processing_time = time.time() - start_time_vision
print(f"Vision info processing time: {vision_processing_time:.2f} seconds")

# Measure tokenization time
print("Running processor...")
start_time_tokenization = time.time()
inputs = processor(
    text=[text],
    images=image_inputs,
    videos=video_inputs,
    padding=True,
    return_tensors="pt",
)
tokenization_time = time.time() - start_time_tokenization
print(f"Processor tokenization time: {tokenization_time:.2f} seconds")
print(f"Image shape after processing: {inputs.pixel_values.shape if hasattr(inputs, 'pixel_values') else 'No pixel_values found'}")

# Measure device transfer time
print("Moving inputs to device...")
start_time_to_device = time.time()
inputs = inputs.to("cuda")
to_device_time = time.time() - start_time_to_device
print(f"Device transfer time: {to_device_time:.2f} seconds")

# Measure inference time
print("Running inference...")
start_time_inference = time.time()
with torch.no_grad():  # Add this for inference to prevent gradient calculation
    generated_ids = model.generate(**inputs, max_new_tokens=512)
inference_time = time.time() - start_time_inference
print(f"Inference time: {inference_time:.2f} seconds")

# Measure post-processing time
print("Post-processing output...")
start_time_postprocess = time.time()
generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]
output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
)
postprocess_time = time.time() - start_time_postprocess
print(f"Post-processing time: {postprocess_time:.2f} seconds")

# Calculate total time
total_time = time.time() - start_time_total
print(f"\n--- Performance Summary ---")
print(f"Total execution time: {total_time:.2f} seconds")
print(f"Model loading time: {model_loading_time:.2f} seconds ({model_loading_time/total_time*100:.1f}%)")
print(f"Processor loading time: {processor_loading_time:.2f} seconds ({processor_loading_time/total_time*100:.1f}%)")
print(f"Chat template time: {template_time:.2f} seconds ({template_time/total_time*100:.1f}%)")
print(f"Vision processing time: {vision_processing_time:.2f} seconds ({vision_processing_time/total_time*100:.1f}%)")
print(f"Tokenization time: {tokenization_time:.2f} seconds ({tokenization_time/total_time*100:.1f}%)")
print(f"Device transfer time: {to_device_time:.2f} seconds ({to_device_time/total_time*100:.1f}%)")
print(f"Inference time: {inference_time:.2f} seconds ({inference_time/total_time*100:.1f}%)")
print(f"Post-processing time: {postprocess_time:.2f} seconds ({postprocess_time/total_time*100:.1f}%)")

# Print the actual output
print("\n--- Model Output ---")
print(output_text)

# Optional: Add detailed image processing inspection
print("\n--- Image Processing Details ---")
if hasattr(processor, 'image_processor'):
    print(f"Processor image_size: {processor.image_processor.size}")
    print(f"Processor crop_size: {processor.image_processor.crop_size if hasattr(processor.image_processor, 'crop_size') else 'N/A'}")
    print(f"Processor do_resize: {processor.image_processor.do_resize}")
    print(f"Processor resample: {processor.image_processor.resample if hasattr(processor.image_processor, 'resample') else 'N/A'}")