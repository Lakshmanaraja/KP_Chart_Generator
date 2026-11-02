"""KP chart -> tag rule matcher. Faithful port of the Time Science web app logic."""
from __future__ import annotations
from typing import Any, Callable, Dict, Iterable, List, Optional, Set

VIMSHOTTARI_CYCLE = ["Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"]
PLANET_ABBR = {"Sun": "Su", "Moon": "Mo", "Mercury": "Me", "Venus": "Ve", "Mars": "Ma",
               "Jupiter": "Ju", "Saturn": "Sa", "Rahu": "Ra", "Ketu": "Ke", "Ascendant": "Asc"}
GENERATION_COLUMNS = ["DA", "DT", "BH", "AN", "SN", "PL", "NL", "SU", "SS", "SK"]
MULTI_BHAVA_COLUMNS = ["DA", "BH", "AN", "SN"]
# Character Report accuracy tier of each column (1 = highest).
CHARACTER_TIER = {"PL": 1, "BH": 2, "SU": 2, "DA": 3, "NL": 3, "DT": 4, "AN": 5, "SS": 5, "SN": 6, "SK": 6}
CUSP_FIELDS = [("DA", "nakshatra_lord"), ("BH", "sub_lord"), ("AN", "sub_sub_lord"), ("SN", "sub_sub_sub_lord")]


def abbr(name: Optional[str]) -> Optional[str]:
    return PLANET_ABBR.get(name, name) if name else None


def house_of_degree(degree: float, houses: List[dict]) -> Optional[int]:
    if not houses:
        return None
    hs = sorted(houses, key=lambda h: h["house_id"])
    nd = ((degree % 360) + 360) % 360
    for i, h in enumerate(hs):
        s, e = h["full_degree"], hs[(i + 1) % len(hs)]["full_degree"]
        if (e < s and (nd >= s or nd < e)) or (s <= nd < e):
            return h["house_id"]
    return None


def da_transit_keys(houses: List[dict], nl_keys: Set[str]) -> Set[str]:
    """Cycle planets passed between a bhava's DA and the next bhava's DA (excluding NL keys)."""
    out: Set[str] = set()
    hs = sorted([h for h in houses if h.get("house_id") and h.get("da")], key=lambda h: h["house_id"])
    for i, h in enumerate(hs):
        nxt = hs[(i + 1) % len(hs)]
        if h["da"] not in VIMSHOTTARI_CYCLE or nxt["da"] not in VIMSHOTTARI_CYCLE:
            continue
        frm, to = VIMSHOTTARI_CYCLE.index(h["da"]), VIMSHOTTARI_CYCLE.index(nxt["da"])
        if frm == to:
            continue
        k = (frm + 1) % 9
        while True:
            key = f"{h['house_id']}-{VIMSHOTTARI_CYCLE[k]}"
            if key not in nl_keys:
                out.add(key)
            if k == to:
                break
            k = (k + 1) % 9
    return out


def chart_keys_by_column(chart: dict, enabled: Iterable[str] = GENERATION_COLUMNS,
                         effective_planet: Optional[Callable[[dict], dict]] = None) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    houses = chart.get("houses") or []
    if not houses:
        return out
    on = set(enabled)

    def add(col: str, bhava, planet):
        p = abbr(planet)
        if col in on and bhava and p:
            out.setdefault(col, set()).add(f"{bhava}-{p}")

    for h in houses:
        for col, field in CUSP_FIELDS:
            add(col, h.get("house_id"), h.get(field))
    nl_keys: Set[str] = set()
    for raw in chart.get("planets") or []:
        if raw.get("planet_name") == "Ascendant":
            continue
        p = {**raw, **effective_planet(raw)} if effective_planet else raw
        bhava = house_of_degree(p.get("full_degree", 0), houses) or p.get("house")
        add("PL", bhava, p.get("planet_name"))
        add("NL", bhava, p.get("nakshatra_lord"))
        add("SU", bhava, p.get("sub_lord"))
        add("SS", bhava, p.get("sub_sub_lord"))
        add("SK", bhava, p.get("sub_sub_sub_lord"))
        nl = abbr(p.get("nakshatra_lord"))
        if bhava and nl:
            nl_keys.add(f"{bhava}-{nl}")
    if "DT" in on:
        dt = da_transit_keys([{"house_id": h.get("house_id"), "da": abbr(h.get("nakshatra_lord"))} for h in houses], nl_keys)
        if dt:
            out["DT"] = dt
    return out


def _column_planet_bhavas(chart: dict, enabled: Iterable[str]) -> Dict[str, Dict[str, Set[int]]]:
    on = set(enabled)
    out: Dict[str, Dict[str, Set[int]]] = {}
    for col, field in CUSP_FIELDS:
        if col not in on:
            continue
        by_planet: Dict[str, Set[int]] = {}
        for h in chart.get("houses") or []:
            p = abbr(h.get(field))
            if h.get("house_id") and p:
                by_planet.setdefault(p, set()).add(h["house_id"])
        out[col] = by_planet
    return out


def chart_mapping_matches(chart: dict, mappings: List[dict], enabled: Iterable[str] = GENERATION_COLUMNS,
                          effective_planet=None) -> Dict[str, Set[str]]:
    """Tag -> set of positive columns responsible for its match.

    AND mappings need every rule, OR mappings any rule. Negated pairs must be absent.
    Several planet-less positive pairs form ONE multi-bhava combination: a single planet
    must occupy every listed bhava within the same cusp column (DA/BH/AN/SN).
    """
    enabled = list(enabled)
    by_col = chart_keys_by_column(chart, enabled, effective_planet)
    keys = set().union(*by_col.values()) if by_col else set()
    col_data = None

    def passes(p: dict) -> bool:
        present = f"{p['bhava']}-{p['planet']}" in keys if p.get("planet") \
            else any(k.startswith(f"{p['bhava']}-") for k in keys)
        return not present if p.get("negated") else present

    def multi_cols(bhavas: List[int]) -> List[str]:
        nonlocal col_data
        if len(bhavas) == 1:
            return [c for c, s in by_col.items() if any(k.startswith(f"{bhavas[0]}-") for k in s)]
        if col_data is None:
            col_data = _column_planet_bhavas(chart, enabled)
        return [c for c in MULTI_BHAVA_COLUMNS
                if any(all(b in occ for b in bhavas) for occ in (col_data.get(c) or {}).values())]

    out: Dict[str, Set[str]] = {}
    for m in mappings:
        pairs = m.get("pairs") or []
        if m.get("is_active") is False or not pairs:
            continue
        group = [p["bhava"] for p in pairs if not p.get("planet") and not p.get("negated")]
        others = [p for p in pairs if p.get("planet") or p.get("negated")]
        gcols = multi_cols(group) if group else []
        units = [passes(p) for p in others]
        if group:
            units.append(bool(gcols))
        ok = any(units) if m.get("match_mode") == "or" else all(units)
        if not units or not ok:
            continue
        cols = out.setdefault(m["tag"], set())
        cols.update(gcols)
        for p in others:
            if p.get("negated"):
                continue
            for c, s in by_col.items():
                if f"{p['bhava']}-{p['planet']}" in s:
                    cols.add(c)
    return out


def character_tier_by_tag(chart: dict, mappings: List[dict], effective_planet=None) -> Dict[str, int]:
    """Best tier per tag; 7 = unclassified (matched only via planet-less/NOT rules)."""
    matches = chart_mapping_matches(chart, mappings, GENERATION_COLUMNS, effective_planet)
    return {m["tag"]: min([CHARACTER_TIER[c] for c in matches.get(m["tag"], ())] or [7]) for m in mappings}
