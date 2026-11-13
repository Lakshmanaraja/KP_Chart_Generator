"""Shared, measured inline lead-ins for phone and A4 insight cards."""
from html import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# DejaVu ships on most Linux hosts; Docker installs it explicitly.
FONT = "Helvetica"
for root in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu"):
    regular = os.path.join(root, "DejaVuSans.ttf")
    bold = os.path.join(root, "DejaVuSans-Bold.ttf")
    if os.path.exists(regular) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("InsightSans", regular))
        pdfmetrics.registerFont(TTFont("InsightSans-Bold", bold))
        pdfmetrics.registerFontFamily("InsightSans", normal="InsightSans", bold="InsightSans-Bold")
        FONT = "InsightSans"
        break


def insight_paragraph(trait, pt, color):
    title = str(trait.get("summary_title") or "").strip().rstrip(": ")
    lead = f"<b>{escape(title)}:</b> " if title else ""
    body = escape(str(trait.get("text") or "")).replace("\n", "<br/>")
    return Paragraph(lead + body, ParagraphStyle(
        "insight", fontName=FONT, fontSize=pt, leading=pt * 1.5,
        textColor=color, spaceBefore=0, spaceAfter=0,
    ))


def insight_height(trait, pt, width, color):
    return insight_paragraph(trait, pt, color).wrap(width, 100000)[1]


def draw_insight(c, trait, x, top, page_height, width, pt, color):
    paragraph = insight_paragraph(trait, pt, color)
    _, height = paragraph.wrap(width, 100000)
    paragraph.drawOn(c, x, page_height - top - height)
    return height