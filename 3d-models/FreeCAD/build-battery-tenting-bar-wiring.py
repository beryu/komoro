#!/usr/bin/env python3
"""Build the wiring manual PDF from Markdown and its versioned diagrams.

Requires reportlab. Pass --font to select a Japanese TrueType font when the
macOS Arial Unicode font is unavailable. Output defaults to output/pdf/.
The SVG reader supports only the shapes used by this manual's three diagrams.
"""

import argparse
import html
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from reportlab.graphics.shapes import Circle, Drawing, Group, Path as SvgPath
from reportlab.graphics.shapes import Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus import Table, TableStyle


HERE = Path(__file__).resolve().parent
NUMBER = r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"


def svg_color(value):
    if value == "none":
        return None
    if value.startswith("rgb("):
        parts = value[4:-1].split(",")
        return colors.Color(*(float(p.strip().rstrip("%")) /
                              (100 if "%" in p else 255) for p in parts))
    return colors.toColor(value)


def read_diagram(path):
    root = ET.parse(path).getroot()
    width, height = float(root.get("width")), float(root.get("height"))
    drawing = Drawing(width, height)
    wrapper = Group()
    wrapper.transform = (1, 0, 0, -1, 0, height)

    def visit(node):
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in {"title", "desc", "clipPath"}:
            return None
        style = dict(part.strip().split(":", 1) for part in
                     node.get("style", "").split(";") if ":" in part)
        def number(key, default=0):
            return float(node.get(key, default))
        shape_style = dict(
            fillColor=svg_color(style.get("fill", node.get("fill", "black"))),
            strokeColor=svg_color(style.get("stroke", node.get("stroke", "none"))),
            strokeWidth=float(style.get("stroke-width", "1")),
        )
        if "stroke-dasharray" in style:
            shape_style["strokeDashArray"] = [float(p) for p in
                                                re.findall(NUMBER, style["stroke-dasharray"])]
        if tag in {"g", "svg"}:
            obj = Group()
            for child in node:
                item = visit(child)
                if item is not None:
                    obj.add(item)
        elif tag == "rect":
            obj = Rect(number("x"), number("y"), number("width"), number("height"),
                       rx=number("rx"), ry=number("ry"), **shape_style)
        elif tag == "circle":
            obj = Circle(number("cx"), number("cy"), number("r"), **shape_style)
        elif tag == "polygon":
            obj = Polygon([float(p) for p in re.findall(NUMBER, node.get("points"))],
                          **shape_style)
        elif tag == "path":
            tokens = re.findall(r"[A-Za-z]|" + NUMBER, node.get("d"))
            obj = SvgPath(**shape_style)
            while tokens:
                command = tokens.pop(0)
                if command in {"M", "L"}:
                    x, y = float(tokens.pop(0)), float(tokens.pop(0))
                    (obj.moveTo if command == "M" else obj.lineTo)(x, y)
                elif command in {"Z", "z"}:
                    obj.closePath()
                else:
                    raise ValueError(f"Unsupported diagram path command: {command}")
        elif tag == "text":
            obj = Group()
            y = number("y")
            obj.transform = (1, 0, 0, -1, 0, 2*y)
            obj.add(String(number("x"), y, "".join(node.itertext()), fontName="JP",
                           fontSize=float(style.get("font-size", "10px").removesuffix("px")),
                           fillColor=shape_style["fillColor"]))
        else:
            raise ValueError(f"Unsupported SVG shape: {tag}")
        transformed = Group()
        for command, arguments in re.findall(r"([A-Za-z]+)\(([^)]*)\)", node.get("transform", "")):
            args = [float(v) for v in re.findall(NUMBER, arguments)]
            if command == "scale":
                transformed.scale(args[0], args[1] if len(args)>1 else args[0])
            elif command == "translate":
                transformed.translate(args[0], args[1] if len(args)>1 else 0)
            else:
                raise ValueError(f"Unsupported SVG transform: {command}")
        transformed.add(obj)
        return transformed

    wrapper.add(visit(root))
    drawing.add(wrapper)
    factor = min(1, 495/width)
    drawing.scale(factor, factor)
    drawing.width *= factor
    drawing.height *= factor
    return drawing


