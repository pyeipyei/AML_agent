from pathlib import Path
import fitz 
import os
import fitz 
from typing import Optional
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

ALLOWED_KEYWORDS = [
    "ssm",
    "annual return",
    "audited financial statements",
    "ar",
    "afs",
]

os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

def pre_filter_documents(pdf_path: str | Path) -> str | None:
    pdf_path = Path(pdf_path)

    filename = pdf_path.stem.lower()

    for keyword in ALLOWED_KEYWORDS:
        if keyword in filename:
            return keyword

    try:
        with fitz.open(pdf_path) as doc:
            if len(doc) == 0:
                return None

            first_page_text = doc[0].get_text().lower()

        for keyword in ALLOWED_KEYWORDS:
            if keyword in first_page_text:
                return keyword

    except Exception as e:
        print(f"Failed to inspect {pdf_path}: {e}")

    return None

#---------------------------------------------------------

def read_pdf(file_path: str) -> str:
    if not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"

    try:
        doc = fitz.open(file_path)

        all_text = []

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text().strip()

            if not text:
                try:
                    tp = page.get_textpage_ocr(
                        language="eng",
                        dpi=300
                    )
                    text = page.get_text(textpage=tp).strip()
                except Exception as e:
                    text = f"[OCR failed: {e}]"

            all_text.append(
                f"===== Page {page_num} =====\n{text}\n"
            )

        doc.close()

        return "\n".join(all_text)

    except Exception as e:
        return f"Failed to read PDF: {e}"

#-------------------------------------------------------------------
