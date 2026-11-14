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
