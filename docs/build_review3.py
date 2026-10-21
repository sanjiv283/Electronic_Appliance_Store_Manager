"""Build docs/Review_3_Report.{docx,pdf} from Review_3_Report.md (matrix from docs/test_results_r3.xml).

    python docs/build_review3.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_reports as br

br.MD, br.XML = "docs/Review_3_Report.md", "docs/test_results_r3.xml"
br.LABEL, br.PDF_OUT = "DBMS Review 3", "docs/Review_3_Report.pdf"
blocks = br.parse(br.refresh_markdown())
br.build_docx(blocks, out="docs/Review_3_Report.docx")
br.build_pdf(blocks)
for ext in ("md", "docx", "pdf"):
    path = f"docs/Review_3_Report.{ext}"
    print(path, os.path.getsize(path), "bytes")
