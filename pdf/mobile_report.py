"""Phone-sized (95 x 200 mm) Character Assessment Report PDF, mirroring the web app's mobile layout."""
from __future__ import annotations
import io
import os
from datetime import datetime
from typing import List, Optional
from reportlab.lib.colors import Color
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from pdf.insight_text import insight_height, draw_insight
from pdf.topic_headers import topic_inset, draw_topic_header

W, H, M = 95 * mm, 200 * mm, 4.5 * mm
LOGO = os.path.join(os.path.dirname(__file__), "logo.png")
rgb = lambda r, g, b: Color(r / 255, g / 255, b / 255)
BG, SURFACE, SHADOW = rgb(244, 246, 249), rgb(255, 255, 255), rgb(229, 233, 239)
TEXT, MUTED, ACCENT, NOTE = rgb(30, 41, 59), rgb(100, 116, 139), rgb(7, 42, 125), rgb(230, 240, 250)
BORDER, WHATSAPP = rgb(213, 221, 231), rgb(22, 163, 74)
KIND = {"primary": rgb(111, 186, 119), "secondary": rgb(122, 162, 219),
        "low": rgb(240, 201, 76), "lowest": rgb(224, 122, 110)}
LEGEND = [
    ("primary", "Primary profile", "A character trait that may appear only if the recorded birth time is accurate up to 5 mins."),
    ("secondary", "Secondary profile", "A character profile that may be exhibited temporarily."),
    ("low", "Low possibility", "A character trait that may appear only if the recorded birth time is accurate to within 3 minutes."),
    ("lowest", "Lowest possibility", "A character trait that may appear only if the recorded birth time is accurate to within 1 second. Results at this level are highly sensitive to birth-time accuracy and have a high chance of error."),
]
BODY_PT, HEAD_PT = 12, 14.5
LH = lambda pt: pt * 1.5  # points
PARENT_NOTE_TITLE = "A Note to Parents"
PARENT_NOTE_LEAD = "This report is built to support understanding, not dictate who your child should be."
PARENT_NOTE_BODY = (
    "Our goal is not to enforce pressure, but to help you better understand your child and reduce "
    "distress from social trends, outside expectations, or differences."
)


class _Doc:
    def __init__(self, buf):
        self.c = canvas.Canvas(buf, pagesize=(W, H))
        self.y = 0.0  # distance from top, in points
        self.started = False

    def page(self):
        if self.started:
            self.c.showPage()
        self.started = True
        self.c.setFillColor(BG)
        self.c.rect(0, 0, W, H, stroke=0, fill=1)
        self.y = 12 * mm

    def text(self, s, x, y_top, pt, bold=False, color=TEXT, align="left"):
        c = self.c
        c.setFont("Helvetica-Bold" if bold else "Helvetica", pt)
        c.setFillColor(color)
        yy = H - y_top
        if align == "center":
            c.drawCentredString(x, yy, s)
        elif align == "right":
            c.drawRightString(x, yy, s)
        else:
            c.drawString(x, yy, s)

    def card(self, x, y_top, w, h, r=4.2 * mm, shadow=True, color=SURFACE):
        c = self.c
        if shadow:
            c.setFillColor(SHADOW)
            c.roundRect(x, H - y_top - h - 0.6 * mm, w, h, r, stroke=0, fill=1)
        c.setFillColor(color)
        c.roundRect(x, H - y_top - h, w, h, r, stroke=0, fill=1)


def wrap(s, pt, width, bold=False):
    return simpleSplit(s, "Helvetica-Bold" if bold else "Helvetica", pt, width) or [""]


