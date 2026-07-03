#!/usr/bin/env bash
set -euo pipefail

echo "Installing system dependencies for AML Agent..."

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y tesseract tesseract-langpack-eng
elif command -v brew >/dev/null 2>&1; then
  brew install tesseract
else
  echo "Unsupported package manager."
  echo "Install Tesseract OCR manually: https://github.com/tesseract-ocr/tesseract"
  exit 1
fi

if command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract installed: $(tesseract --version 2>&1 | head -n 1)"
else
  echo "Tesseract install finished but binary not found on PATH."
  exit 1
fi
