import openai
from PIL import Image
import base64
import io
import json
import csv
from datetime import datetime
import os
import sys
import hashlib

openai.api_key = os.environ.get("OPENAI_API_KEY")

def encode_image(image_path):
    """Convert image to base64 encoding."""
    with Image.open(image_path) as image:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()
        encoded_image = base64.b64encode(img_bytes).decode("utf-8")
        return encoded_image

def log_usage(image_path, input_tokens, output_tokens, total_cost, image_hash):
    """Log API usage and costs to CSV file."""
    log_file = "data/gpt_usage_log.csv"
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    file_exists = os.path.isfile(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "image_path", "input_tokens", "output_tokens", "total_cost", "image_hash"])
        writer.writerow([
            datetime.now().isoformat(),
            image_path,
            input_tokens,
            output_tokens,
            f"{total_cost:.4f}",
            image_hash
        ])

def process_receipt(image_path, image_hash):
    """Process receipt image using GPT-4 Vision to extract and classify data."""
    base64_image = encode_image(image_path)

    response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": """
You are a data extraction assistant. Your task is to extract and classify data from a receipt image and return a clean JSON object with this exact structure:

{
  "store_info": {
    "name": "string",
    "address": "string",
    "phone": "string",
    "date": "string (format: YYYY-MM-DD)"
  },
  "transaction_details": {
    "subtotal": number,
    "tax": number,
    "total": number,
    "payment_method": "string",
    "change": number
  },
  "items": [
    {
      "name": "string",
      "price": number,
      "quantity": number,
      "category": "Food | Electronics | Services | Personal Care | Household | Other",
      "subtotal": number
    }
  ]
}

**Rules**:
- Format all prices as decimal numbers (no currency symbols).
- Include quantity for each item (default to 1 if not listed).
- Categorize each item accurately.
- Calculate item subtotal = price × quantity.
- Extract and include the "change" amount if visible.
- Format dates as YYYY-MM-DD (e.g., 2024-03-19).
- Return ONLY the JSON object. Do not include any explanations or markdown.
"""
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                },
                {
                    "type": "text",
                    "text": "Extract all data from this receipt image using the rules above and output a valid JSON."
                }
            ]
        }
    ],
    max_tokens=1500,
    temperature=0.2
)


    content = response.choices[0].message.content
    usage = response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens

    # Cost Calculation for GPT-4 Vision
    input_cost = (input_tokens / 1000) * 0.005
    output_cost = (output_tokens / 1000) * 0.015
    total_cost = input_cost + output_cost

    # Log usage
    log_usage(image_path, input_tokens, output_tokens, total_cost, image_hash)
    
    try:
        # Clean the content to ensure it's valid JSON
        content = content.strip()
        # Remove any markdown code block markers if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        print("Raw response:", content)  # Debug print
        
        # Parse the content as JSON
        json_data = json.loads(content)
        return json_data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print("Raw response:", content)
        # Return a default structure with error information
        return {
            "error": "Failed to parse receipt data",
            "raw_response": content,
            "store_info": {"name": "Error", "address": "", "phone": "", "date": ""},
            "transaction_details": {"total": 0, "tax": 0, "subtotal": 0, "payment_method": "", "change": 0},
            "items": []
        }

def main():
    """Main function to process receipt image from command line argument."""
    if len(sys.argv) != 2:
        print("Usage: python process_receipt.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image file not found at {image_path}")
        sys.exit(1)

    try:
        # For command line testing, we'll calculate hash here as well.
        # In the Streamlit app, hash is passed from app.py
        temp_hash = hashlib.sha256(open(image_path, 'rb').read()).hexdigest()
        result = process_receipt(image_path, temp_hash)
        print("Type of result:", type(result))
        print("Result:", json.dumps(result, indent=2))
        
        # Save the processed data
        with open("processed_receipt.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print("Receipt processing completed successfully!")
    except Exception as e:
        print(f"Error processing receipt: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 