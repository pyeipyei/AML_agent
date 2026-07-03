from pathlib import Path
import os
import shutil
import sys
from typing import Optional

import pymupdf as fitz

ALLOWED_KEYWORDS = [
    "ssm",
    "annual return",
    "audited financial statements",
    "ar",
    "afs",
]

_TESSDATA_CANDIDATES = [
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
    "/usr/local/share/tessdata",
    "/opt/homebrew/share/tessdata",
    "/usr/local/share/tessdata",
    r"C:\Program Files\Tesseract-OCR\tessdata",
    r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
]


def _find_tessdata_dir() -> str | None:
    for path in _TESSDATA_CANDIDATES:
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "eng.traineddata")):
            return path
    return None


def configure_tesseract() -> None:
    """Set TESSDATA_PREFIX when Tesseract language data can be located."""
    if os.environ.get("TESSDATA_PREFIX"):
        return

    tessdata_dir = _find_tessdata_dir()
    if tessdata_dir:
        os.environ["TESSDATA_PREFIX"] = tessdata_dir


def is_ocr_available() -> bool:
    configure_tesseract()
    return shutil.which("tesseract") is not None and _find_tessdata_dir() is not None


def ocr_unavailable_message() -> str:
    if shutil.which("tesseract") is None:
        return (
            "Tesseract OCR is not installed. Install it with "
            "`./scripts/install_system_deps.sh` or your system package manager."
        )
    if _find_tessdata_dir() is None:
        return (
            "Tesseract language data was not found. Install English data with "
            "`tesseract-ocr-eng` (Linux) or reinstall Tesseract (Windows/macOS)."
        )
    return "Tesseract OCR is not configured."


configure_tesseract()

_SSM_BOILERPLATE_MARKERS = (
    "This company information is generated from MYDATA SSM Services",
    "MENARA SSM@SENTRAL",
    "Printing Date:",
)


def _strip_ssm_boilerplate(text: str) -> str:
    cleaned = text
    for marker in _SSM_BOILERPLATE_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip()


_CONTENT_MARKERS = (
    "company no",
    "director",
    "shareholder",
    "registration",
    "section a",
    "annual return",
    "particulars of company",
    "sdn. bhd",
)


def _needs_ocr(page: fitz.Page, embedded_text: str) -> bool:
    if not embedded_text.strip():
        return True

    lower = embedded_text.lower()
    if any(marker in lower for marker in _CONTENT_MARKERS):
        return False

    if page.get_images(full=True):
        return True

    substantive = _strip_ssm_boilerplate(embedded_text)
    return len(substantive) < 250


def _ocr_page_text(page: fitz.Page) -> str:
    tp = page.get_textpage_ocr(language="eng", dpi=300)
    return page.get_text(textpage=tp).strip()


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

            if _needs_ocr(page, text):
                if not is_ocr_available():
                    if not text:
                        text = f"[OCR unavailable: {ocr_unavailable_message()}]"
                else:
                    try:
                        ocr_text = _ocr_page_text(page)
                        if len(ocr_text) > len(text):
                            text = ocr_text
                    except Exception as e:
                        if not text:
                            text = f"[OCR failed: {e}]"

            all_text.append(
                f"===== Page {page_num} =====\n{text}\n"
            )

        doc.close()

        return "\n".join(all_text)

    except Exception as e:
        return f"Failed to read PDF: {e}"

#-------------------------------------------------------------------