def rich_wrap(runs, pt, width):
    """Wrap (text, bold) runs while retaining inline emphasis."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    result, line, line_width = [], [], 0.0

    def push_line():
        nonlocal line, line_width
        if line:
            result.append(line)
            line, line_width = [], 0.0

    def append(text, bold, text_width):
        nonlocal line_width
        if line and line[-1][1] == bold:
            line[-1] = (line[-1][0] + text, bold)
        else:
            line.append((text, bold))
        line_width += text_width

    import re
    for text, bold in runs:
        font = "Helvetica-Bold" if bold else "Helvetica"
        for token in (t for t in re.split(r"(\s+)", text) if t):
            if token.isspace():
                if line and not line[-1][0].endswith(" "):
                    append(" ", bold, stringWidth(" ", font, pt))
                continue
            token_width = stringWidth(token, font, pt)
            if line and line_width + token_width > width:
                push_line()
            append(token, bold, token_width)
    push_line()
    return result


def draw_rich(d: _Doc, lines, x, y, pt, color=TEXT):
    for line in lines:
        dx = x
        for text, bold in line:
            d.text(text, dx, y + pt, pt, bold, color)
            dx += d.c.stringWidth(text, "Helvetica-Bold" if bold else "Helvetica", pt)
        y += LH(pt)
    return y


def draw_sparkle(d: _Doc, cx, cy, radius, color=ACCENT):
    d.c.setStrokeColor(color); d.c.setLineWidth(1.25); d.c.setLineCap(1)
    diagonal = radius * 0.55
    for x1, y1, x2, y2 in [
        (cx, cy - radius, cx, cy + radius), (cx - radius, cy, cx + radius, cy),
        (cx - diagonal, cy - diagonal, cx + diagonal, cy + diagonal),
        (cx - diagonal, cy + diagonal, cx + diagonal, cy - diagonal),
    ]:
        d.c.line(x1, H - y1, x2, H - y2)
    d.c.setLineCap(0)


def report_title(text_source: str = "report") -> str:
    """Cover/PDF title: child reports get the parent-guide title."""
    return ("Understanding Your Child: A Guide for Parents"
            if text_source == "child" else "Character Assessment Report")


def _fit(s, pt, width, bold=True, min_pt=7.0, tracking=0.0):
    """Largest size <= pt at which s fits on one line."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    font = "Helvetica-Bold" if bold else "Helvetica"
    while pt > min_pt and stringWidth(s, font, pt) + tracking * max(len(s) - 1, 0) > width:
        pt -= 0.25
    return pt


def cover_copy(text_source: str = "report"):
    """(kicker, title, subtitle) for the cover title card."""
    if text_source == "child":
        return ("CHILD PERSONALITY & BEHAVIOURAL BLUEPRINT", "Understanding Your Child",
                "A Comprehensive Guide for Parents")
    return ("PERSONALITY & BEHAVIOURAL BLUEPRINT", "CHARACTER ASSESSMENT REPORT",
            "Comprehensive Guide for Yourself")


