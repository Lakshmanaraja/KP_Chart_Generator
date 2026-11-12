"""Builds Character Report topics: filtering, tier ranking, global de-duplication, trait codes."""
from __future__ import annotations
import re
from typing import Dict, List, Optional
from services.matcher_service import chart_mapping_matches, CHARACTER_TIER, GENERATION_COLUMNS

OTHERS = "Others"
DEFAULT_EXCLUDED = re.compile(r"\bindustry\b|\bpartner\b|\bmarriage\b|\bsleep\b", re.I)
KIND_BY_TIER_INDEX = {3: "secondary", 4: "low", 5: "lowest"}


def section_allowed(section: str, selected: Optional[List[str]]) -> bool:
    """Explicit topic selection wins; otherwise default-excluded topics are dropped."""
    sec = (section or OTHERS).strip()
    if selected is not None:
        return any(t.strip().lower() == sec.lower() for t in selected)
    return not DEFAULT_EXCLUDED.search(sec)


def topic_prefixes(titles: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for title in titles:
        if title in out:
            continue
        letters = re.sub(r"[^A-Za-z]", "", title).upper()
        if not letters:
            out[title] = f"T{len(out) + 1}"
            continue
        n, cand = 1, letters[:1]
        while cand in out.values() and n < len(letters):
            n += 1
            cand = letters[:n]
        out[title] = cand
    return out


def trait_label(prefix: str, ti: int, n: int) -> str:
    return f"{prefix}{ {3: 'S', 4: 'L', 5: 'LT'}.get(ti, '') }{n}".replace(" ", "")


def ordered_traits(tiers: List[List[str]], prefix: str) -> List[dict]:
    counters: Dict[str, int] = {}
    out = []
    for ti in [0, 1, 2, 6, 3, 4, 5]:
        for text in tiers[ti]:
            series = str(ti) if ti in (3, 4, 5) else "main"
            counters[series] = counters.get(series, 0) + 1
            out.append({"text": text, "code": trait_label(prefix, ti, counters[series]),
                        "kind": KIND_BY_TIER_INDEX.get(ti, "primary")})
    return out


def build_report(chart: dict, mappings: List[dict], topics: Optional[List[str]] = None,
                 extra_tags: Optional[List[str]] = None, *,
                 include_sn: bool = False, include_sk: bool = False,
                 text_source: str = "report") -> List[dict]:
    """Returns [{title, traits:[{text, code, kind}]}] in report order.

    text_source="child" uses each tag's child_report_text; anything else uses report_text.
    Tags with blank text for the chosen source are left out."""
    field = "child_report_text" if (text_source or "").lower() == "child" else "report_text"
    
    enabled = [c for c in GENERATION_COLUMNS
               if (c != "SN" or include_sn) and (c != "SK" or include_sk)]
    matches = chart_mapping_matches(chart, mappings, enabled)
    all_matches = chart_mapping_matches(chart, mappings)
    generated = {t.lower() for t in matches}
    # A saved Generated tag must not bypass a disabled column. Retain genuinely
    # unmatched verified extras, preserving the existing unclassified behavior.
    blocked = {t.lower() for t in all_matches if t not in matches}
    generated |= {t.lower() for t in (extra_tags or []) if t.lower() not in blocked}

    cands = [m for m in mappings
             if m.get("is_active", True) and m["tag"].lower() in generated
             and (m.get(field) or "").strip()
             and section_allowed(m.get("section") or OTHERS, topics)]
    tier = {m["tag"]: min([CHARACTER_TIER[c] for c in matches.get(m["tag"], ())] or [7])
            for m in cands}
    cands.sort(key=lambda m: (m.get("bhava_no") or 99, tier.get(m["tag"], 7),
                              m.get("section_order") or 0, m.get("display_order") or 0))
    tier_idx = lambda tag: min(max(tier.get(tag, 7) - 1, 0), 6)
    order: List[str] = []
    for m in cands:
        t = (m.get("section") or OTHERS).strip()
        if t not in order:
            order.append(t)
    seen, bucket = set(), {}
    for m in sorted(cands, key=lambda m: tier_idx(m["tag"])):  # stable: best tier wins duplicates
        text = clean_text(m[field])
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        sec = (m.get("section") or OTHERS).strip()
        bucket.setdefault(sec, [[] for _ in range(7)])[tier_idx(m["tag"])].append(text)
    titles = [t for t in order if t in bucket]
    prefixes = topic_prefixes(titles)
    return [{"title": t, "traits": ordered_traits(bucket[t], prefixes[t])} for t in titles]


def clean_text(text: str) -> str:
    text = text.strip()
    if re.search(r"[ÂÃâ][\x80-\xbf\u0152-\u2122]", text):
        for enc in ("cp1252", "latin-1"):
            try:
                text = text.encode(enc).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        text = text.replace("\u00e2", "'")  # stray lossy mojibake
        text = re.sub(r"[\u2018\u2019\u02BC\u2032]", "'", text)
        text = re.sub(r"[\u201C\u201D\u2033]", '"', text)
        text = re.sub(r"[\u2013\u2014\u2212]", "-", text).replace("\u2026", "...")
        text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
        #text = re.sub(r"[ \t]{2,}", " ", text).rstrip(",;")
        text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", text)  # control bytes render as black boxes
        text = re.sub(r"[ \t]{2,}", " ", text).rstrip(",;")
        if text and text[-1] not in ".!?":
            text += "."
    return text
