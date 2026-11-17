"""Shared measured pagination: as many cards per page as fit, uncapped.

Keep readable font floors; exceptionally long content uses fewer cards rather
than clipping or silently dropping text. Section-ending pages may be short.
"""
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

SAFETY = 2 * mm


def fit_label(text, width, font, pt):
    text = str(text or "")
    if stringWidth(text, font, pt) <= width:
        return text
    while text and stringWidth(text + "...", font, pt) > width:
        text = text[:-1]
    return text.rstrip() + "..."


def draw_page_header(d, section, name, x, width, page_height, top, pt, color, border):
    right_width = width * 0.56
    suffix = f" • Page {d.c.getPageNumber()}"
    name_width = max(0, right_width - stringWidth(suffix, "Helvetica", pt))
    right = fit_label(name, name_width, "Helvetica", pt) + suffix
    left = fit_label(section, width * 0.42, "Helvetica-Bold", pt)
    d.text(left, x, top, pt, True, color)
    d.text(right, x + width, top, pt, False, color, "right")
    d.c.setStrokeColor(border)
    d.c.setLineWidth(0.5)
    d.c.line(x, page_height - top - 3, x + width, page_height - top - 3)


def card_pages(traits, available, height_of, base_pt=12, min_pt=10, gap=12,
               first_available=None):
    """Return batches with the exact measured size used by drawing."""
    # Reserve room for card shadows so no card edge ever touches the margin.
    available -= SAFETY
    if first_available is not None:
        first_available -= SAFETY
    pending = list(traits)
    opening = first_available is not None
    while pending:
        capacity = first_available if opening else available
        # No card cap: take every card that fits whole on the page.
        count = len(pending)
        while count:
            batch = pending[:count]
            pt = base_pt
            while True:
                heights = [height_of(t, pt) for t in batch]
                used = sum(heights) + gap * (count - 1)
                if used <= capacity:
                    break
                if pt <= min_pt:
                    break
                pt = max(min_pt, pt - 0.25)
            if used <= capacity:
                # Cards keep their natural height and stack from the top with a
                # fixed gap; leftover space stays at the bottom of the page.
                yield batch, pt, heights
                pending = pending[count:]
                opening = False
                break
            if count == 1:
                raise ValueError("Trait content exceeds one readable PDF page; shorten the prediction or guidance.")
            count -= 1