def _cover(d: _Doc, client: dict, text_source: str = "report"):
    d.page()
    c = d.c
    cw = W - 2 * M
    x, inner = M + 4 * mm, cw - 8 * mm
    if os.path.exists(LOGO):
        c.drawImage(LOGO, W / 2 - 5.5 * mm, H - 21 * mm, 11 * mm, 11 * mm, mask="auto")
    d.text("TIME SCIENCE", W / 2, 27 * mm, 15, True, ACCENT, "center")
    kicker, title, subtitle = cover_copy(text_source)
    # Card 1: report title
    track = 0.6
    kpt = _fit(kicker, 8.5, inner * 0.9, True, 6, track)
    tpt = _fit(title, 18, inner * 0.9, True, 10)
    spt = 10.5
    sub_lines = wrap(subtitle, spt, inner)
    pad = 5 * mm
    h1 = pad + kpt + 3 * mm + 3 * mm + tpt + 2.5 * mm + LH(spt) * len(sub_lines) + pad - 2 * mm
    y1 = 32 * mm
    d.card(M, y1, cw, h1)
    y = y1 + pad + kpt
    c.setFont("Helvetica-Bold", kpt); c.setFillColor(MUTED)
    t = c.beginText(x, H - y); t.setCharSpace(track); t.textOut(kicker); c.drawText(t)
    y += 2.5 * mm
    c.setStrokeColor(ACCENT); c.setLineWidth(1.4)
    c.line(x, H - y, x + 9 * mm, H - y)
    y += 3.5 * mm + tpt
    d.text(title, x, y, tpt, True, ACCENT)
    y += 2 * mm
    for l in sub_lines:
        y += spt
        d.text(l, x, y, spt, False, MUTED); y += LH(spt) - spt
    # Card 2: subject & metadata
    rows = [("Date of Birth", client.get("date_of_birth")), ("Time of Birth", client.get("time_of_birth")),
            ("Place of Birth", client.get("place")), ("Timezone", client.get("timezone"))]
    rows = [(k, str(v)) for k, v in rows if v not in (None, "")]
    npt = 20
    name_lines = wrap(client.get("name", ""), npt, inner, True)
    val_w = inner - 27 * mm
    row_lines = [wrap(v, 8.5, val_w) for _, v in rows]
    h2 = pad + 7.5 + 2.5 * mm + LH(npt) * len(name_lines)
    if rows:
        h2 += 3 * mm + sum(LH(8.5) * len(ls) + 1 * mm for ls in row_lines)
    h2 += pad - 2 * mm
    y2 = y1 + h1 + 4 * mm
    d.card(M, y2, cw, h2)
    y = y2 + pad + 7.5
    c.setFont("Helvetica", 7.5); c.setFillColor(rgb(148, 163, 184))
    t = c.beginText(x, H - y); t.setCharSpace(0.8); t.textOut("PREPARED FOR"); c.drawText(t)
    y += 2.5 * mm
    for l in name_lines:
        y += npt
        d.text(l, x, y, npt, True, ACCENT); y += LH(npt) - npt
    if rows:
        y += 1 * mm
        c.setStrokeColor(rgb(226, 232, 240)); c.setLineWidth(0.5)
        c.line(x, H - y, x + inner, H - y)
        y += 2 * mm
        for (k, _), ls in zip(rows, row_lines):
            y += 8.5
            d.text(k.upper(), x, y, 6.5, False, rgb(148, 163, 184))
            for i, l in enumerate(ls):
                if i: y += LH(8.5)
                d.text(l, x + 27 * mm, y, 8.5, False, rgb(71, 85, 105))
            y += LH(8.5) - 8.5 + 1 * mm
    # Author footer with clickable actions
    fy, fh = H - 13 * mm - 47 * mm, 47 * mm
    d.card(M, fy, W - 2 * M, fh)
    d.text("Report Prepared by", x, fy + 6 * mm, 9.5, False, MUTED)
    d.text("Lakshmanaraja Kannan", x, fy + 12 * mm, 13, True, ACCENT)
    d.text("Time Science Researcher & Astrologer", x, fy + 17.5 * mm, 9.5, False, MUTED)
    for label, ay, url, primary in [("Chat on WhatsApp", 22.5, "https://wa.me/919176600055", True),
                                    ("Visit Website", 34.5, "https://timescience.org", False)]:
        top = fy + ay * mm
        c.setFillColor(WHATSAPP if primary else SURFACE); c.setStrokeColor(BORDER); c.setLineWidth(0.8)
        c.roundRect(x, H - top - 10.5 * mm, inner, 10.5 * mm, 2 * mm, stroke=0 if primary else 1, fill=1)
        d.text(label, W / 2, top + 6.6 * mm, 11.5, True, SURFACE if primary else TEXT, "center")
        c.linkURL(url, (x, H - top - 10.5 * mm, x + inner, H - top), relative=0)
    gen = client.get("generated_on") or datetime.now().strftime("%d-%m-%Y")
    d.text(f"Generated on {gen}", W / 2, H - 6 * mm, 9, False, MUTED, "center")


def _legend(d: _Doc):
    d.page()
    w = W - 2 * M
    d.card(M, 5 * mm, w, H - 10 * mm, shadow=False)
    x, inner = M + 4 * mm, w - 8 * mm
    y = 16 * mm
    d.text("Read this before proceeding", x, y, 13, True); y += LH(13) + 2 * mm
    intro = wrap("This report is based on 12 years of research. Please read each line carefully, "
                 "as every detail may be important.", 10.5, inner - 11 * mm)
    nh = len(intro) * LH(10.5) + 5 * mm
    d.card(x, y, inner, nh, 2 * mm, False, NOTE)
    d.c.setStrokeColor(MUTED); d.c.circle(x + 4 * mm, H - y - 4.5 * mm, 1.7 * mm, stroke=1, fill=0)
    d.text("i", x + 4 * mm, y + 5.5 * mm, 9, True, MUTED, "center")
    for i, l in enumerate(intro):
        d.text(l, x + 8 * mm, y + 5 * mm + i * LH(10.5), 10.5)
    y += nh + 8 * mm
    for kind, label, desc in LEGEND:
        d.c.setFillColor(KIND[kind])
        d.c.roundRect(x + 1.2 * mm, H - y - 2.1 * mm, 1.7 * mm, 5.6 * mm, 0.85 * mm, stroke=0, fill=1)
        d.text(label, x + 8 * mm, y, 12, True); y += 6 * mm
        for l in wrap(desc, 11, inner - 8 * mm):
            d.text(l, x + 8 * mm, y, 11, False, MUTED); y += LH(11)
        y += 7 * mm


