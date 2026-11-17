"""Shared blue topic artwork and indivisible heading layout for PDF renderers."""
from pathlib import Path
from reportlab.lib.units import mm
from reportlab.lib.colors import Color

TOPICS = {'personality':'personality', 'speaking style':'speaking-style', 'speaking':'speaking-style',
          'daily life':'daily-life', 'education':'education', 'creativity':'creativity', 'skills':'skills',
          'food preference':'food-preference', 'food preferences':'food-preference',
          'health issues':'health-issues', 'wellness':'health-issues', 'travel':'travel',
          'places and things':'places-and-things', 'social circle':'social-circle'}

def topic_inset(title):
    return 9 * mm if title.strip().lower() in TOPICS else 0

def draw_topic_header(d, title, lines, x, width, page_height, pt, line_height, brand):
    key = TOPICS.get(title.strip().lower())
    top = d.y
    if key:
        d.c.drawImage(str(Path(__file__).parent / 'topic_icons' / (key + '.png')),
                      x, page_height - top - 6 * mm, 6 * mm, 6 * mm, mask='auto')
    for i, line in enumerate(lines):
        d.text(line, x + topic_inset(title), top + pt * 0.8 + i * line_height, pt, True, brand)
    divider = top + len(lines) * line_height + 1 * mm
    d.c.setStrokeColor(Color(213/255, 221/255, 231/255)); d.c.setLineWidth(0.7)
    d.c.line(x, page_height - divider, x + width, page_height - divider)
    d.y = divider + 4 * mm


def section_starter_layout(title, width, pt, icon_size):
    """Measure the prominent section opener before allocating its two cards."""
    from reportlab.lib.utils import simpleSplit
    inset = icon_size + 3 * mm if title.strip().lower() in TOPICS else 0
    lines = simpleSplit(title, "Helvetica-Bold", pt, width - inset) or [""]
    heading_height = max(icon_size, len(lines) * pt * 1.25)
    return lines, inset, heading_height, heading_height + 10 * mm


def draw_section_starter(d, title, x, width, page_height, pt, icon_size, brand, border):
    lines, inset, heading_height, total = section_starter_layout(title, width, pt, icon_size)
    top = d.y
    key = TOPICS.get(title.strip().lower())
    if key:
        d.c.drawImage(str(Path(__file__).parent / 'topic_icons' / (key + '.png')),
                      x, page_height - top - icon_size, icon_size, icon_size, mask='auto')
    text_top = top + max(0, (heading_height - len(lines) * pt * 1.25) / 2)
    for i, line in enumerate(lines):
        d.text(line, x + inset, text_top + pt + i * pt * 1.25, pt, True, brand)
    divider = top + heading_height + 3 * mm
    d.c.setStrokeColor(border)
    d.c.setLineWidth(0.7)
    d.c.line(x, page_height - divider, x + width, page_height - divider)
    d.y = top + total
