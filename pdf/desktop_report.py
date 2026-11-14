"""A4 desktop Character Assessment Report PDF, mirroring the web app's desktop layout.

Drop into app/pdf/desktop_report.py. Same inputs as mobile_report.render_pdf:
    sections: [{"title": str, "traits": [{"text", "code", "kind"}]}]   (kind: primary|secondary|low|lowest)
    client:   {"name", "date_of_birth", "time_of_birth", "place", "timezone", "generated_on"?}
"""
from __future__ import annotations
import io
import os
from datetime import datetime
from typing import List
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from pdf.insight_text import insight_height, draw_insight

W, H = A4
LOGO = os.path.join(os.path.dirname(__file__), "logo.png")
rgb = lambda r, g, b: Color(r / 255, g / 255, b / 255)
BODY, GREY, BRAND = rgb(30, 41, 59), rgb(100, 116, 139), rgb(7, 42, 125)
NOTE, BORDER, CODE, WHITE = rgb(230, 240, 250), rgb(226, 232, 240), rgb(148, 163, 184), rgb(255, 255, 255)
KIND = {"primary": rgb(111, 186, 119), "secondary": rgb(122, 162, 219),
        "low": rgb(240, 201, 76), "lowest": rgb(224, 122, 110)}
ORDER = ["primary", "secondary", "low", "lowest"]
LEGEND = [
    ("primary", "Primary profile", "A character trait that may appear only if the recorded birth time is accurate up to 5 mins."),
    ("secondary", "Secondary profile", "A character profile that may be exhibited temporarily."),
    ("low", "Low possibility", "A character trait that may appear only if the recorded birth time is accurate to within 3 minutes."),
    ("lowest", "Lowest possibility", "A character trait that may appear only if the recorded birth time is accurate to within 1 second. Results at this level are highly sensitive to birth-time accuracy and have a high chance of error."),
]
TOP, BOTTOM = 20 * mm, H - 18 * mm
WIDTH = min(W - 36 * mm, 150 * mm)          # constrained editorial column (~680px), centred
X = (W - WIDTH) / 2
BODY_PT, HEAD_PT = 12, 17
LH = lambda pt: pt * 1.5                     # line height in points
PAD, GAP, ITEM_GAP, CODE_COL = 5 * mm, 5 * mm, 3.5 * mm, 12 * mm
INDENT = PAD + 3 * mm
TEXT_W = WIDTH - INDENT - CODE_COL - PAD


def wrap(s, pt, width, bold=False):
    return simpleSplit(s or "", "Helvetica-Bold" if bold else "Helvetica", pt, width) or [""]


def report_title(text_source: str = "report") -> str:
    """Cover/PDF title: child reports get the parent-guide title."""
    return ("Understanding Your Child: A Guide for Parents"
            if text_source == "child" else "Character Assessment Report")


class _Doc:
    def __init__(self, buf):
        self.c = canvas.Canvas(buf, pagesize=A4)
        self.y = TOP          # distance from top, in points
        self.started = False

    def page(self):
        if self.started:
            self.c.showPage()
        self.started = True
        self.y = TOP

    def text(self, s, x, y_top, pt, bold=False, color=BODY, align="left"):
        c = self.c
        c.setFont("Helvetica-Bold" if bold else "Helvetica", pt)
        c.setFillColor(color)
        yy = H - y_top
        (c.drawCentredString if align == "center" else c.drawRightString if align == "right" else c.drawString)(x, yy, s)


