"""Convert docs/demo_guide.md to docs/demo_guide.docx (emoji legend replaced by text for Word)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_reports as b

text = open("docs/demo_guide.md", encoding="utf-8").read()
text = text.replace("🔌", "[LIVE ORACLE]").replace("📄", "[NO DB NEEDED]")
b.build_docx(b.parse(text), "docs/demo_guide.docx")
print("docs/demo_guide.docx", os.path.getsize("docs/demo_guide.docx"), "bytes")
