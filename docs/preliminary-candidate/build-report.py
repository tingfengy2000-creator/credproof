"""Build candidate report from retained official template and reviewed Markdown.

Requires python-docx from the bundled runtime. Does not run models or candidates.
Real assets are optional during drafting and must be supplied before final QA.
Convert via export-report.ps1, then render/inspect the exported PDF separately.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
TITLE = "密证 CredProof——面向 AI 工具的凭据泄露验证与受控修复系统"


def font(run, name="宋体", size=12, bold=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    if bold is not None:
        run.bold = bold
    rp = run._r.get_or_add_rPr()
    rf = rp.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rp.insert(0, rf)
    for role in ("ascii", "hAnsi", "eastAsia", "cs"):
        rf.set(qn("w:" + role), name)


def inline(paragraph, text):
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    parts = re.split(r"(\*\*.*?\*\*|`[^`]+`)", text)
    for part in parts:
        if not part:
            continue
        isbold = part.startswith("**") and part.endswith("**")
        if isbold:
            part = part[2:-2]
        elif part.startswith("`") and part.endswith("`"):
            part = part[1:-1]
        font(paragraph.add_run(part), bold=isbold)


def format_paragraph(p, *, indent=True):
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(3)
    pf.first_line_indent = Pt(24) if indent else Pt(0)
    pf.widow_control = True
    for r in p.runs:
        font(r)


def heading(doc, title, level=1):
    style_name = f"Heading {level}"
    if style_name not in doc.styles:
        style = doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
        style.base_style = doc.styles["Normal"]
        outline = OxmlElement("w:outlineLvl")
        outline.set(qn("w:val"), str(level - 1))
        style._element.get_or_add_pPr().append(outline)
    p = doc.add_paragraph(style=style_name)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(8 if level == 1 else 6)
    p.paragraph_format.space_after = Pt(5 if level == 1 else 3)
    p.paragraph_format.line_spacing = 1.5
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    font(p.add_run(title), "黑体", 16 if level == 1 else 14, True)
    return p


def field(p, instruction):
    begin, code, end = OxmlElement("w:fldChar"), OxmlElement("w:instrText"), OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    code.set(qn("xml:space"), "preserve")
    code.text = " " + instruction + " "
    end.set(qn("w:fldCharType"), "end")
    for el in (begin, code, end):
        r = p.add_run()
        font(r)
        r._r.append(el)


def add_figure(doc, path, caption, width=15.2):
    if path is None:
        return
    path = path.resolve(strict=True)
    p = doc.add_paragraph()
    format_paragraph(p, indent=False)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width))
    c = doc.add_paragraph()
    format_paragraph(c, indent=False)
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    inline(c, caption)


def table(doc, lines):
    rows = [[v.strip() for v in x.strip().strip("|").split("|")] for x in lines]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    if rows[0][0] == "方法":
        rows[0] = ["方法", "问题修复", "正常通过", "对象通过", "任务完成", "误修改"]
        labels = ["A 固定程序", "B 一次生成", "C 反馈模型"]
        for row, label in zip(rows[1:], labels):
            row[0] = label
    t = doc.add_table(rows=1, cols=len(rows[0]))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    widths = [3.05] + [2.5] * (len(rows[0]) - 1)
    if len(rows[0]) == 3:
        widths = [3.5, 6.7, 5.1]
    for column, width in zip(t.columns, widths):
        column.width = Cm(width)
    for i, vals in enumerate(rows):
        cells = t.rows[0].cells if i == 0 else t.add_row().cells
        for j, value in enumerate(vals):
            cells[j].width = Cm(widths[j])
            cells[j].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cells[j].paragraphs[0]
            format_paragraph(p, indent=False)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.keep_with_next = i < len(rows) - 1
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            inline(p, value)
            if i == 0:
                for r in p.runs:
                    r.bold = True
        trpr = t.rows[i]._tr.get_or_add_trPr()
        trpr.append(OxmlElement("w:cantSplit"))
        if i == 0:
            trpr.append(OxmlElement("w:tblHeader"))
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement("w:" + edge)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D9D9D9")
        borders.append(el)
    t._tbl.tblPr.append(borders)


def build(args):
    reference = HERE / "assets/official-template.docx"
    doc = Document(reference)
    # Keep real template cover + instructions; replace only downstream slots.
    paragraphs = list(doc.paragraphs)
    for p in paragraphs[27:]:
        p._p.getparent().remove(p._p)
    for i, value in [(12, "作品名称：" + TITLE), (14, "提交日期：待填")]:
        p = paragraphs[i]
        p.clear()
        if i == 12:
            # Preserve the official field and full name; make the brand and
            # descriptor deliberate lines instead of an accidental short tail.
            value = value.replace("CredProof——", "CredProof——\n", 1)
        font(p.add_run(value), "黑体", 16, True)
        p.paragraph_format.line_spacing = 1.5
    for p in paragraphs[17:22]:
        format_paragraph(p, indent=False)

    # Template-wide typography follows its written requirements, not its old
    # 10.5pt fallback style. Preserve all unrelated package styles/components.
    for name in ("Normal", "toc 1", "toc 2", "toc 3"):
        if name not in doc.styles:
            continue
        s = doc.styles[name]
        s.font.name = "宋体"
        s.font.size = Pt(12)
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.paragraph_format.line_spacing = 1.5
        s.paragraph_format.space_after = Pt(0)
        rf = s._element.get_or_add_rPr().get_or_add_rFonts()
        for role in ("ascii", "hAnsi", "eastAsia", "cs"):
            rf.set(qn("w:" + role), "宋体")
    if "Title" not in doc.styles:
        doc.styles.add_style("Title", WD_STYLE_TYPE.PARAGRAPH)
    doc.styles["Title"].font.name = "黑体"
    doc.styles["Title"].font.size = Pt(26)
    doc.styles["Title"].font.color.rgb = RGBColor(0, 0, 0)
    paragraphs[4].style = doc.styles["Title"]

    # Reset the template's fixed seven-page footer and section page restart.
    for section in doc.sections:
        for el in list(section._sectPr.findall(qn("w:pgNumType"))):
            section._sectPr.remove(el)
    section = doc.sections[-1]
    section.footer.is_linked_to_previous = False
    for p in list(section.footer.paragraphs):
        p.clear()
    foot = section.footer.paragraphs[0]
    format_paragraph(foot, indent=False)
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    inline(foot, "第 ")
    field(foot, "PAGE")
    inline(foot, " 页 共 ")
    field(foot, "NUMPAGES")
    inline(foot, " 页")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(p.add_run("目录"), "黑体", 16, True)
    p.paragraph_format.space_after = Pt(10)
    toc = doc.add_paragraph()
    format_paragraph(toc, indent=False)
    field(toc, 'TOC \\o "1-1" \\h \\z \\u')

    manuscript = (HERE / "manuscript.md").read_text(encoding="utf-8")
    body = manuscript.split("## 摘要\n", 1)[1]
    heading(doc, "摘要")
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("## 第一章"):
            doc.add_page_break()
        if line.startswith("### 2.2"):
            add_figure(doc, args.mechanism, "图 1 运行证据约束下的候选修复与验收流程")
        if line.startswith("### 2.4"):
            add_figure(doc, args.overview, "图 2 真实工作台中的证据与独立任务状态")
        if line.startswith("### 3.5"):
            number = 3 if args.overview else 2
            add_figure(doc, args.trace, f"图 {number} h03 两次候选与真实验证反馈 历史记录回放")
        if line.startswith("### 3.8"):
            add_figure(doc, args.recheck, "图 4 当前对象的实际复检记录 不调用模型")
        if line.startswith("## "):
            heading(doc, line[3:], 1)
        elif line.startswith("### "):
            section_heading = heading(doc, line[4:], 2)
        elif line.startswith("|"):
            group = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                group.append(lines[i])
                i += 1
            table(doc, group)
            continue
        else:
            p = doc.add_paragraph()
            format_paragraph(p, indent=not line.startswith(("关键词", "[")))
            if line.startswith("["):
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            inline(p, line)
        i += 1

    doc.core_properties.title = TITLE
    doc.core_properties.subject = "中国研究生网络安全创新大赛 创意作品赛"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.comments = ""
    doc.core_properties.keywords = "运行时凭据 本地智能体 受控修复"
    settings = doc.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    receipt = {"source": str(reference), "source_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
               "manuscript_sha256": hashlib.sha256((HERE / "manuscript.md").read_bytes()).hexdigest(),
               "output": str(args.output), "assets": {key: str(getattr(args, key)) if getattr(args, key) else None for key in ("mechanism", "overview", "trace")},
               "historical_result_run": "20260929t095000z-holdout8", "presentation_version": "0.2.0-preliminary.4", "not_final_render_qa": True}
    (HERE / "working").mkdir(exist_ok=True)
    (HERE / "working/build-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "credproof-manuscript-candidate.docx")
    parser.add_argument("--mechanism", type=Path)
    parser.add_argument("--overview", type=Path)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--recheck", type=Path)
    build(parser.parse_args())
