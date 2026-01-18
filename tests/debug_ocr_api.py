#!/usr/bin/env python3
"""
Debug script to test OCR API call format.
"""

import base64
import requests
import fitz
import json

# Read PDF
pdf_path = "data/papers/2601.10716_WildRayZer_ Self-supervised Large View Synthesis in Dynamic Environments.pdf"

print("=" * 60)
print("Testing OCR API Call Format")
print("=" * 60)

# Open PDF and convert first page to image
doc = fitz.open(pdf_path)
page = doc[0]

# Render page to image
mat = fitz.Matrix(2.0, 2.0)
pix = page.get_pixmap(matrix=mat)
img_data = pix.tobytes("png")

# Base64 encode
img_base64 = base64.b64encode(img_data).decode("utf-8")
img_data_url = f"data:image/png;base64,{img_base64}"

print(f"\nPDF pages: {len(doc)}")
print(f"First page image size: {len(img_data)} bytes")
print(f"Base64 encoded size: {len(img_base64)} chars")

doc.close()

# Test different payload formats
test_payloads = [
    {
        "name": "With DeepSeek-OCR model",
        "payload": {
            "model": "/Users/imac/dev/DeepSeek-OCR-8bit",
            "image": [img_data_url],
            "prompt": "<|grounding|>Convert the document to markdown.",
            "max_tokens": 4096,
            "temperature": 0.0,
        }
    },
    {
        "name": "Without model field",
        "payload": {
            "image": [img_data_url],
            "prompt": "<|grounding|>Convert the document to markdown.",
            "max_tokens": 4096,
            "temperature": 0.0,
        }
    },
]

for test in test_payloads:
    print(f"\n{'=' * 60}")
    print(f"Testing: {test['name']}")
    print(f"{'=' * 60}")

    print(f"Payload keys: {list(test['payload'].keys())}")
    print(f"Image field type: {type(test['payload'].get('image'))}")

    if isinstance(test['payload'].get('image'), list):
        print(f"Image array length: {len(test['payload']['image'])}")

    try:
        response = requests.post(
            "http://192.168.31.101:8000/generate",
            json=test['payload'],
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            print(f"✓ Success!")
            result = response.json()
            print(f"Response keys: {list(result.keys())}")

            text = result.get("text", "")
            print(f"\nText length: {len(text)}")
            print(f"First 500 chars:\n{text[:500]}")
            break  # Stop on first success
        else:
            print(f"✗ Failed")
            print(f"Response: {response.text[:500]}")

    except Exception as e:
        print(f"✗ Error: {e}")