def _topics(d: _Doc, sections: List[dict]):
    if not sections:
        return
    w = W - 2 * M
    PAD, GAP, INDENT, ITEM_GAP, BADGE = 3 * mm, 4 * mm, 5 * mm, 5 * mm, 8 * mm
    tw = w - INDENT - PAD - BADGE
    bottom = H - 10 * mm
    height_of = lambda t: insight_height(t, BODY_PT, tw, TEXT)
    for sec in sections:
        # Each report section starts cleanly; continuation pages are added only when its traits overflow.
        d.page()
        traits = sec["traits"]
        head = wrap(sec["title"], HEAD_PT, w - topic_inset(sec["title"]), True)
        head_h = len(head) * LH(HEAD_PT) + 5 * mm
        if traits and d.y + head_h + 2 * PAD + height_of(traits[0]) > bottom:
            d.page()
        draw_topic_header(d, sec["title"], head, M, w, H, HEAD_PT, LH(HEAD_PT), ACCENT)
        # Group consecutive traits by kind into colored-accent cards, splitting across pages.
        groups: List[List[dict]] = []
        for t in traits:
            if groups and groups[-1][0]["kind"] == t["kind"]:
                groups[-1].append(t)
            else:
                groups.append([t])
        for g in groups:
            i = 0
            while i < len(g):
                if d.y + 2 * PAD + height_of(g[i]) > bottom:
                    d.page()
                chunk, h = [], 2 * PAD
                while i < len(g) and d.y + h + height_of(g[i]) + (ITEM_GAP if chunk else 0) <= bottom:
                    h += height_of(g[i]) + (ITEM_GAP if chunk else 0)
                    chunk.append(g[i]); i += 1
                if not chunk:  # single trait taller than a page: force it
                    chunk = [g[i]]; h = 2 * PAD + height_of(g[i]); i += 1
                d.card(M, d.y, w, h, 3 * mm)
                d.c.setFillColor(KIND[g[0]["kind"]])
                d.c.roundRect(M, H - d.y - h, 1.6 * mm, h, 0.8 * mm, stroke=0, fill=1)
                ty = d.y + PAD
                for t in chunk:
                    draw_insight(d.c, t, M + INDENT, ty, H, tw, BODY_PT, TEXT)
                    # code pill
                    pill_w = d.c.stringWidth(t["code"], "Helvetica-Bold", 7.5) + 3 * mm
                    px = W - M - PAD - pill_w
                    d.c.setFillColor(BG)
                    d.c.roundRect(px, H - ty - 4.6 * mm, pill_w, 4.2 * mm, 2.1 * mm, stroke=0, fill=1)
                    d.text(t["code"], px + pill_w / 2, ty + 3.1 * mm, 7.5, True, MUTED, "center")
                    ty += height_of(t) + ITEM_GAP
                d.y += h + GAP
        d.y += 3 * mm


