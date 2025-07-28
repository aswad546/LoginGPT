#!/usr/bin/env python3
import sys
import time
import re
from openai import OpenAI

def classify_image(image_url):
    """
    Send a chat completion request to vLLM Serve using the image URL.
    Returns a tuple (final_answer, full_response, inference_time).
    """
    # Configure OpenAI client to use your vLLM Serve instance
    client = OpenAI(
        api_key="token-abc123",
        base_url="http://localhost:8000/v1",
    )

    # The prompt text to send to the model
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

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url", 
                    "image_url": {"url": image_url},
                    "min_pixels": 200704,   # 256*28*28
                    "max_pixels": 401408,   # 512*28*28
                },
                {"type": "text", "text": PROMPT_TEXT},
            ]
        }
    ]
    
    try:
        print(f"Starting inference at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        start_time = time.time()
        
        chat_response = client.chat.completions.create(
            model="Qwen/Qwen2.5-VL-7B-Instruct",
            messages=messages,
            max_tokens=512,
        )
        
        end_time = time.time()
        inference_time = end_time - start_time
        
        output_text = chat_response.choices[0].message.content.strip()
        
        # Extract final answer ("YES" or "NO")
        matches = re.findall(r'\b(YES|NO)\b', output_text, re.IGNORECASE)
        final_answer = matches[-1].upper() if matches else None
        
        return final_answer, output_text, inference_time, chat_response
    
    except Exception as e:
        print(f"Error during classification: {e}")
        return None, None, None, None

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image_url>")
        sys.exit(1)
    
    image_url = sys.argv[1]
    print(f"Sending request to classify image: {image_url}")
    
    final_answer, full_response, inference_time, raw_response = classify_image(image_url)
    
    print("\n========== RESPONSE ==========")
    if full_response:
        print(full_response)
    else:
        print("No response received")
    
    print("\n========== FINAL ANSWER ==========")
    if final_answer:
        print(final_answer)
    else:
        print("Could not determine final answer")
    
    print("\n========== TIMING ==========")
    if inference_time:
        print(f"Inference completed in {inference_time:.2f} seconds")
        
        # Display token usage if available
        if hasattr(raw_response, 'usage'):
            print(f"\n========== TOKEN USAGE ==========")
            print(f"Prompt tokens: {raw_response.usage.prompt_tokens}")
            print(f"Completion tokens: {raw_response.usage.completion_tokens}")
            print(f"Total tokens: {raw_response.usage.total_tokens}")

if __name__ == "__main__":
    main()