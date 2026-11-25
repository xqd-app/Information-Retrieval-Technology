"""Convert the analysis report Markdown into a formatted DOCX."""

import re
import sys
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

SRC = sys.argv[1] if len(sys.argv) > 1 else r"E:\Information Retrieval Technology\全球信息获取分析展现项目-优劣分析报告.md"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"E:\Information Retrieval Technology\全球信息获取分析展现项目-优劣分析报告.docx"

CN_BODY = "等线"
CN_HEAD = "微软雅黑"
ACCENT = RGBColor(0x1F, 0x3B, 0x57)


def set_run_font(run, size=10.5, bold=False, color=None, name=CN_BODY):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = name
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), name)


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(paragraph, text, size=10.5, base_bold=False, color=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            r = paragraph.add_run(part[2:-2])
            set_run_font(r, size, True, color)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = paragraph.add_run(part[1:-1])
            set_run_font(r, size - 1, base_bold, RGBColor(0x7A, 0x2E, 0x1F), "Consolas")
        else:
            r = paragraph.add_run(part)
            set_run_font(r, size, base_bold, color)


def body_para(doc, text, size=10.5, space_after=4, indent=0, bullet=False, color=None):
    p = doc.add_paragraph(style="List Bullet" if bullet else None)
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    pf.line_spacing = 1.25
    if indent:
        pf.left_indent = Cm(0.62 * indent)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_inline(p, text, size, color=color)
    return p


def heading(doc, text, level):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    if level == 1:
        pf.space_before = Pt(16)
        pf.space_after = Pt(8)
        size = 15
    elif level == 2:
        pf.space_before = Pt(12)
        pf.space_after = Pt(5)
        size = 12.5
    else:
        pf.space_before = Pt(9)
        pf.space_after = Pt(4)
        size = 11
    pf.keep_with_next = True
    add_inline(p, text, size, base_bold=True, color=ACCENT)
    return p


def split_row(line):
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def is_divider(cells):
    return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c)


def add_section(doc, landscape):
    new_sec = doc.add_section(WD_SECTION.NEW_PAGE)
    if landscape:
        new_sec.orientation = WD_ORIENT.LANDSCAPE
        new_sec.page_width, new_sec.page_height = Cm(29.7), Cm(21.0)
    else:
        new_sec.orientation = WD_ORIENT.PORTRAIT
        new_sec.page_width, new_sec.page_height = Cm(21.0), Cm(29.7)
    new_sec.left_margin = new_sec.right_margin = Cm(1.6)
    new_sec.top_margin = new_sec.bottom_margin = Cm(1.8)
    return new_sec


def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    el = tr_pr.makeelement(qn("w:tblHeader"), {})
    tr_pr.append(el)


def add_table(doc, rows, font_size=8.5):
    header, body = rows[0], [r for r in rows[1:] if not is_divider(r)]
    wide = len(header) >= 8
    if wide:
        add_section(doc, True)
        font_size = 8
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    repeat_header(table.rows[0])
    hdr = table.rows[0].cells
    for i, text in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(1)
        add_inline(p, text, font_size, base_bold=True)
    for row in body:
        cells = table.add_row().cells
        for i in range(len(header)):
            text = row[i] if i < len(row) else ""
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.1
            add_inline(p, text, font_size)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    if wide:
        add_section(doc, False)


def main():
    with open(SRC, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(1.9)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name = CN_BODY
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CN_BODY)

    # footer with page number
    footer_p = sec.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run("全球信息获取·分析·展现 六项目优劣分析报告  ·  1")
    set_run_font(run, 8, color=RGBColor(0x88, 0x88, 0x88))

    tablebuf = []
    in_code = False
    title_done = False

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            tablebuf.append(split_row(stripped))
            continue
        if tablebuf:
            add_table(doc, tablebuf, 9 if len(tablebuf[0]) <= 4 else 8)
            tablebuf = []

        if not stripped:
            continue
        if set(stripped) <= {"-", "—", "*"} and len(stripped) > 2:
            continue

        if stripped.startswith("> "):
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.5)
            pf.space_after = Pt(3)
            add_inline(p, stripped[2:], 9.5, color=RGBColor(0x55, 0x55, 0x55))
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1 and not title_done:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(6)
                add_inline(p, text, 21, base_bold=True, color=ACCENT)
                title_done = True
            else:
                heading(doc, text, min(level - 1, 3) if title_done else level)
            continue

        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            depth = len(m.group(1)) // 2
            text = re.sub(r"^\[[ xX]\]\s*", "☐ ", m.group(2))
            body_para(doc, text, 10, 3, indent=depth + 1, bullet=True)
            continue

        m = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if m:
            body_para(doc, f"{m.group(2)}. {m.group(3)}", 10, 3, indent=1)
            continue

        body_para(doc, stripped, 10.5 if len(stripped) < 120 else 10, 5)

    if tablebuf:
        add_table(doc, tablebuf, 8)

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    sys.exit(main())
