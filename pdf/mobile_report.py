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


def report_title(text_source: str = "report") -> str:
    """Cover/PDF title: child reports get the parent-guide title."""
    print(f"report_title called with text_source: {text_source}")
    return ("Understanding Your Child: A Guide for Parents"
            if text_source == "child" else "Character Assessment Report")


def _cover(d: _Doc, client: dict, text_source: str = "report"):
    d.page()
    c, inner = d.c, W - 2 * M - 8 * mm
    if os.path.exists(LOGO):
        c.drawImage(LOGO, W / 2 - 5.5 * mm, H - 23 * mm, 11 * mm, 11 * mm, mask="auto")
    d.text("TIME SCIENCE", W / 2, 31 * mm, 15, True, ACCENT, "center")
    x = M + 4 * mm
    y = 62 * mm
    for l in wrap(report_title(text_source).upper(), 10.5, inner, True):
        d.text(l, x, y, 10.5, True, ACCENT); y += LH(10.5)
    y += 2.5 * mm
    for l in wrap("Comprehensive Personality & Behavioural Blueprint", 9.5, inner):
        d.text(l, x, y, 9.5, False, MUTED); y += LH(9.5)
    y += 9 * mm
    for l in wrap(client.get("name", ""), 24, inner, True):
        d.text(l, x, y, 24, True, ACCENT); y += LH(24)
    rows = [("Date of Birth", client.get("date_of_birth")), ("Time of Birth", client.get("time_of_birth")),
            ("Place of Birth", client.get("place")), ("Timezone", client.get("timezone"))]
    rows = [(k, str(v)) for k, v in rows if v not in (None, "")]
    if rows:
        y += 3 * mm
        c.setStrokeColor(rgb(226, 232, 240)); c.setLineWidth(0.4)
        c.line(x, H - y + 4 * mm, x + inner, H - y + 4 * mm)
        for k, v in rows:
            d.text(k.upper(), x, y, 6.5, False, rgb(148, 163, 184))
            for l in wrap(v, 8, inner - 22 * mm):
                d.text(l, x + 22 * mm, y, 8, False, rgb(71, 85, 105)); y += LH(8)
            y += 0.6 * mm
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
    d.page()
    w = W - 2 * M
    PAD, GAP, INDENT, ITEM_GAP, BADGE = 4 * mm, 4 * mm, 6 * mm, 3.5 * mm, 12 * mm
    tw = w - INDENT - PAD - BADGE
    bottom = H - 10 * mm
    lines_of = lambda t: wrap(t["text"], BODY_PT, tw)
    height_of = lambda t: len(lines_of(t)) * LH(BODY_PT)
    for sec in sections:
        traits = sec["traits"]
        head = wrap(sec["title"], HEAD_PT, w, True)
        head_h = len(head) * LH(HEAD_PT) + 3 * mm
        if traits and d.y + head_h + 2 * PAD + height_of(traits[0]) > bottom:
            d.page()
        for l in head:
            d.text(l, M, d.y + HEAD_PT * 0.8, HEAD_PT, True); d.y += LH(HEAD_PT)
        d.y += 3 * mm
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
                    for j, l in enumerate(lines_of(t)):
                        d.text(l, M + INDENT, ty + BODY_PT * 0.85 + j * LH(BODY_PT), BODY_PT)
                    # code pill
                    pill_w = d.c.stringWidth(t["code"], "Helvetica-Bold", 7.5) + 3 * mm
                    px = W - M - PAD - pill_w
                    d.c.setFillColor(BG)
                    d.c.roundRect(px, H - ty - 4.6 * mm, pill_w, 4.2 * mm, 2.1 * mm, stroke=0, fill=1)
                    d.text(t["code"], px + pill_w / 2, ty + 3.1 * mm, 7.5, True, MUTED, "center")
                    ty += height_of(t) + ITEM_GAP
                d.y += h + GAP
        d.y += 3 * mm


def render_mobile_pdf(sections: List[dict], client: dict, text_source: str = "report") -> bytes:
    buf = io.BytesIO()
    d = _Doc(buf)
    _cover(d, client, text_source)
    _legend(d)
    _topics(d, sections)
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