def _cover(d: _Doc, client: dict, text_source: str = "report"):
    d.page()
    c = d.c
    if os.path.exists(LOGO):
        c.drawImage(LOGO, W / 2 - 11 * mm, H - 52 * mm, 22 * mm, 22 * mm, mask="auto")
    d.text("TIME SCIENCE", W / 2, 62 * mm, 20, True, BRAND, "center")
    ty = 95 * mm
    for l in wrap(report_title(text_source), 26, WIDTH, True):
        d.text(l, W / 2, ty, 26, True, BRAND, "center"); ty += LH(26)
    d.text("Comprehensive Personality & Behavioural Blueprint", W / 2, ty + 3 * mm, 12, False, GREY, "center")
    y = max(130 * mm, ty + 16 * mm)
    for l in wrap(client.get("name", ""), 22, WIDTH, True):
        d.text(l, W / 2, y, 22, True, BODY, "center"); y += LH(22)
    rows = [("Date of Birth", client.get("date_of_birth")), ("Time of Birth", client.get("time_of_birth")),
            ("Place of Birth", client.get("place")), ("Timezone", client.get("timezone"))]
    rows = [(k, str(v)) for k, v in rows if v not in (None, "")]
    if rows:
        y += 4 * mm
        c.setStrokeColor(BORDER); c.setLineWidth(0.6)
        c.line(X + 20 * mm, H - y, X + WIDTH - 20 * mm, H - y)
        y += 9 * mm
        kx, vx = X + 25 * mm, X + 65 * mm
        for k, v in rows:
            d.text(k.upper(), kx, y, 8.5, False, CODE)
            for l in wrap(v, 11, X + WIDTH - 20 * mm - vx):
                d.text(l, vx, y, 11, False, BODY); y += LH(11)
            y += 1.5 * mm
    # Author footer
    fy = H - 60 * mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.6); c.line(X, H - fy, X + WIDTH, H - fy)
    d.text("Report Prepared by", W / 2, fy + 9 * mm, 10, False, GREY, "center")
    d.text("Lakshmanaraja Kannan", W / 2, fy + 16 * mm, 14, True, BRAND, "center")
    d.text("Time Science Researcher & Astrologer", W / 2, fy + 22 * mm, 10, False, GREY, "center")
    links = "WhatsApp: +91 91766 00055   |   timescience.org"
    d.text(links, W / 2, fy + 30 * mm, 10, False, BRAND, "center")
    lw = c.stringWidth(links, "Helvetica", 10)
    half = c.stringWidth("WhatsApp: +91 91766 00055", "Helvetica", 10)
    lx, ly = W / 2 - lw / 2, H - fy - 30 * mm
    c.linkURL("https://wa.me/919176600055", (lx, ly - 2, lx + half, ly + 10), relative=0)
    c.linkURL("https://timescience.org", (lx + lw - c.stringWidth("timescience.org", "Helvetica", 10), ly - 2, lx + lw, ly + 10), relative=0)
    gen = client.get("generated_on") or datetime.now().strftime("%d-%m-%Y")
    d.text(f"Generated on {gen}", W / 2, H - 12 * mm, 9, False, GREY, "center")


def _legend(d: _Doc, text_source: str = "report"):
    d.page()
    c, y = d.c, TOP
    d.text(report_title(text_source), X, y + 6 * mm, 22, True, BRAND); y += 18 * mm
    c.setStrokeColor(BORDER); c.setLineWidth(0.85); c.line(X, H - y, X + WIDTH, H - y); y += 12 * mm
    d.text("Read this before proceeding", X, y, 15, True); y += 6 * mm
    intro = wrap("This report is based on 14 years of research. Please read each line carefully, "
                 "as every detail may be important.", 11, WIDTH - 16 * mm)
    nh = len(intro) * LH(11) + 8 * mm
    c.setFillColor(NOTE); c.roundRect(X, H - y - nh, WIDTH, nh, 2.5 * mm, stroke=0, fill=1)
    c.setStrokeColor(GREY); c.setLineWidth(0.85); c.circle(X + 6 * mm, H - y - nh / 2, 2 * mm, stroke=1, fill=0)
    d.text("i", X + 6 * mm, y + nh / 2 + 1.1 * mm, 9, True, GREY, "center")
    for i, l in enumerate(intro):
        d.text(l, X + 12 * mm, y + 6.5 * mm + i * LH(11), 11)
    y += nh + 12 * mm
    for kind, label, desc in LEGEND:
        c.setFillColor(KIND[kind])
        c.roundRect(X + 1 * mm, H - y - 2 * mm, 1.8 * mm, 6 * mm, 0.9 * mm, stroke=0, fill=1)
        d.text(label, X + 8 * mm, y, 12.5, True); y += 6.5 * mm
        dl = wrap(desc, 11, WIDTH - 8 * mm)
        for i, l in enumerate(dl):
            d.text(l, X + 8 * mm, y + i * LH(11), 11, False, GREY)
        y += len(dl) * LH(11) + 9 * mm


