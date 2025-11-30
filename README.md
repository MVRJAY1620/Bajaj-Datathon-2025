# Bajaj-Datathon-2025
Bajaj health Datathon IIT Madras Placement 2025

📄 Bill Extraction API – README

🚀 Overview
This project implements a Bill / Invoice Line Item Extraction API for the HackRx Datathon (IIT challenge).
The solution extracts line-item details, including:
1. item_name
2. item_quantity
3. item_rate
4. item_amount


The API follows the exact response structure required in the problem statement and processes single-page bills from a provided URL.

OCR extraction is done using OCR.Space API (cloud OCR) to avoid local resource dependencies and support deployment on lightweight cloud platforms.

🧠 Approach
Key steps in processing:
1. Download the bill document from URL.
2. OCR using OCR.Space and request bounding-box overlays.
3. Flatten tokens (word, x/y position, width, height).
4. Group tokens into text lines based on vertical alignment.
5. Parse item rows using heuristics:
6. skip header and total lines
7. detect numeric columns
8. right-most number → item_amount
9. previous numbers → quantity and rate
10. preceding text → item_name
11. Return structured bill items in required JSON schema.

No LLM currently used

To minimize cost & dependency, this version uses simple rule-based parsing.
Future improvement: optional LLM refinement and token-aware prompting.

🛠 Technology Stack
- Component	Tool
- Backend Framework	FastAPI
- OCR Engine	OCR.Space Cloud API
- Deployment	Render (free tier)
- Language	Python 3

🔗 API Endpoint
POST /extract-bill-data
Content-Type: application/json

📥 Request Body
{
  "document": "https://hackrx.blob.core.windows.net/assets/datathon-IIT/sample_2.png"
}

📤 Sample Response
{
  "is_success": true,
  "token_usage": {
    "total_tokens": 0,
    "input_tokens": 0,
    "output_tokens": 0
  },
  "data": {
    "pagewise_line_items": [
      {
        "page_no": "1",
        "page_type": "Bill Detail",
        "bill_items": [
          {
            "item_name": "Livi 300mg Tab",
            "item_amount": 448.0,
            "item_rate": 32.0,
            "item_quantity": 14.0
          }
        ]
      }
    ],
    "total_item_count": 1
  }
}


⚠ Note: Item values depend on OCR accuracy & document quality.

📦 Project Structure
.
├── app.py
├── requirements.txt
└── README.md

🌍 Deployment Instructions (Render Cloud)

Push this code to GitHub.

Create a new Web Service in Render → Connect repo.

Configure:

Build Command  : pip install -r requirements.txt
Start Command  : uvicorn app:app --host 0.0.0.0 --port $PORT


Add Environment Variable:
OCR_SPACE_API_KEY = <your-key>

Deploy → live endpoint URL available for submission.

🧪 Testing via Swagger

Open:

https://<your-render-url>/docs


Use the interactive POST /extract-bill-data UI to test invoices.

📈 Future Improvements

LLM-powered structured extraction for better accuracy

Multi-page PDFs

Sub-total & Final total detection with reconciliation

Confidence scoring and OCR cleanup

👤 Author

Vandana Rachel
Undergraduate Aerospace Engineering
IIT Madras