def _parents_note(d: _Doc):
    """Measured, nested reading guidance and an airy two-paragraph parent note."""
    d.page()
    w = W - 2 * M
    outer_pad, accent_w, card_gap, title_pt = 3.5 * mm, 1.7 * mm, 5 * mm, 12.5
    content_x = M + outer_pad + accent_w
    content_w = w - 2 * outer_pad - accent_w
    sub_pad = 3 * mm
    sub_text_x = content_x + sub_pad
    sub_text_w = content_w - 2 * sub_pad
    soft_green, soft_warm, soft_blue = rgb(239, 248, 240), rgb(255, 248, 235), rgb(241, 245, 251)
    amber, amber_bg = rgb(146, 64, 14), rgb(254, 243, 199)
    other_colors = [KIND["secondary"], KIND["low"], KIND["lowest"]]

    def measure(pt):
        primary = rich_wrap([
            ("Your child will show the ", False), ("Primary trait most often", True), (".", False),
        ], pt, sub_text_w)
        secondary = rich_wrap([
            ("Other traits appear in specific situations and may ", False),
            ("change over time", True), (".", False),
        ], pt, sub_text_w - 4 * mm)
        both = rich_wrap([
            ("Both ", False), ("behaviors are strong", True), (". It may be ", False),
            ("difficult to predict", True), (" which appears in a given situation.", False),
        ], pt, sub_text_w)
        note_lead = rich_wrap([(PARENT_NOTE_LEAD, True)], pt + 0.75, content_w)
        note_body = rich_wrap([(PARENT_NOTE_BODY, False)], pt, content_w)
        scenario_title_width = d.c.stringWidth("Primary + other category traits", "Helvetica-Bold", pt + 0.25)
        a_height = (2 * sub_pad + LH(pt + 0.25) + 1.5 * mm + len(primary) * LH(pt)
                    + 1.5 * mm + len(secondary) * LH(pt))
        b_height = 2 * sub_pad + LH(pt + 0.25) + 1.5 * mm + len(both) * LH(pt)
        guidance_height = (2 * outer_pad + LH(title_pt) + 2 * mm + 7 * mm + 3 * mm
                           + a_height + 3 * mm + b_height)
        note_height = (2 * outer_pad + LH(title_pt) + 2 * mm + len(note_lead) * LH(pt + 0.75)
                       + 2.5 * mm + len(note_body) * LH(pt))
        return {
            "primary": primary, "secondary": secondary, "both": both,
            "note_lead": note_lead, "note_body": note_body,
            "scenario_title_width": scenario_title_width, "a_height": a_height,
            "b_height": b_height, "guidance_height": guidance_height, "note_height": note_height,
        }

    pt = 10.5
    measured = measure(pt)
    while measured["guidance_height"] + card_gap + measured["note_height"] > H - 10 * mm - d.y and pt > 9.25:
        pt -= 0.25
        measured = measure(pt)

    def draw_outer(top, height, color):
        d.card(M, top, w, height, 4.2 * mm, True, color)
        d.c.setFillColor(ACCENT)
        d.c.roundRect(M + 0.9 * mm, H - top - height + 1.2 * mm,
                      accent_w, height - 2.4 * mm, 0.85 * mm, stroke=0, fill=1)

    def legend_width(label, colors, font_pt):
        return (4.4 * mm + len(colors) * 1.7 * mm + max(0, len(colors) - 1) * mm
                + 1.2 * mm + d.c.stringWidth(label, "Helvetica-Bold", font_pt) + 2.2 * mm)

    def draw_legend_item(x, top, width, label, colors, bg, font_pt):
        d.card(x, top, width, 7 * mm, 3.5 * mm, False, bg)
        pill_x = x + 2.2 * mm
        for color in colors:
            d.c.setFillColor(color)
            d.c.roundRect(pill_x, H - top - 1.9 * mm - 3.2 * mm,
                          1.7 * mm, 3.2 * mm, 0.8 * mm, stroke=0, fill=1)
            pill_x += 2.7 * mm
        d.text(label, pill_x + 1.2 * mm, top + 4.55 * mm, font_pt, True, TEXT)

    guidance_y = d.y
    draw_outer(guidance_y, measured["guidance_height"], SURFACE)
    top = guidance_y + outer_pad
    d.text("How to Read Conflicting Traits", content_x, top + title_pt, title_pt, True, ACCENT)
    top += LH(title_pt) + 2 * mm

    legend_pt = min(8.5, pt - 1)
    while (legend_width("Primary traits", [KIND["primary"]], legend_pt)
           + legend_width("Other category traits", other_colors, legend_pt) + 2 * mm > content_w
           and legend_pt > 7.25):
        legend_pt -= 0.25
    primary_legend_w = legend_width("Primary traits", [KIND["primary"]], legend_pt)
    other_legend_w = legend_width("Other category traits", other_colors, legend_pt)
    draw_legend_item(content_x, top, primary_legend_w, "Primary traits", [KIND["primary"]], soft_green, legend_pt)
    draw_legend_item(content_x + primary_legend_w + 2 * mm, top, other_legend_w,
                     "Other category traits", other_colors, soft_blue, legend_pt)
    top += 10 * mm

    # Scenario A: soft green nested card with inline category pills.
    d.card(content_x, top, content_w, measured["a_height"], 3 * mm, False, soft_green)
    d.text("Primary + other category traits", sub_text_x, top + sub_pad + pt + 0.25,
           pt + 0.25, True, TEXT)
    pill_x = sub_text_x + measured["scenario_title_width"] + 2 * mm
    for color in [KIND["primary"], *other_colors]:
        d.c.setFillColor(color)
        d.c.roundRect(pill_x, H - top - sub_pad - 0.2 * mm - 3.2 * mm,
                      1.7 * mm, 3.2 * mm, 0.8 * mm, stroke=0, fill=1)
        pill_x += 2.7 * mm
    body_top = top + sub_pad + LH(pt + 0.25) + 1.5 * mm
    body_top = draw_rich(d, measured["primary"], sub_text_x, body_top, pt) + 1.5 * mm
    d.c.setFillColor(ACCENT)
    d.c.circle(sub_text_x + 0.8 * mm, H - body_top - 1.4 * mm, 0.65 * mm, stroke=0, fill=1)
    draw_rich(d, measured["secondary"], sub_text_x + 4 * mm, body_top, pt)
    top += measured["a_height"] + 3 * mm

    # Scenario B: warm nested card and a compact Uncommon badge.
    d.card(content_x, top, content_w, measured["b_height"], 3 * mm, False, soft_warm)
    d.text("Both traits appear as Primary", sub_text_x, top + sub_pad + pt + 0.25,
           pt + 0.25, True, TEXT)
    badge_w = d.c.stringWidth("Uncommon", "Helvetica-Bold", 7.5) + 4 * mm
    badge_x = sub_text_x + sub_text_w - badge_w
    d.c.setFillColor(amber_bg)
    d.c.roundRect(badge_x, H - top - sub_pad + 0.5 * mm - 5 * mm,
                  badge_w, 5 * mm, 2.5 * mm, stroke=0, fill=1)
    d.text("Uncommon", badge_x + 2 * mm, top + sub_pad + 3.0 * mm, 7.5, True, amber)
    body_top = top + sub_pad + LH(pt + 0.25) + 1.5 * mm
    draw_rich(d, measured["both"], sub_text_x, body_top, pt)

    # Parent note: star accents, bold lead paragraph and a regular second paragraph.
    note_y = guidance_y + measured["guidance_height"] + card_gap
    draw_outer(note_y, measured["note_height"], NOTE)
    top = note_y + outer_pad
    draw_sparkle(d, content_x + 1.6 * mm, top + 2.1 * mm, 1.6 * mm)
    draw_sparkle(d, content_x + 5.3 * mm, top + 1.1 * mm, 0.9 * mm, KIND["primary"])
    d.text(PARENT_NOTE_TITLE, content_x + 9 * mm, top + title_pt, title_pt, True, ACCENT)
    top += LH(title_pt) + 2 * mm
    top = draw_rich(d, measured["note_lead"], content_x, top, pt + 0.75) + 2.5 * mm
    draw_rich(d, measured["note_body"], content_x, top, pt)
    d.y = note_y + measured["note_height"]


def render_mobile_pdf(sections: List[dict], client: dict, text_source: str = "report") -> bytes:
    buf = io.BytesIO()
    d = _Doc(buf)
    _cover(d, client, text_source)
    _legend(d)
    _topics(d, sections)
    if text_source == "child":
        _parents_note(d)
    d.c.setTitle(f"{report_title(text_source)} - {client.get('name', '')}")
    d.c.setAuthor("Time Science")
    d.c.save()
    return buf.getvalue()

def render_mobile_from_chart(chart, mappings, client, topics=None, extra_tags=None,
                             *, include_sn=False, include_sk=False, text_source="report"):
    """Match enabled columns before ranking; SN and SK are independent opt-ins."""
    from app.engine.ranker import build_report
    sections = build_report(chart, mappings, topics, extra_tags,
                            include_sn=include_sn, include_sk=include_sk,
                            text_source=text_source)
    return render_mobile_pdf(sections, client, text_source)
