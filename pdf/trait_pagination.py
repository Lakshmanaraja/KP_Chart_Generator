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


def _renumber(batches):
    """Relabel codes so each tier reads sequentially in final page order.

    Same-tier codes are reused (sorted by original order), so the label set is
    unchanged; only cards moved by packing swap numbers.
    """
    order = [t for batch, _, _ in batches for t in batch]
    by_kind = {}
    for t in sorted(order, key=lambda t: t.get("_pos", 0)):
        by_kind.setdefault(t.get("kind"), []).append(t.get("code"))
    for t in order:
        codes = by_kind.get(t.get("kind"))
        if codes and t.get("code") is not None:
            t["code"] = codes.pop(0)
        t.pop("_pos", None)


def card_pages(traits, available, height_of, base_pt=12, min_pt=10, gap=12,
               first_available=None):
    """Pack cards page by page with one fixed font size.

    When a card does not fit the remaining space, later smaller cards of the
    SAME tier may fill the gap; a different tier never jumps ahead. Codes are
    renumbered afterwards so numbering stays continuous.
    """
    available -= SAFETY
    if first_available is not None:
        first_available -= SAFETY
    pending = [dict(t, _pos=i) for i, t in enumerate(traits)]
    opening = first_available is not None
    batches = []
    while pending:
        capacity = first_available if opening else available
        batch, heights, used, blocked = [], [], 0, None
        for t in pending:
            if blocked is not None and t.get("kind") != blocked:
                break
            h = height_of(t, base_pt)
            need = h + (gap if batch else 0)
            if used + need <= capacity:
                batch.append(t); heights.append(h); used += need
            elif blocked is None:
                blocked = t.get("kind")
        pt = base_pt
        if not batch:
            # A single card taller than a whole page: shrink as last resort.
            t = pending[0]
            h = height_of(t, pt)
            while h > capacity and pt > min_pt:
                pt = max(min_pt, pt - 0.25)
                h = height_of(t, pt)
            if h > capacity:
                raise ValueError("Trait content exceeds one readable PDF page; shorten the prediction or guidance.")
            batch, heights = [t], [h]
        taken = {id(t) for t in batch}
        pending = [t for t in pending if id(t) not in taken]
        batches.append((batch, pt, heights))
        opening = False
    _renumber(batches)
    yield from batches
