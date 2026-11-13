"""Shared, measured inline lead-ins for phone and A4 insight cards.

Uses the same standard Helvetica font family as the legend, cover and other
report pages, with Helvetica-Bold for inline titles and Helvetica for body text.
"""
from html import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

FONT = "Helvetica"


def insight_paragraph(trait, pt, color):
    title = str(trait.get("summary_title") or "").strip().rstrip(": ")
    lead = f"<b>{escape(title)}:</b> " if title else ""
    body = escape(str(trait.get("text") or "")).replace("\n", "<br/>")
    return Paragraph(lead + body, ParagraphStyle(
        "insight",
        fontName=FONT,
        fontSize=pt,
        leading=pt * 1.5,
        textColor=color,
        spaceBefore=0,
        spaceAfter=0,
    ))


def insight_height(trait, pt, width, color):
    return insight_paragraph(trait, pt, color).wrap(width, 100000)[1]


def draw_insight(c, trait, x, top, page_height, width, pt, color):
    paragraph = insight_paragraph(trait, pt, color)
    _, height = paragraph.wrap(width, 100000)
    paragraph.drawOn(c, x, page_height - top - height)
    return height