def _h(t):
    return insight_height(t, BODY_PT, TEXT_W, BODY)


def _card(d: _Doc, items: List[dict]) -> float:
    c, top = d.c, d.y
    total = 2 * PAD + sum(_h(t) for t in items) + ITEM_GAP * (len(items) - 1)
    c.setFillColor(WHITE); c.setStrokeColor(BORDER); c.setLineWidth(0.7)
    c.roundRect(X, H - top - total, WIDTH, total, 2.6 * mm, stroke=1, fill=1)
    c.setFillColor(KIND[items[0]["kind"]])
    c.roundRect(X + 1 * mm, H - top - total + 1.3 * mm, 1.8 * mm, max(2.6 * mm, total - 2.6 * mm), 0.9 * mm, stroke=0, fill=1)
    iy = top + PAD
    for idx, t in enumerate(items):
        draw_insight(c, t, X + INDENT, iy, H, TEXT_W, BODY_PT, BODY)
        code = t.get("code", "")
        pill_w = c.stringWidth(code, "Helvetica-Bold", 8.5) + 3 * mm
        px = X + WIDTH - PAD - pill_w
        c.setFillColor(NOTE)
        c.roundRect(px, H - iy - 4.6 * mm, pill_w, 4.2 * mm, 2.1 * mm, stroke=0, fill=1)
        d.text(code, px + pill_w / 2, iy + 3.1 * mm, 8.5, True, GREY, "center")
        iy += _h(t) + (ITEM_GAP if idx < len(items) - 1 else 0)
    return total


def _topics(d: _Doc, sections: List[dict]):
    sections = [s for s in sections if s.get("traits")]
    if not sections:
        return
    d.page()
    for sec in sections:
        traits = sec["traits"]
        head = wrap(sec["title"], HEAD_PT, WIDTH, True)
        head_to_card = max(0, len(head) - 1) * LH(HEAD_PT) + 4.5 * mm
        gap = 9 * mm if d.y > TOP + 2 else 0
        if d.y + gap + head_to_card + 2 * PAD + _h(traits[0]) > BOTTOM:
            d.page()
        else:
            d.y += gap
        d.y += LH(HEAD_PT) * 0.6
        for i, l in enumerate(head):
            d.text(l, X, d.y + i * LH(HEAD_PT), HEAD_PT, True, BRAND)
        d.y += head_to_card
        for kind in ORDER:
            items = [t for t in traits if t.get("kind") == kind]
            if not items:
                continue
            if d.y + 2 * PAD + _h(items[0]) > BOTTOM:
                d.page()
            buf: List[dict] = []
            for t in items:
                content = sum(_h(b) for b in buf) + ITEM_GAP * len(buf) + _h(t)
                if buf and d.y + 2 * PAD + content > BOTTOM:
                    _card(d, buf); d.page(); buf = []
                buf.append(t)
            if buf:
                d.y += _card(d, buf) + GAP


def render_desktop_pdf(sections: List[dict], client: dict, text_source: str = "report") -> bytes:
    buf = io.BytesIO()
    d = _Doc(buf)
    _cover(d, client, text_source)
    _legend(d, text_source)
    _topics(d, sections)
    d.c.setTitle(f"{report_title(text_source)} - {client.get('name', '')}")
    d.c.setAuthor("Time Science")
    d.c.save()
    return buf.getvalue()

def render_desktop_from_chart(chart, mappings, client, topics=None, extra_tags=None,
                              *, include_sn=False, include_sk=False, text_source="report"):
    """Match enabled columns before ranking; SN and SK are independent opt-ins."""
    from app.engine.ranker import build_report
    sections = build_report(chart, mappings, topics, extra_tags,
                            include_sn=include_sn, include_sk=include_sk,
                            text_source=text_source)
    return render_desktop_pdf(sections, client, text_source)
