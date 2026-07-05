
"""
Recursive Vimshottari Dasha Engine (skeleton)

IMPORTANT
---------
This file provides the recursive architecture requested.
It is intended to replace the repeated calculate_bhuktis /
calculate_antaras / calculate_pratyantaras functions.

You should plug it into your FastAPI project by importing
the functions below.

NOTE:
The remaining integration with your API endpoints and Redis
is project-specific.
"""

import datetime

TOTAL_YEARS = 120


def add_years(start, years):
    return start + datetime.timedelta(days=years * 365.25)


def circular_order_from(lord, order):
    i = order.index(lord)
    return order[i:] + order[:i]


def build_periods(parent_lord, start, end, order, years_map):
    duration = end - start
    current = start
    out = []

    for lord in circular_order_from(parent_lord, order):
        part = duration * (years_map[lord] / TOTAL_YEARS)
        finish = current + part
        out.append({
            "planet": lord,
            "start": current,
            "end": finish,
        })
        current = finish

    return out


def locate_running(periods, moment):
    for p in periods:
        if p["start"] <= moment < p["end"]:
            return p
    return periods[-1]


def remaining_fraction(period, moment):
    total = (period["end"] - period["start"]).total_seconds()
    rem = (period["end"] - moment).total_seconds()
    return rem / total if total else 0.0


def compute_running_hierarchy(
    major_lord,
    major_start,
    major_end,
    birth_dt,
    order,
    years_map,
    depth=4,
):
    """
    depth:
        1 = Mahadasha
        2 = Bhukti
        3 = Antara
        4 = Pratyantara
        5 = Sukshma
    """

    result = {
        "planet": major_lord,
        "start": major_start,
        "end": major_end,
    }

    if depth == 1:
        return result

    current_lord = major_lord
    current_start = major_start
    current_end = major_end
    current_birth = birth_dt

    labels = [
        "bhukti",
        "antara",
        "pratyantara",
        "sukshma",
    ]

    node = result

    for level in range(depth - 1):

        periods = build_periods(
            current_lord,
            current_start,
            current_end,
            order,
            years_map,
        )

        running = locate_running(periods, current_birth)

        node[labels[level]] = {
            "planet": running["planet"],
            "start": running["start"],
            "end": running["end"],
        }

        node = node[labels[level]]

        current_lord = running["planet"]
        current_start = running["start"]
        current_end = running["end"]

    return result


def flatten_periods(parent_lord, start, end, order, years_map):
    return build_periods(parent_lord, start, end, order, years_map)


def calculate_bhuktis(md_lord, md_start, md_end, order, years_map):
    return flatten_periods(md_lord, md_start, md_end, order, years_map)


def calculate_antaras(bh_lord, bh_start, bh_end, order, years_map):
    return flatten_periods(bh_lord, bh_start, bh_end, order, years_map)


def calculate_pratyantaras(an_lord, an_start, an_end, order, years_map):
    return flatten_periods(an_lord, an_start, an_end, order, years_map)


def calculate_sukshmas(pr_lord, pr_start, pr_end, order, years_map):
    return flatten_periods(pr_lord, pr_start, pr_end, order, years_map)
