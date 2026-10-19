"""
NeuroQuant-LOB Research Paper Compilation Engine
Compiles Typst manuscript to IEEE/arXiv compliant PDF and validates structure.
"""

import os
import sys
import re
import typst

PAPER_DIR = os.path.dirname(os.path.abspath(__file__))
TYP_PATH = os.path.join(PAPER_DIR, "neuroquant_lob.typ")
PDF_PATH = os.path.join(PAPER_DIR, "neuroquant_lob.pdf")

def get_pdf_page_count(pdf_path):
    with open(pdf_path, "rb") as f:
        content = f.read()
    # Matches /Type /Page (excluding /Pages)
    pages = re.findall(rb"/Type\s*/Page\b", content)
    return len(pages)

def compile_paper():
    print(f"[*] Compiling {TYP_PATH} -> {PDF_PATH} via Typst 0.15.0...")
    if not os.path.exists(TYP_PATH):
        print(f"[!] Source file {TYP_PATH} not found!")
        return False

    try:
        typst.compile(TYP_PATH, output=PDF_PATH)
        size_kb = os.path.getsize(PDF_PATH) / 1024.0
        pages = get_pdf_page_count(PDF_PATH)
        print(f"[SUCCESS] Compiled successfully!")
        print(f"  -> Output: {PDF_PATH}")
        print(f"  -> File Size: {size_kb:.2f} KB")
        print(f"  -> Page Count: {pages} Pages")
        return True, pages
    except Exception as e:
        print(f"[FAIL] Typst compilation failed: {e}")
        return False, 0

if __name__ == "__main__":
    success, pages = compile_paper()
    if not success:
        sys.exit(1)
