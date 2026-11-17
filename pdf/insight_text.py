"""Shared, measured trait cards for phone and A4 insight lists.

Each trait renders as: a bold title row (when a summary title exists), the
prediction paragraph in regular weight, then — only when guidance exists — a
softly tinted "How You Can Help" callout separated by clear vertical space.
Uses the same standard Helvetica family as the rest of the report.
"""
from html import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

FONT = "Helvetica"


from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit

BOX_BG = colors.HexColor("#FFF7E6")
BOX_BORDER = colors.HexColor("#F5DFAE")
BOX_ACCENT = colors.HexColor("#B7791F")
BOX_TEXT = colors.HexColor("#3D3523")
BOX_HEAD = "How You Can Help"
BOX_GAP, BOX_PAD, BOX_HEAD_GAP = 4 * mm, 3 * mm, 1.6 * mm
TITLE_GAP = 1.4 * mm
TITLE_LEADING = 1.35


def _guidance(trait):
    return str(trait.get("guidance") or "").strip()


def insight_title(trait):
    """Bold lead-in title shown on its own row above the prediction."""
    return str(trait.get("summary_title") or "").strip().rstrip(": ")


def title_lines(trait, pt, width):
    title = insight_title(trait)
    if not title:
        return []
    return simpleSplit(title, "Helvetica-Bold", pt + 0.5, width) or [title]


def title_height(trait, pt, width):
    lines = title_lines(trait, pt, width)
    if not lines:
        return 0.0
    return len(lines) * (pt + 0.5) * TITLE_LEADING + TITLE_GAP


def insight_paragraph(trait, pt, color):
    """The prediction text alone; the title is drawn on its own row above."""
    body = escape(str(trait.get("text") or "")).replace("\n", "<br/>")
    return Paragraph(body, ParagraphStyle(
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
    h = title_height(trait, pt, width)
    h += insight_paragraph(trait, pt, color).wrap(width, 100000)[1]
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
    y = top
    for line in title_lines(trait, pt, width):
        c.setFont("Helvetica-Bold", pt + 0.5)
        c.setFillColor(color)
        c.drawString(x, page_height - y - (pt + 0.5), line)
        y += (pt + 0.5) * TITLE_LEADING
    if y > top:
        y += TITLE_GAP
    paragraph = insight_paragraph(trait, pt, color)
    _, height = paragraph.wrap(width, 100000)
    paragraph.drawOn(c, x, page_height - y - height)
    y += height
    if not _guidance(trait):
        return y - top
    g, gh, head_h, box_h = _box_metrics(trait, pt, width)
    btop = y + BOX_GAP
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
    return y - top + BOX_GAP + box_h
