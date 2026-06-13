"""
ScanFiler — Local Document Classifier (Tesseract OCR + Ollama LLM)

Extracts text from scanned documents using Tesseract OCR, then classifies
the content using a local Ollama LLM. Everything runs on your machine —
no data ever leaves it.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytesseract
from PIL import Image
from pdf2image import convert_from_path


# ─── Classification Prompt ──────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """You are a document classification assistant. Based on the text extracted from a scanned document, determine what type of document this is.

Return ONLY a valid JSON object with these exact keys — no explanation, no markdown:
{{
    "document_type": "The category (e.g., Bank Statement, Billing Statement, Tax Document, Medical Bill, Insurance Document, Pay Stub, Invoice, Receipt, Legal Document, Government Form)",
    "company": "The company/institution/organization name (e.g., TD Bank, PSEG, IRS, Aetna)",
    "date": "The statement/billing date in YYYY-MM format. If only a year is visible, use YYYY. If no date found, use null",
    "confidence": 0.95,
    "suggested_filename": "A descriptive filename without extension using underscores (e.g., TD_Bank_Statement_June_2026)"
}}

Rules:
- "document_type" should be a clean, capitalized category name
- "company" should be the official/common company name
- "date" MUST be the actual statement, billing, or document date (ignore copyright or print dates)
- The year/month in "suggested_filename" MUST exactly match the "date" field
- "confidence" is a float 0.0–1.0 reflecting classification certainty
- If you cannot determine type or company, set confidence below 0.5
- Return ONLY the JSON object

Here is the extracted text from the document:

{text}"""


# ─── OCR Functions ──────────────────────────────────────────────────────────

def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image file using Tesseract OCR."""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"OCR failed for image {image_path}: {e}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF by converting pages to images, then OCR-ing each."""
    try:
        images = convert_from_path(pdf_path, dpi=300)
        texts = []
        for i, page_image in enumerate(images):
            page_text = pytesseract.image_to_string(page_image)
            texts.append(page_text.strip())
        return "\n\n".join(texts)
    except Exception as e:
        raise RuntimeError(f"OCR failed for PDF {pdf_path}: {e}")


def extract_text(file_path: str) -> str:
    """Extract text from a supported file (PDF or image)."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"):
        return extract_text_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ─── Ollama Classification ─────────────────────────────────────────────────

def classify_with_ollama(text: str, model: str, host: str) -> dict:
    """
    Send extracted text to a local Ollama model for classification.
    Uses the ollama Python library to communicate with the local server.
    """
    import ollama

    if not text or len(text.strip()) < 10:
        return _error_result("Extracted text is too short or empty — OCR may have failed")

    # Truncate very long texts to keep inference fast (first 3000 chars is enough)
    truncated = text[:3000] if len(text) > 3000 else text

    prompt = CLASSIFICATION_PROMPT.format(text=truncated)

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a document classifier. You MUST respond with ONLY a valid JSON object. No explanation, no markdown fences.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            options={
                "temperature": 0.1,  # Low temperature for consistent classification
            },
        )

        response_text = response["message"]["content"]
        return _parse_response(response_text)

    except Exception as e:
        error_msg = str(e)
        
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return _error_result(
                "Cannot connect to Ollama. Make sure it's running: ollama serve"
            )
        if "not found" in error_msg.lower():
            return _error_result(
                f"Model '{model}' not found. Install it: ollama pull {model}"
            )
        return _error_result(f"Ollama error: {error_msg}")


# ─── Main Classification Entry Point ───────────────────────────────────────

def classify_document(file_path: str, model: str, host: str) -> dict:
    """
    Full pipeline: OCR the document, then classify with local LLM.

    Args:
        file_path: Path to the PDF or image file.
        model: Ollama model name (e.g., "llama3.2").
        host: Ollama server URL (e.g., "http://localhost:11434").

    Returns:
        A dict with keys: document_type, company, date, confidence, suggested_filename.
        On failure, includes an 'error' key.
    """
    path = Path(file_path)

    if not path.exists():
        return _error_result(f"File not found: {file_path}")

    # Step 1: Extract text via OCR
    try:
        extracted_text = extract_text(file_path)
    except Exception as e:
        return _error_result(f"OCR error: {str(e)}")

    if not extracted_text.strip():
        return _error_result("OCR produced no text — the document may be blank or unreadable")

    # Step 2: Classify with local LLM
    result = classify_with_ollama(extracted_text, model, host)
    result["ocr_preview"] = extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text

    return result


# ─── Helpers ────────────────────────────────────────────────────────────────

def _parse_response(text: str) -> dict:
    """Parse Ollama's response text into a classification dict."""
    cleaned = text.strip()

    # Strip markdown fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            try:
                result = json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                return _error_result(f"Could not parse LLM response as JSON: {text[:200]}")
        else:
            return _error_result(f"No JSON found in LLM response: {text[:200]}")

    # Validate required keys
    required_keys = ["document_type", "company", "date", "confidence", "suggested_filename"]
    for key in required_keys:
        if key not in result:
            result[key] = None

    # Ensure confidence is a float
    try:
        result["confidence"] = float(result.get("confidence", 0))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    return result


def _error_result(message: str) -> dict:
    """Create an error classification result."""
    return {
        "document_type": "Unknown",
        "company": "Unknown",
        "date": None,
        "confidence": 0.0,
        "suggested_filename": None,
        "error": message,
    }
