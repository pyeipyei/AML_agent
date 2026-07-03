# AML Agent

Multi-agent document processing pipeline for KYC extraction and Artemis screening.

## Setup

### Python dependencies

```bash
uv sync
```

### System dependencies (Tesseract OCR)

Scanned PDFs without embedded text require [Tesseract OCR](https://github.com/tesseract-ocr/tesseract). PyMuPDF calls the `tesseract` binary at runtime; it is not installed via `pip`.

**Linux (Debian/Ubuntu):**

```bash
./scripts/install_system_deps.sh
```

Or manually:

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

**macOS:**

```bash
brew install tesseract
```

**Windows:**

Install from [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki) and ensure `tesseract` is on your `PATH`.

The app auto-detects `TESSDATA_PREFIX` on Linux, macOS, and Windows when possible.

### Run the UI

```bash
cd AML_agent
streamlit run app.py
```
