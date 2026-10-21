"""Regenerate the test matrix inside Review_2_Report.md, then build the DOCX and PDF.

    python -m pytest tests --junitxml=docs/test_results.xml
    python docs/build_reports.py

The matrix is built ONLY from the junit result file, so it shows what really ran.
"""
import importlib
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
MD, XML = "docs/Review_2_Report.md", "docs/test_results.xml"
PREFIX = {"test_config": "CFG", "test_services": "SVC", "test_routes": "RTE", "test_oracle_integration": "INT"}
REMARK = {"CFG": "Pure logic", "SVC": "Fake DB connection - proves SQL/transaction logic, not Oracle behaviour",
          "RTE": "Services stubbed; Flask test client", "INT": "Live Oracle 21c XE, separate test schema (student run 2026-10-22)"}
RANK = {"FAILED": 3, "BLOCKED": 2, "NOT RUN": 1, "PASSED": 0}


def collect():
    groups = OrderedDict()
    for case in ET.parse(XML).getroot().iter("testcase"):
        module = case.get("classname").split(".")[-1]
        base = re.sub(r"\[.*\]$", "", case.get("name"))
        status, actual = "PASSED", "Executed; assertions held"
        for child in case:
            if child.tag in ("failure", "error"):
                status, actual = "FAILED", (child.get("message") or "failed").splitlines()[0][:120]
            elif child.tag == "skipped":
                reason = child.get("message") or ""
                status = "BLOCKED" if reason.startswith("BLOCKED") else "NOT RUN"
                actual = "Not executed: no Oracle instance available" if status == "BLOCKED" else reason
        key = (module, base)
        old = groups.get(key)
        if old is None:
            groups[key] = [status, actual, 1]
        else:
            old[2] += 1
            if RANK[status] > RANK[old[0]]:
                old[0], old[1] = status, actual
    return groups


ORDER = ['test_config', 'test_services', 'test_routes', 'test_oracle_integration']


def matrix_md():
    rows = ["| ID | Test description | Expected outcome | Actual outcome | Status | Remarks |", "|---|---|---|---|---|---|"]
    counters, totals = {}, {}
    for (module, name), (status, actual, n) in sorted(collect().items(), key=lambda kv: ORDER.index(kv[0][0])):
        p = PREFIX[module]
        counters[p] = counters.get(p, 0) + 1
        doc = (getattr(importlib.import_module("tests." + module), name).__doc__ or name).strip()
        what, _, expected = doc.partition(" | ")
        extra = f" ({n} parameter sets)" if n > 1 else ""
        rows.append(f"| {p}-{counters[p]:02d} | {what.replace('|', '/')}{extra} | {expected.replace('|', '/') or what} | "
                    f"{actual.replace('|', '/')} | **{status}** | {REMARK[p]} |")
        totals[status] = totals.get(status, 0) + n
    summary = "Totals by pytest case: " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items()))
    return "\n".join(rows) + "\n\n" + summary


def refresh_markdown():
    text = open(MD, encoding="utf-8").read()
    new = "<!-- MATRIX:START -->\n" + matrix_md() + "\n<!-- MATRIX:END -->"
    text = re.sub(r"<!-- MATRIX:START -->.*?<!-- MATRIX:END -->", lambda _: new, text, flags=re.S)
    open(MD, "w", encoding="utf-8").write(text)
    return text


