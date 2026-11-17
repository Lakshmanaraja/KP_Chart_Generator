"""Shared, measured inline lead-ins for phone and A4 insight cards.

Uses the same standard Helvetica font family as the legend, cover and other
report pages, with Helvetica-Bold for inline titles and Helvetica for body text.
"""
from html import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

FONT = "Helvetica"


from reportlab.lib import colors
from reportlab.lib.units import mm

BOX_BG = colors.HexColor("#FFF7E6")
BOX_BORDER = colors.HexColor("#F5DFAE")
BOX_ACCENT = colors.HexColor("#B7791F")
BOX_TEXT = colors.HexColor("#3D3523")
BOX_HEAD = "How You Can Help"
BOX_GAP, BOX_PAD, BOX_HEAD_GAP = 2.6 * mm, 3 * mm, 1.6 * mm


def _guidance(trait):
    return str(trait.get("guidance") or "").strip()


def insight_paragraph(trait, pt, color):
    """Bold summary-title lead-in followed directly by the description (guidance excluded)."""
    title = str(trait.get("summary_title") or "").strip().rstrip(": ")
    lead = f"<b>{escape(title)}:</b> " if title else ""
    body = escape(str(trait.get("text") or "")).replace("\n", "<br/>")
    return Paragraph(lead + body, ParagraphStyle(
        "insight", fontName=FONT, fontSize=pt, leading=pt * 1.5,
        textColor=color, spaceBefore=0, spaceAfter=0,
    ))


def guidance_paragraph(trait, pt):
    text = escape(_guidance(trait)).replace("\n", "<br/>")
    return Paragraph(text, ParagraphStyle(
        "guidance", fontName=FONT, fontSize=pt - 0.5, leading=(pt - 0.5) * 1.6,
        textColor=BOX_TEXT, spaceBefore=0, spaceAfter=0,
    ))


def _box_metrics(trait, pt, width):
    g = guidance_paragraph(trait, pt)
    gh = g.wrap(width - 2 * BOX_PAD, 100000)[1]
    head_h = pt * 1.2
    return g, gh, head_h, 2 * BOX_PAD + head_h + BOX_HEAD_GAP + gh


def insight_height(trait, pt, width, color):
    h = insight_paragraph(trait, pt, color).wrap(width, 100000)[1]
    if _guidance(trait):
        h += BOX_GAP + _box_metrics(trait, pt, width)[3]
    return h


def _bulb(c, cx, cy, r):
    """Small lightbulb: glass circle, base and two rays (cy in PDF coordinates)."""
    c.setFillColor(BOX_ACCENT)
    c.circle(cx, cy + r * 0.25, r, stroke=0, fill=1)
    c.rect(cx - r * 0.45, cy - r * 1.25, r * 0.9, r * 0.6, stroke=0, fill=1)
    c.setStrokeColor(BOX_ACCENT); c.setLineWidth(0.6)
    c.line(cx - r * 1.9, cy + r * 1.2, cx - r * 1.4, cy + r * 0.9)
    c.line(cx + r * 1.9, cy + r * 1.2, cx + r * 1.4, cy + r * 0.9)


def draw_insight(c, trait, x, top, page_height, width, pt, color):
    paragraph = insight_paragraph(trait, pt, color)
    _, height = paragraph.wrap(width, 100000)
    paragraph.drawOn(c, x, page_height - top - height)
    if not _guidance(trait):
        return height
    g, gh, head_h, box_h = _box_metrics(trait, pt, width)
    btop = top + height + BOX_GAP
    c.saveState()
    c.setFillColor(BOX_BG); c.setStrokeColor(BOX_BORDER); c.setLineWidth(0.6)
    c.roundRect(x, page_height - btop - box_h, width, box_h, 2.4 * mm, stroke=1, fill=1)
    hy = btop + BOX_PAD
    r = pt * 0.22
    _bulb(c, x + BOX_PAD + r * 2, page_height - hy - head_h * 0.55, r)
    c.setFillColor(BOX_ACCENT); c.setFont("Helvetica-Bold", pt - 0.3)
    c.drawString(x + BOX_PAD + r * 4.6, page_height - hy - head_h * 0.8, BOX_HEAD)
    c.restoreState()
    g.drawOn(c, x + BOX_PAD, page_height - hy - head_h - BOX_HEAD_GAP - gh)
    return height + BOX_GAP + box_h