def markup(text):
    parts, end = [], 0
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(html.escape(text[end:match.start()]))
        label, target = match.groups()
        if target.startswith(("https://", "http://")):
            parts.append(f'<link href="{html.escape(target, quote=True)}" color="#177C9B">'
                         f'{html.escape(label)}</link>')
        else:
            parts.append(html.escape(label) + "（リポジトリ内）")
        end = match.end()
    parts.append(html.escape(text[end:]))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", "".join(parts))


def build(font, output):
    pdfmetrics.registerFont(TTFont("JP", str(font)))
    common = dict(fontName="JP", wordWrap="CJK", textColor=colors.HexColor("#233644"))
    styles = {
        "body": ParagraphStyle("body", fontSize=9.2, leading=13.2, spaceAfter=5, **common),
        "title": ParagraphStyle("title", fontSize=22, leading=28, spaceAfter=12, **common),
        "h2": ParagraphStyle("h2", fontSize=15, leading=21, spaceBefore=8, spaceAfter=10, keepWithNext=True, **common),
        "h3": ParagraphStyle("h3", fontSize=11.5, leading=16, spaceBefore=7, spaceAfter=6, keepWithNext=True, **common),
        "table": ParagraphStyle("table", fontSize=8.4, leading=11.8, **common),
        "list": ParagraphStyle("list", fontSize=9.2, leading=13.2, spaceAfter=3,
                               leftIndent=14, firstLineIndent=-14, **common),
    }
    lines = (HERE/"BATTERY-TENTING-BAR-WIRING.md").read_text().splitlines()
    story, i = [], 0
    page_sections = {"1", "2", "3", "5", "6", "8", "9", "10", "11", "12"}
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        if line.startswith("# "):
            story.append(Paragraph(markup(line[2:]), styles["title"]))
        elif line.startswith("### "):
            if line[4:] in {"検査基板の測定用線を準備する", "ケース外での追加測定"}:
                story.append(PageBreak())
            story.append(Paragraph(markup(line[4:]), styles["h3"]))
        elif line.startswith("## "):
            if line.split()[1].split(".")[0] in page_sections:
                story.append(PageBreak())
            story.append(Paragraph(markup(line[3:]), styles["h2"]))
        elif line.startswith("!["):
            path = HERE/re.search(r"\]\(([^)]+)\)", line).group(1)
            if path.suffix == ".svg":
                story.append(read_diagram(path))
            else:
                width, height = ImageReader(str(path)).getSize()
                story.append(Image(str(path), width=495, height=495*height/width))
            story.append(Spacer(1, 12))
        elif line.startswith("|"):
            rows = [line]
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            data = []
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                if all(re.fullmatch(r"[-:]+", c) for c in cells):
                    continue
                data.append([Paragraph(markup(c), styles["table"]) for c in cells])
            n = len(data[0])
            widths = {2: [192,303], 3: [70,165,260], 4: [35,139,139,182]}[n]
            if "端子番号" in rows[0]:
                widths = [70,55,370]
            table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E2EEF3")),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F6F8FA")]),
                ("LINEBELOW", (0,0), (-1,0), .8, colors.HexColor("#A0B5C1")),
                ("LINEBELOW", (0,1), (-1,-1), .3, colors.HexColor("#D6E0E6")),
                ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            story.extend([table, Spacer(1,10)])
        elif re.match(r"^\d+\. ", line) or line.startswith("- "):
            story.append(Paragraph(markup("・"+line[2:] if line.startswith("- ") else line), styles["list"]))
        else:
            paragraph = [line]
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||!\[|\d+\. |[-] )", lines[i]):
                paragraph.append(lines[i]); i += 1
            story.append(Paragraph(markup("".join(paragraph)), styles["body"]))

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#CFDCE3")); canvas.line(50,43,545,43)
        canvas.setFont("JP",8); canvas.setFillColor(colors.HexColor("#647782"))
        canvas.drawString(50,29,"komoro / USBケーブル加工・配線手順書 / Rev J")
        canvas.drawRightString(545,29,f"2026-10-18  |  {doc.page}")

    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(output), pagesize=(595.276,841.89), leftMargin=42,
                                 rightMargin=42, topMargin=36, bottomMargin=57,
                                 title="komoro USBケーブル加工・配線手順書", author="komoro project")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("/Library/Fonts/Arial Unicode.ttf"))
    parser.add_argument("--output", type=Path, default=HERE.parents[1]/"output/pdf/battery-tenting-bar-wiring.pdf")
    args = parser.parse_args()
    build(args.font, args.output)