# ------------------------------------------------------------------ tiny markdown parser
def parse(text):
    """Blocks: ('h', level, text) ('p', text) ('code', text) ('ul', [..]) ('table', rows) ('pb',)"""
    lines, i, out = text.splitlines(), 0, []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            if ln.strip() != "```mermaid":          # diagram image replaces the Mermaid source
                out.append(("code", "\n".join(lines[i + 1:j])))
            i = j + 1
        elif re.match(r"!\[[^\]]*\]\([^)]+\)\s*$", ln):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", ln)
            out.append(("img", m.group(1), m.group(2)))
            i += 1
        elif ln.startswith("<!--") or not ln.strip():
            i += 1
        elif ln.strip() == "\\newpage":
            out.append(("pb",))
            i += 1
        elif re.match(r"#{1,4} ", ln):
            level = len(ln) - len(ln.lstrip("#"))
            out.append(("h", level, ln[level:].strip()))
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
        elif re.match(r"\s*([-*]|\d+\.) ", ln):
            items = []
            while i < len(lines) and re.match(r"\s*([-*]|\d+\.) ", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                i += 1
            out.append(("ul", items))
        else:
            para = [ln.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||```|!\[|\s*([-*]|\d+\.) |<!--)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(("p", " ".join(para)))
    return out


def plain(s):
    return re.sub(r"[*`]", "", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s))


# ------------------------------------------------------------------ DOCX
def build_docx(blocks, out="docs/Review_2_Report.docx"):
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)
    footer = doc.sections[0].footer.paragraphs[0]
    footer.text = "Electronic Appliance Store Management System - DBMS Review 2 - Page "
    run = footer.add_run()
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        el = OxmlElement("w:fldChar" if kind else "w:instrText")
        if kind:
            el.set(qn("w:fldCharType"), kind)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        run._r.append(el)

    def rich(par, s):
        for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)):
            if part.startswith("**"):
                par.add_run(part[2:-2]).bold = True
            elif part.startswith("`") and len(part) > 1:
                par.add_run(part[1:-1]).font.name = "Consolas"
            else:
                par.add_run(part)

    first_h1 = True
    for b in blocks:
        if b[0] == "h":
            first_h1 = False
            doc.add_heading(plain(b[2]), 0 if b[1] == 1 else min(b[1] - 1, 3))
        elif b[0] == "p":
            rich(doc.add_paragraph(), b[1])
        elif b[0] == "code":
            r = doc.add_paragraph().add_run(b[1])
            r.font.name, r.font.size = "Consolas", Pt(7.5)
        elif b[0] == "ul":
            for item in b[1]:
                rich(doc.add_paragraph(style="List Bullet"), item)
        elif b[0] == "pb":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif b[0] == "img":
            doc.add_picture(os.path.join("docs", b[2]), width=Inches(6.2))
            cap = doc.add_paragraph(b[1])
            cap.runs[0].italic = True
            cap.runs[0].font.size = Pt(9)
        elif b[0] == "table":
            rows = b[1]
            n = len(rows[0])
            t = doc.add_table(rows=len(rows), cols=n)
            t.style = "Table Grid"
            for ri, row in enumerate(rows):
                for ci, text in enumerate((row + [""] * n)[:n]):
                    par = t.cell(ri, ci).paragraphs[0]
                    rich(par, text)
                    for r in par.runs:
                        r.font.size = Pt(8)
                        r.bold = bool(r.bold) or ri == 0
            doc.add_paragraph()
    doc.save(out)


# ------------------------------------------------------------------ PDF
def build_pdf(blocks):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10, leading=13)
    cell = ParagraphStyle("c", parent=body, fontSize=7.5, leading=9)
    code = ParagraphStyle("code", fontName="Courier", fontSize=7, leading=8.5, backColor=colors.whitesmoke, leftIndent=3)
    heads = {1: ss["Heading1"], 2: ss["Heading2"], 3: ss["Heading3"], 4: ss["Heading4"]}

    def rich(s):
        s = escape(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s))
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        return re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", s)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(15 * mm, 8 * mm, "Electronic Appliance Store Management System - DBMS Review 2")
        canvas.drawRightString(doc.pagesize[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    story, width, first_h1 = [], A4[0] - 30 * mm, True
    for b in blocks:
        if b[0] == "h":
            first_h1 = False
            story.append(Paragraph(rich(b[2]), heads[min(b[1], 4)]))
        elif b[0] == "p":
            story += [Paragraph(rich(b[1]), body), Spacer(1, 3)]
        elif b[0] == "code":
            story += [Preformatted("\n".join(l[:125] for l in b[1].splitlines()), code), Spacer(1, 4)]
        elif b[0] == "ul":
            story += [Paragraph("&bull; " + rich(item), body) for item in b[1]] + [Spacer(1, 3)]
        elif b[0] == "pb":
            story.append(PageBreak())
        elif b[0] == "img":
            from PIL import Image as PILImage
            path = os.path.join("docs", b[2])
            w, h = PILImage.open(path).size
            scale = min(width / w, 215 * mm / h)
            story.append(KeepTogether([Image(path, w * scale, h * scale),
                                       Paragraph("<i>%s</i>" % escape(b[1]), cell), Spacer(1, 6)]))
        elif b[0] == "table":
            rows, n = b[1], len(b[1][0])
            data = [[Paragraph(rich(c), cell) for c in (r + [""] * n)[:n]] for r in rows]
            weights = [max(10, min(48, max(len(plain(r[c])) if c < len(r) else 0 for r in rows))) ** 0.7 for c in range(n)]
            t = Table(data, colWidths=[width * w / sum(weights) for w in weights], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [t, Spacer(1, 6)]
    SimpleDocTemplate("docs/Review_2_Report.pdf", pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                      topMargin=15 * mm, bottomMargin=15 * mm, author="Sanjiv Shine Fernandas",
                      title="Electronic Appliance Store Management System - Review 2"
                      ).build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    blocks = parse(refresh_markdown())
    build_docx(blocks)
    build_pdf(blocks)
    for ext in ("md", "docx", "pdf"):
        path = f"docs/Review_2_Report.{ext}"
        print(path, os.path.getsize(path), "bytes")
