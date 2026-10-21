"""Convert a demo guide to .docx (emoji legend replaced by text for Word).

    python docs/build_demo_docx.py                       # docs/demo_guide.md -> docs/demo_guide.docx
    python docs/build_demo_docx.py docs/Review_3_Demo_Guide  # Review 3 guide
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_reports as b

base = sys.argv[1] if len(sys.argv) > 1 else "docs/demo_guide"
text = open(base + ".md", encoding="utf-8").read()
text = text.replace("🔌", "[LIVE ORACLE]").replace("📄", "[NO DB NEEDED]")
b.build_docx(b.parse(text), base + ".docx")
print(base + ".docx", os.path.getsize(base + ".docx"), "bytes")
