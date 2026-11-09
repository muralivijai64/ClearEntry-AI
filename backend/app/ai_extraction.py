
import json
import os
import re
from pathlib import Path

import pymupdf
from dotenv import load_dotenv
from openai import OpenAI


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from backend/.env")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=90.0,
    max_retries=1,
)


# --------------------------------------------------
# PDF TEXT EXTRACTION
# --------------------------------------------------

def extract_pdf_text(file_path: str) -> str:
    try:
        with pymupdf.open(file_path) as pdf:
            if pdf.page_count == 0:
                raise ValueError("The PDF contains no pages.")

            if pdf.page_count > 30:
                raise ValueError(
                    "PDF has more than 30 pages. Please split it first."
                )

            page_text = []

            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()

                text = re.sub(
                    r"<br\s*/?>",
                    "\n",
                    text,
                    flags=re.IGNORECASE,
                )

                if text:
                    page_text.append(
                        f"\n--- PAGE {page_number} ---\n{text}"
                    )

        extracted_text = "\n".join(page_text).strip()

        if len(extracted_text) < 30:
            raise ValueError(
                "No readable text was found. This may be a scanned PDF. "
                "OCR support is not enabled yet."
            )

        return extracted_text[:40000]

    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"Could not read PDF: {error}") from error


# --------------------------------------------------
# AI DOCUMENT EXTRACTION
# --------------------------------------------------

def extract_document_data(
    file_path: str,
    document_type: str,
) -> dict:

    document_text = extract_pdf_text(file_path)

    prompt = f"""
You are an expert customs documentation data extraction assistant.

Extract information from the supplied commercial shipping document.

DOCUMENT TYPE: {document_type}

SELLER AND BUYER IDENTIFICATION:
1. SELLER / EXPORTER means supplier.
2. BUYER / IMPORTER means importer.
3. When both headings appear before their company details,
   identify the first company/address block as seller and
   the second company/address block as buyer.
4. Include company name and relevant address.
5. Do not invent missing information.

GENERAL RULES:
- Extract only information supported by the document.
- Preserve original currency and measurement units.
- Do not calculate or invent missing values.
- Confidence must be a number from 0.0 to 1.0.
- Evidence must be a short phrase copied from the document.
- Missing fields must have null values, confidence 0.0,
  and null evidence.
- Confidence is an estimate, not a guarantee.
- Keep review_required true.
- Return valid JSON only. No Markdown fences.

IMPORTANT INVOICE TOTAL RULE:
- invoice_total means the final grand total payable/value
  explicitly printed on the invoice.
- Prefer the value beside labels such as TOTAL INVOICE VALUE,
  GRAND TOTAL, or TOTAL.
- Do not use subtotal when a separate grand total exists.
- Do not calculate invoice_total from line items.
- Preserve the currency in invoice_total, for example
  "USD 16,320.00".
- If no final total is printed, return null.
- For packing lists and Bills of Lading, invoice_total
  will normally be null.

Return this JSON structure:

{{
  "document_type": "{document_type}",
  "document_number": null,
  "document_date": null,
  "supplier": null,
  "importer": null,
  "currency": null,
  "incoterm": null,
  "origin_country": null,
  "destination_port": null,
  "invoice_total": null,
  "line_items": [
    {{
      "description": null,
      "hsn": null,
      "quantity": null,
      "unit": null,
      "unit_price": null,
      "line_total": null
    }}
  ],
  "package_count": null,
  "package_type": null,
  "gross_weight_kg": null,
  "net_weight_kg": null,
  "measurement_cbm": null,
  "container_numbers": [],
  "bill_of_lading_number": null,
  "vessel_name": null,
  "port_of_loading": null,
  "port_of_discharge": null,
  "field_confidence": {{
    "document_number": 0.0,
    "document_date": 0.0,
    "supplier": 0.0,
    "importer": 0.0,
    "currency": 0.0,
    "incoterm": 0.0,
    "origin_country": 0.0,
    "destination_port": 0.0,
    "invoice_total": 0.0,
    "line_items": 0.0,
    "package_count": 0.0,
    "gross_weight_kg": 0.0,
    "net_weight_kg": 0.0,
    "measurement_cbm": 0.0
  }},
  "evidence": {{
    "document_number": null,
    "document_date": null,
    "supplier": null,
    "importer": null,
    "currency": null,
    "incoterm": null,
    "origin_country": null,
    "destination_port": null,
    "invoice_total": null,
    "line_items": null,
    "package_count": null,
    "gross_weight_kg": null,
    "net_weight_kg": null,
    "measurement_cbm": null
  }},
  "review_required": true,
  "review_notes": []
}}

DOCUMENT TEXT:

{document_text}
"""

    try:
        response = client.responses.create(
            model=GROQ_MODEL,
            input=prompt,
        )

        output = response.output_text.strip()

        if output.startswith("```"):
            output = re.sub(
                r"^```(?:json)?\s*",
                "",
                output,
                count=1,
                flags=re.IGNORECASE,
            )
            output = re.sub(r"\s*```$", "", output)

        data = json.loads(output)

        if not isinstance(data, dict):
            raise ValueError(
                "The AI returned an unexpected data format."
            )

        if not isinstance(data.get("line_items"), list):
            data["line_items"] = []

        if not isinstance(data.get("field_confidence"), dict):
            data["field_confidence"] = {}

        if not isinstance(data.get("evidence"), dict):
            data["evidence"] = {}

        # Compatibility with older validation data.
        if data.get("invoice_total") is None:
            data["invoice_total"] = data.get("total_invoice_value")

        data["field_confidence"].setdefault("invoice_total", 0.0)
        data["evidence"].setdefault("invoice_total", None)

        # Do not allow AI confidence to bypass human review.
        data["review_required"] = True
        data["source_document_type"] = document_type

        return data

    except json.JSONDecodeError as error:
        raise ValueError(
            f"The AI response was not valid JSON: {error}"
        ) from error

    except ValueError:
        raise

    except Exception as error:
        raise RuntimeError(
            f"Groq extraction request failed: {error}"
        ) from error
