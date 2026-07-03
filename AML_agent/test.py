import fitz  # PyMuPDF
import os

os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

def read_pdf(file_path):
    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}")
        return

    try:
        doc = fitz.open(file_path)
        print(f"Opened PDF with {doc.page_count} pages.\n")

        for page_num, page in enumerate(doc, start=1):
            print(f"{'=' * 20} Page {page_num} {'=' * 20}")

            # Try extracting embedded text first
            text = page.get_text().strip()

            # If no text exists, perform OCR
            if not text:
                print("[No embedded text found. Running OCR...]")

                try:
                    tp = page.get_textpage_ocr(
                        language="eng",
                        dpi=300
                    )
                    text = page.get_text(textpage=tp).strip()
                except Exception as e:
                    print(f"OCR failed: {e}")
                    text = ""

            if text:
                print(text)
            else:
                print("[No text found on this page]")

            print()

        doc.close()

    except Exception as e:
        print(f"Failed to read PDF: {e}")


if __name__ == "__main__":
    file_path = input("Enter the PDF file path: ").strip()

    # Remove surrounding quotes
    file_path = file_path.strip('"').strip("'")

    read_pdf(file_path)