
import fitz
from pathlib import Path

pdf_path = Path("uploads/Invoice.pdf")

pdf = fitz.open(pdf_path)

for page_number, page in enumerate(pdf, start=1):
    print(f"\n========== PAGE {page_number} ==========\n")
    print(page.get_text("text"))

pdf.close()
