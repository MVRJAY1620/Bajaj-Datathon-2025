import io
import requests
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List

app = FastAPI(title="Bill Extractor - Assignment Schema")

OCR_SPACE_API_URL = "https://api.ocr.space/parse/image"
OCR_SPACE_API_KEY = "K85891760088957"  # your key
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


class DocReq(BaseModel):
    document: str


def download_bytes(url: str) -> bytes:
    resp = requests.get(url, stream=True, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Download failed: {resp.status_code}")
    return resp.content


def call_ocr_space(file_bytes: bytes, filename_hint: str, api_key: str = OCR_SPACE_API_KEY) -> Dict[str, Any]:
    files = {
        "file": (filename_hint, io.BytesIO(file_bytes))
    }
    data = {
        "apikey": api_key,
        "language": "eng",
        "isOverlayRequired": "True"   # must be string
    }
    resp = requests.post(OCR_SPACE_API_URL, files=files, data=data, timeout=120)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OCR provider error: {resp.status_code}")
    return resp.json()

def group_tokens_to_lines(tokens: List[dict], y_tol: int = 8) -> List[dict]:
    """
    Group word tokens into lines based on their vertical position.
    Each line = { 'words': [token,...] }
    """
    # sort by vertical then horizontal
    tokens = sorted(tokens, key=lambda t: (t["top"], t["left"]))
    lines: List[dict] = []
    for tok in tokens:
        placed = False
        for line in lines:
            # if token is close in Y to this line, put it there
            if abs(tok["top"] - line["avg_top"]) <= y_tol:
                line["words"].append(tok)
                line["avg_top"] = sum(w["top"] for w in line["words"]) / len(line["words"])
                placed = True
                break
        if not placed:
            lines.append({"avg_top": tok["top"], "words": [tok]})

    # sort words within each line left→right
    for line in lines:
        line["words"].sort(key=lambda w: w["left"])
    return lines


def extract_items_from_lines(lines: List[dict]) -> List[dict]:
    """
    Very simple heuristic:
    - Skip header/total lines
    - Right-most number in the line = item_amount
    - Numbers before that = quantity, rate (if present)
    - Everything before first numeric = item_name (minus serial number)
    """
    items: List[dict] = []

    for line in lines:
        words = line["words"]
        texts = [w["text"] for w in words]
        full = " ".join(texts).lower()

        # skip obvious non-item lines
        if any(k in full for k in ["sl#", "description", "qty", "rate",
                                   "gross amount", "discount", "category total", "total"]):
            continue

        # find all numeric tokens and rightmost one as amount
        numeric_indices = []
        for i, t in enumerate(words):
            txt = t["text"].replace(",", "")
            if NUMBER_RE.fullmatch(txt):
                try:
                    val = float(txt)
                    numeric_indices.append((i, val))
                except ValueError:
                    pass

        if not numeric_indices:
            continue  # no numbers -> not an item row

        # rightmost numeric = amount
        amount_idx, amount_val = numeric_indices[-1]

        # numbers before that = qty / rate (very simple guess)
        before = [pair for pair in numeric_indices if pair[0] < amount_idx]

        qty_val = None
        rate_val = None
        if len(before) == 1:
            qty_val = before[0][1]
        elif len(before) >= 2:
            # assume layout: ... qty  rate  amount
            qty_val = before[-2][1]
            rate_val = before[-1][1]

        # item_name = text before first numeric (ignore simple serial at start)
        first_num_idx = before[0][0] if before else amount_idx
        name_tokens = texts[:first_num_idx]

        # drop leading pure-integer as serial number
        if name_tokens and NUMBER_RE.fullmatch(name_tokens[0]):
            name_tokens = name_tokens[1:]

        item_name = " ".join(name_tokens).strip()
        if not item_name:
            # if empty name, skip to reduce garbage
            continue

        items.append({
            "item_name": item_name,
            "item_amount": float(f"{amount_val:.2f}"),
            "item_rate": float(f"{rate_val:.2f}") if rate_val is not None else None,
            "item_quantity": float(qty_val) if qty_val is not None else None
        })

    return items


@app.post("/extract-bill-data")
async def extract_bill_data(req: DocReq):
    url = req.document
    try:
        # 1) Download file
        file_bytes = download_bytes(url)

        # 2) Clean filename (strip query string)
        filename = url.split("/")[-1]
        filename = filename.split("?")[0]
        if not filename:
            filename = "upload.png"

        # 3) Call OCR.Space
        ocr_json = call_ocr_space(file_bytes, filename)

        parsed = ocr_json.get("ParsedResults")
        if not parsed:
            return {
                "is_success": False,
                "token_usage": {
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0
                },
                "data": {
                    "pagewise_line_items": [],
                    "total_item_count": 0,
                    "ocr_tokens": []
                }
            }

        first = parsed[0]
        text_overlay = first.get("TextOverlay", {})
        lines_ov = text_overlay.get("Lines", [])

        # ---- build flat tokens from overlay ----
        ocr_tokens = []
        for line in lines_ov:
            for w in line.get("Words", []):
                ocr_tokens.append({
                    "text": w.get("WordText", ""),
                    "left": w.get("Left", 0),
                    "top": w.get("Top", 0),
                    "width": w.get("Width", 0),
                    "height": w.get("Height", 0)
                })

        # ---- group tokens into lines & extract items ----
        grouped_lines = group_tokens_to_lines(ocr_tokens)
        bill_items = extract_items_from_lines(grouped_lines)

        # ---- build final response in required schema ----
        return {
            "is_success": True,
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
                        "bill_items": bill_items
                    }
                ],
                "total_item_count": len(bill_items),
                # keep tokens for debugging (you can remove later)
                "ocr_tokens": ocr_tokens
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


