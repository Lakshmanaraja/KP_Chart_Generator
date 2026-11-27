"""Generic DBA/transit windows and marriage/child-birth prediction reports."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
import re
from typing import Any

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from models.schemas import PlanetLordSummaryRequest, PredictionPeriodsRequest, PredictionReportRequest, ReportRequest
from pdf.desktop_report import render_desktop_pdf
from pdf.mobile_report import H as MOBILE_H, W as MOBILE_W, render_mobile_pdf
from services.chart_service import compute_kp_json
from services.dasa_service import calculate_antaras, calculate_bhuktis, compute_major_dasha
from services.planet_lord_summary_service import PLANET_ABBREVIATIONS, _calculate as calculate_planet_summary
from services.matcher_service import house_of_degree
from services.report_service import NoTraitsFoundError, _pdf
from services.transit_service import get_star_transits_for_cusps
from utils.date_utils import find_sub_lord_recursive, get_moon_longitude, get_nak_charan_and_pos, to_julian_day


BHAVA_GROUPS = ((1, 5, 9), (2, 6, 10), (3, 7, 11), (4, 8, 12))


def bhava_group(bhava_number: int) -> tuple[int, ...]:
    for group in BHAVA_GROUPS:
        if bhava_number in group:
            return group
    raise ValueError("bhava_number must be from 1 to 12")


def add_calendar_years(value: date, years: int) -> date:
    """Add calendar years, clamping leap day to the last day of February."""
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        return value.replace(year=target_year, day=28)


def _window(request: PredictionPeriodsRequest | PredictionReportRequest) -> tuple[date, date]:
    client_tz = timezone(timedelta(hours=request.timezone))
    start = request.from_date or datetime.now(client_tz).date()
    return start, add_calendar_years(start, request.duration_years)


def _time_parts(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        parts.append(0)
    if len(parts) != 3:
        raise ValueError("time_of_birth must use HH:MM or HH:MM:SS")
    return parts[0], parts[1], parts[2]


def _birth_times(request: PredictionPeriodsRequest | PredictionReportRequest):
    year, month, day = (int(part) for part in request.date_of_birth.split("-"))
    hour, minute, second = _time_parts(request.time_of_birth)
    local_birth = datetime(year, month, day, hour, minute, second)
    utc_birth = local_birth - timedelta(hours=request.timezone)
    julian_day = to_julian_day(
        utc_birth.year, utc_birth.month, utc_birth.day,
        utc_birth.hour, utc_birth.minute, utc_birth.second,
    )
    moon_longitude = get_moon_longitude(julian_day, request.latitude, request.longitude)
    return local_birth, moon_longitude


def _overlaps(start: datetime, end: datetime, window_start: datetime, window_end: datetime) -> bool:
    return start < window_end and end > window_start


def _period_json(period: dict[str, Any]) -> dict[str, str]:
    return {
        "start": period["start"].isoformat(),
        "end": period["end"].isoformat(),
    }


def get_dba_periods(request: PredictionPeriodsRequest) -> dict[str, Any]:
    start_date, end_date = _window(request)
    try:
        birth_datetime, moon_longitude = _birth_times(request)
        major_periods = compute_major_dasha(birth_datetime, moon_longitude)
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, f"Invalid birth details: {exc}") from None

    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date, time.min)
    bhukti_periods: list[dict[str, str]] = []
    antara_periods: list[dict[str, str]] = []
    for mahadasha in major_periods:
        bhuktis = calculate_bhuktis(mahadasha["planet"], mahadasha["start"], mahadasha["end"])
        for bhukti in bhuktis:
            if _overlaps(bhukti["start"], bhukti["end"], start, end):
                bhukti_periods.append({
                    "mahadasha": mahadasha["planet"],
                    "mahadasha_start": mahadasha["start"].isoformat(),
                    "mahadasha_end": mahadasha["end"].isoformat(),
                    "bhukthi": bhukti["planet"],
                    **_period_json(bhukti),
                })
            antaras = calculate_antaras(bhukti["planet"], bhukti["start"], bhukti["end"])
            for antara in antaras:
                if _overlaps(antara["start"], antara["end"], start, end):
                    antara_periods.append({
                        "mahadasha": mahadasha["planet"],
                        "mahadasha_start": mahadasha["start"].isoformat(),
                        "mahadasha_end": mahadasha["end"].isoformat(),
                        "bhukthi": bhukti["planet"],
                        "bhukthi_start": bhukti["start"].isoformat(),
                        "bhukthi_end": bhukti["end"].isoformat(),
                        "antara": antara["planet"],
                        **_period_json(antara),
                    })

    return {
        "from_date": start_date.isoformat(),
        "end_date_exclusive": end_date.isoformat(),
        "duration_years": request.duration_years,
        "bhava_number": request.bhava_number,
        "bhukti_periods": bhukti_periods,
        "antara_periods": antara_periods,
    }


def _transit_window(start_date: date, end_date: date, offset_hours: float) -> tuple[str, str]:
    local_zone = timezone(timedelta(hours=offset_hours))
    start_local = datetime.combine(start_date, time.min, tzinfo=local_zone)
    end_local = datetime.combine(end_date, time.min, tzinfo=local_zone)
    return (
        start_local.astimezone(timezone.utc).isoformat(),
        end_local.astimezone(timezone.utc).isoformat(),
    )


def _as_utc_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_transit_periods(request: PredictionPeriodsRequest, *, consolidate_house_periods: bool = False) -> dict[str, Any]:
    start_date, end_date = _window(request)
    try:
        chart = compute_kp_json(
            request.date_of_birth,
            ":".join(str(part).zfill(2) for part in _time_parts(request.time_of_birth)),
            request.latitude,
            request.longitude,
            request.timezone,
            request.ayanamsa,
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, f"Invalid birth details: {exc}") from None

    cusps = [
        {"house_id": house["house_id"], "full_degree": house.get("full_degree")}
        for house in chart.get("houses", [])
        if house.get("house_id") is not None and house.get("full_degree") is not None
    ]
    if len(cusps) != 12:
        raise HTTPException(422, "Could not calculate all 12 natal cusps")

    interval_start, interval_end = _transit_window(start_date, end_date, request.timezone)
    requested_start = datetime.fromisoformat(interval_start).astimezone(timezone.utc)
    requested_end = datetime.fromisoformat(interval_end).astimezone(timezone.utc)
    # Marriage reports need the beginning of a continuous bhava transit even
    # when its nakshatra rows started before the selected report window.
    query_start = interval_start
    if consolidate_house_periods:
        history_start = add_calendar_years(start_date, -5)
        query_start, _ = _transit_window(history_start, end_date, request.timezone)
    rows = get_star_transits_for_cusps(cusps, query_start, interval_end)
    group = bhava_group(request.bhava_number)
    secondary = [bhava for bhava in group if bhava != request.bhava_number]
    candidates = []
    for row in rows:
        actual_bhava = row.get("bhava")
        if actual_bhava not in group:
            continue
        try:
            row_start = _as_utc_datetime(row["date"])
            row_end = _as_utc_datetime(row["exit_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if row_start >= requested_end or row_end <= requested_start:
            # Keep pre-window rows during the history scan; they may join a
            # continuous bhava period that overlaps the requested window.
            if not (consolidate_house_periods and row_end <= requested_start):
                continue
        candidates.append({
            **row,
            "actual_bhava": actual_bhava,
            "bhava_type": "primary" if actual_bhava == request.bhava_number else "secondary",
            "primary_bhava": request.bhava_number,
            "secondary_bhavas": secondary,
        })
    filtered = (
        _consolidate_bhava_transits(candidates, requested_start, requested_end)
        if consolidate_house_periods else candidates
    )
    return {
        "from_date": start_date.isoformat(),
        "end_date_exclusive": end_date.isoformat(),
        "duration_years": request.duration_years,
        "bhava_number": request.bhava_number,
        "bhava_group": list(group),
        "secondary_bhavas": secondary,
        "transit_periods": filtered,
    }



def _consolidate_bhava_transits(
    rows: list[dict[str, Any]], window_start: datetime, window_end: datetime
) -> list[dict[str, Any]]:
    """Join adjacent nakshatra rows into continuous planet-in-bhava periods."""
    grouped: dict[tuple[str, int], list[tuple[datetime, datetime, dict[str, Any]]]] = {}
    for row in rows:
        try:
            start = _as_utc_datetime(row["date"])
            end = _as_utc_datetime(row["exit_date"])
            house = int(row["actual_bhava"])
        except (KeyError, TypeError, ValueError):
            continue
        if end > start:
            grouped.setdefault((str(row.get("planet") or ""), house), []).append((start, end, row))

    merged: list[dict[str, Any]] = []
    for (planet, house), intervals in grouped.items():
        intervals.sort(key=lambda item: (item[0], item[1]))
        current_start = current_end = None
        current = None
        current_exit_degree = None
        stars: set[str] = set()

        def append_current():
            if current_start is None or current_end is None or current is None:
                return
            if current_start < window_end and current_end > window_start:
                merged.append({
                    **current,
                    "planet": planet,
                    "actual_bhava": house,
                    "date": current_start.isoformat(),
                    "exit_date": current_end.isoformat(),
                    "exit_degree": current_exit_degree,
                    "stars": sorted(stars),
                })

        for start, end, row in intervals:
            if current_start is None:
                current_start, current_end, current = start, end, row
                current_exit_degree = row.get("exit_degree")
                stars = {str(row.get("star"))} if row.get("star") else set()
            elif start <= current_end:
                if end > current_end:
                    current_end = end
                    current_exit_degree = row.get("exit_degree")
                if row.get("star"):
                    stars.add(str(row["star"]))
            else:
                append_current()
                current_start, current_end, current = start, end, row
                current_exit_degree = row.get("exit_degree")
                stars = {str(row.get("star"))} if row.get("star") else set()
        append_current()

    return sorted(merged, key=lambda row: (_as_utc_datetime(row["date"]), row["planet"], row["actual_bhava"]))

def _report_cover(request: PredictionReportRequest, kind: str = "report") -> bytes:
    client = {
        "name": request.name,
        "date_of_birth": request.date_of_birth,
        "time_of_birth": request.time_of_birth,
        "place": request.place,
        "timezone": f"UTC{'+' if request.timezone >= 0 else ''}{request.timezone:g}",
    }
    if kind == "marriage":
        if request.version == "desktop":
            return render_desktop_pdf([], client, "marriage")
        return render_mobile_pdf([], client, "marriage")

    report_request = ReportRequest(
        name=request.name,
        date_of_birth=request.date_of_birth,
        time_of_birth=request.time_of_birth,
        latitude=request.latitude,
        longitude=request.longitude,
        timezone=request.timezone,
        place=request.place,
        ayanamsa=request.ayanamsa,
        version=request.version,
        text_source="report",
        report_type="character_assessment",
        gender=request.gender,
        extra_tags=request.extra_tags,
        topics=request.topics,
        include_sn=request.include_sn,
        include_sk=request.include_sk,
    )
    try:
        return _pdf(report_request)
    except NoTraitsFoundError:
        if request.version == "desktop":
            return render_desktop_pdf([], client, "report")
        return render_mobile_pdf([], client, "report")



def _prediction_significators(
    request: PredictionReportRequest | PredictionPeriodsRequest,
    bhavas: tuple[int, ...],
) -> dict[str, Any]:
    """Classify natal planets by house location and cuspal summary links."""
    try:
        chart = compute_kp_json(
            request.date_of_birth,
            ":".join(str(part).zfill(2) for part in _time_parts(request.time_of_birth)),
            request.latitude,
            request.longitude,
            request.timezone,
            request.ayanamsa,
        )
        options = PlanetLordSummaryRequest(
            date_of_birth=request.date_of_birth,
            time_of_birth=request.time_of_birth,
            latitude=request.latitude,
            longitude=request.longitude,
            timezone=request.timezone,
            ayanamsa=request.ayanamsa,
        )
        summary = calculate_planet_summary({"cusps": chart.get("houses", []), "planets": chart.get("planets", [])}, options)
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(422, f"Invalid birth details: {exc}") from None

    by_bhava: dict[int, dict[str, list[str]]] = {}
    planet_rows = {row["planet_name"]: row for row in summary["rows"]}
    chart_planets = {planet.get("planet_name"): planet for planet in chart.get("planets", [])}
    combined_values: dict[str, str] = {}
    cusp_rows = chart.get("houses", [])
    for planet, row in planet_rows.items():
        chart_planet = chart_planets.get(planet)
        if chart_planet:
            combined_values[planet] = _time_science_combined_value(
                planet,
                chart_planet,
                cusp_rows,
                row.get("location"),
            )

    for bhava in bhavas:
        located: list[str] = []
        interlinked: list[str] = []
        for row in summary["rows"]:
            planet = str(row["planet_name"])
            if row.get("location") == bhava:
                located.append(planet)
                continue
            linked = {
                int(value)
                for key in ("nl_bhavas", "su_bhavas", "ss_bhavas", "sk_bhavas")
                for value in (row.get(key) or [])
            }
            if bhava in linked:
                interlinked.append(planet)
        by_bhava[bhava] = {"location": located, "cuspal_interlink": interlinked}
    return {"bhavas": by_bhava, "cusps": cusp_rows, "combined_values": combined_values}


def _time_science_combined_value(
    planet: str,
    planet_data: dict[str, Any],
    cusps: list[dict[str, Any]],
    own_house: int | str | None,
) -> str:
    """Format PL-NL-SU-SS-SK like the Time Science Combined row in Dasa Analysis."""
    roles = (
        (planet, None),
        (planet_data.get("nakshatra_lord"), None),
        (planet_data.get("sub_lord"), "sub_lord"),
        (planet_data.get("sub_sub_lord"), "sub_sub_lord"),
        (planet_data.get("sub_sub_sub_lord"), "sub_sub_sub_lord"),
    )
    values: list[str] = []
    for index, (role, cusp_column) in enumerate(roles):
        if not role:
            continue
        bhavas = (
            sorted({int(cusp["house_id"]) for cusp in cusps
                    if cusp.get(cusp_column) == role and cusp.get("house_id") is not None})
            if cusp_column else []
        )
        if not bhavas and own_house is not None:
            try:
                bhavas = [int(own_house)]
            except (TypeError, ValueError):
                bhavas = []
        abbreviation = PLANET_ABBREVIATIONS.get(str(role), str(role))
        if index == 0:
            abbreviation = abbreviation.upper()
        values.append(f"{abbreviation}({','.join(map(str, bhavas))})")
    return "-".join(values)


def _transit_combined_value(planet: str, degree: Any, cusps: list[dict[str, Any]]) -> str | None:
    """Build a Time Science combined value from a transit planet's boundary degree."""
    if degree is None or not planet:
        return None
    try:
        degree = float(degree)
        _, _, nakshatra_lord, _, position_in_nakshatra, nakshatra_size = get_nak_charan_and_pos(degree)
        sub_lords = find_sub_lord_recursive(
            position_in_nakshatra, nakshatra_size, nakshatra_lord, levels=3
        )
        own_house = house_of_degree(degree, cusps)
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    planet_data = {
        "nakshatra_lord": nakshatra_lord,
        "sub_lord": sub_lords[0] if len(sub_lords) > 0 else None,
        "sub_sub_lord": sub_lords[1] if len(sub_lords) > 1 else None,
        "sub_sub_sub_lord": sub_lords[2] if len(sub_lords) > 2 else None,
    }
    return _time_science_combined_value(planet, planet_data, cusps, own_house)


def _dba_planet_periods(
    dba: dict[str, Any],
    selected_planets: set[str],
    combined_values: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return matching periods plus date-hidden ancestors needed to show their hierarchy."""
    records: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    parents: dict[tuple[str, str, str, str], tuple[str, str, str, str]] = {}

    def ensure(level: str, planet: Any, start: Any, end: Any) -> tuple[str, str, str, str] | None:
        if not planet or not start or not end:
            return None
        raw_start, raw_end = str(start), str(end)
        key = (level, str(planet), raw_start, raw_end)
        record = records.setdefault(key, {
            "level": level,
            "planet": PLANET_ABBREVIATIONS.get(str(planet), str(planet)),
            "start": raw_start[:10],
            "end": raw_end[:10],
            "show_dates": str(planet) in selected_planets,
            "combined_value": combined_values.get(str(planet)) if combined_values and str(planet) in selected_planets else None,
        })
        record["show_dates"] = record["show_dates"] or str(planet) in selected_planets
        return key

    for row in dba.get("bhukti_periods", []):
        dasa = ensure("Dasa", row.get("mahadasha"), row.get("mahadasha_start"), row.get("mahadasha_end"))
        bhukthi = ensure("Bhukthi", row.get("bhukthi"), row.get("start"), row.get("end"))
        if dasa and bhukthi:
            parents[bhukthi] = dasa

    for row in dba.get("antara_periods", []):
        dasa = ensure("Dasa", row.get("mahadasha"), row.get("mahadasha_start"), row.get("mahadasha_end"))
        bhukthi = ensure("Bhukthi", row.get("bhukthi"), row.get("bhukthi_start"), row.get("bhukthi_end"))
        antara = ensure("Antara", row.get("antara"), row.get("start"), row.get("end"))
        if dasa and bhukthi:
            parents[bhukthi] = dasa
        if bhukthi and antara:
            parents[antara] = bhukthi

    included = {key for key, row in records.items() if row["show_dates"]}
    for key in tuple(included):
        child = key
        while child in parents:
            parent = parents[child]
            parent_start = date.fromisoformat(records[parent]["start"])
            parent_end = date.fromisoformat(records[parent]["end"])
            child_start = date.fromisoformat(records[child]["start"])
            child_end = date.fromisoformat(records[child]["end"])
            if parent_start <= child_start and parent_end >= child_end:
                included.add(parent)
                child = parent
            else:
                break

    level_order = {"Dasa": 0, "Bhukthi": 1, "Antara": 2}
    return sorted(
        (records[key] for key in included),
        key=lambda row: (row["start"], level_order[row["level"]], row["planet"], row["end"]),
    )


DBA_LEVEL_RANK = {"Dasa": 1, "Bhukthi": 2, "Antara": 3}


def _nest_dba_periods(entries: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Nest periods under their deepest date-enclosing higher-level period."""
    ordered = sorted(entries, key=lambda row: (
        date.fromisoformat(row["start"]), DBA_LEVEL_RANK[row["level"]],
        date.fromisoformat(row["end"]), row["planet"],
    ))
    roots: list[dict[str, Any]] = []
    prior: list[dict[str, Any]] = []
    for entry in ordered:
        node = {**entry, "children": [], "depth": 0}
        child_start, child_end = date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"])
        parents = [candidate for candidate in prior
                   if DBA_LEVEL_RANK[candidate["level"]] < DBA_LEVEL_RANK[entry["level"]]
                   and date.fromisoformat(candidate["start"]) <= child_start
                   and date.fromisoformat(candidate["end"]) >= child_end]
        if parents:
            parent = max(parents, key=lambda candidate: (
                DBA_LEVEL_RANK[candidate["level"]],
                -(date.fromisoformat(candidate["end"]) - date.fromisoformat(candidate["start"])).days,
            ))
            node["depth"] = parent["depth"] + 1
            parent["children"].append(node)
        else:
            roots.append(node)
        prior.append(node)

    def sort_tree(nodes: list[dict[str, Any]]) -> None:
        nodes.sort(key=lambda row: (date.fromisoformat(row["start"]), DBA_LEVEL_RANK[row["level"]], date.fromisoformat(row["end"]), row["planet"]))
        for node in nodes:
            sort_tree(node["children"])

    sort_tree(roots)
    return roots


class DBAHierarchyRow(Flowable):
    """One compact DBA row with a date column and nested-level guide."""
    INDENT = 13

    def __init__(self, row: dict[str, Any], font_size: float, tick_color: str = "#16A34A"):
        super().__init__()
        self.row = row
        self.font_size = font_size
        self.tick_color = tick_color
        self.combined_value = row.get("combined_value")
        self.summary_font_size = max(4.8, font_size - 1.4)
        self.row_height = max(15, int(self.font_size + 6))
        if self.combined_value:
            self.row_height += self.summary_font_size + 2

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        self.height = self.row_height
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        depth = int(self.row["depth"])
        baseline = (
            self.summary_font_size + 3
            if self.combined_value else (self.height - self.font_size) / 2 + 1
        )
        long_period = self.row.get("show_dates", True) and _period_exceeds_six_months(
            self.row.get("start"), self.row.get("end")
        )
        if depth:
            canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
            canvas.setLineWidth(1.1)
            canvas.line(depth * self.INDENT - 4, 1, depth * self.INDENT - 4, self.height - 1)

        emphasis_color = colors.HexColor("#0B0F19") if long_period else colors.HexColor("#1E293B")
        show_dates = self.row.get("show_dates", True)
        if not show_dates:
            emphasis_color = colors.HexColor("#64748B")
        label_font = "Helvetica-Bold" if long_period else "Helvetica"
        canvas.setFillColor(emphasis_color)
        canvas.setFont(label_font, self.font_size)
        label = f"{self.row['planet']} — {self.row['level']}"
        label_x = depth * self.INDENT + 2
        canvas.drawString(label_x, baseline, label)
        if self.combined_value:
            canvas.setFillColor(colors.HexColor("#64748B"))
            canvas.setFont("Helvetica", self.summary_font_size)
            canvas.drawString(label_x, 1, self.combined_value)
        if not show_dates:
            canvas.setFillColor(colors.HexColor("#64748B"))
            canvas.setFont("Helvetica", self.font_size)
            canvas.drawRightString(self.width - 2, baseline, "—")
            return

        if long_period:
            tick_x = label_x + canvas.stringWidth(label, label_font, self.font_size) + 3
            tick_y = baseline + self.font_size * 0.35
            canvas.setStrokeColor(colors.HexColor(self.tick_color))
            canvas.setLineWidth(1.5)
            canvas.line(tick_x, tick_y, tick_x + 2, tick_y - 2)
            canvas.line(tick_x + 2, tick_y - 2, tick_x + 6, tick_y + 3)

        # Courier keeps every digit aligned; draw a vector arrow so it is not
        # dependent on a platform font's arrow glyph.
        date_size = max(7.2, self.font_size - 0.8)
        start, end = self.row["start"], self.row["end"]
        right_edge = self.width - 2
        canvas.setFont("Courier-Bold" if long_period else "Courier", date_size)
        canvas.setFillColor(emphasis_color if long_period else colors.HexColor("#475569"))
        canvas.drawRightString(right_edge, baseline, end)
        end_width = canvas.stringWidth(end, "Courier", date_size)
        arrow_center = right_edge - end_width - 7
        canvas.drawRightString(arrow_center - 5, baseline, start)
        canvas.setStrokeColor(colors.HexColor("#64748B"))
        canvas.setLineWidth(0.8)
        arrow_y = baseline + date_size * 0.34
        canvas.line(arrow_center - 2.5, arrow_y, arrow_center + 2.5, arrow_y)
        canvas.line(arrow_center + 0.5, arrow_y + 2, arrow_center + 2.5, arrow_y)
        canvas.line(arrow_center + 0.5, arrow_y - 2, arrow_center + 2.5, arrow_y)


def _render_dba_tree(
    entries: list[dict[str, str]], font_size: float, small_style, tick_color: str = "#16A34A"
):
    if not entries:
        return [Paragraph("No matching periods.", small_style)]
    rows: list[DBAHierarchyRow] = []

    def flatten(nodes):
        for node in nodes:
            rows.append(DBAHierarchyRow(node, font_size, tick_color))
            flatten(node["children"])

    flatten(_nest_dba_periods(entries))
    return rows

def _parse_event_date(value: Any) -> date | None:
    """Normalize date, datetime, or ISO text to a calendar date in UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.date()


def _period_exceeds_six_months(start_value: Any, end_value: Any) -> bool:
    start_date = _parse_event_date(start_value)
    end_date = _parse_event_date(end_value)
    if start_date is None or end_date is None:
        return False
    month_index = start_date.year * 12 + start_date.month - 1 + 6
    threshold_year, month0 = divmod(month_index, 12)
    threshold_month = month0 + 1
    threshold_day = min(start_date.day, monthrange(threshold_year, threshold_month)[1])
    return end_date > date(threshold_year, threshold_month, threshold_day)


class TransitPlanetCell(Flowable):
    """Planet cell with a small green check for transit periods over six months."""

    def __init__(
        self, planet: str, start: Any, end: Any, font_size: float, tick_color: str = "#16A34A"
    ):
        super().__init__()
        self.planet = planet
        self.long_period = _period_exceeds_six_months(start, end)
        self.font_size = font_size
        self.tick_color = tick_color
        self.height = font_size + 2

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(colors.HexColor("#1E293B"))
        canvas.setFont("Helvetica", self.font_size)
        canvas.drawString(0, 1, self.planet)
        if self.long_period:
            x = canvas.stringWidth(self.planet, "Helvetica", self.font_size) + 3
            y = self.height / 2 + 1
            canvas.setStrokeColor(colors.HexColor(self.tick_color))
            canvas.setLineWidth(1.5)
            canvas.line(x, y, x + 2, y - 2)
            canvas.line(x + 2, y - 2, x + 6, y + 3)


class MarriageSummaryRow(Flowable):
    """Date-first stacked summary row with a tick and a subtle divider."""

    def __init__(self, item: dict[str, str], is_mobile: bool):
        super().__init__()
        self.item = item
        self.is_mobile = is_mobile
        self.date_size = 10.5 if is_mobile else 12
        self.detail_size = 8.8
        self.height = self.date_size + self.detail_size + 22

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        date_baseline = self.height - self.date_size - 3
        canvas.setStrokeColor(colors.HexColor(self.item["tick_color"]))
        canvas.setLineWidth(1.6)
        canvas.line(0, date_baseline + self.date_size * .25 + 2, 2.3, date_baseline + self.date_size * .25)
        canvas.line(2.3, date_baseline + self.date_size * .25, 6.8, date_baseline + self.date_size * .25 + 5)
        date_color = "#64748B" if self.item.get("time_horizon") == "Past" else "#0F172A"
        canvas.setFillColor(colors.HexColor(date_color))
        canvas.setFont("Helvetica-Bold", self.date_size)
        start_label = date.fromisoformat(self.item["start"]).strftime("%d %b %Y")
        end_label = date.fromisoformat(self.item["end"]).strftime("%d %b %Y")
        date_x = 12
        canvas.drawString(date_x, date_baseline, start_label)
        start_width = canvas.stringWidth(start_label, "Helvetica-Bold", self.date_size)
        arrow_start = date_x + start_width + 5
        arrow_y = date_baseline + self.date_size * .35
        canvas.setStrokeColor(colors.HexColor("#334155"))
        canvas.setLineWidth(.8)
        canvas.line(arrow_start, arrow_y, arrow_start + 8, arrow_y)
        canvas.line(arrow_start + 5.5, arrow_y + 2.5, arrow_start + 8, arrow_y)
        canvas.line(arrow_start + 5.5, arrow_y - 2.5, arrow_start + 8, arrow_y)
        canvas.drawString(arrow_start + 12, date_baseline, end_label)

        detail_y = 5
        horizon = self.item.get("time_horizon", "Future")
        if horizon == "Active Window" and self.item["tick_color"] == "#D4A017":
            badge_bg, badge_fg = "#FEF3C7", "#92400E"
        else:
            horizon_style = {
                "Past": ("#F1F5F9", "#94A3B8"),
                "Active Window": ("#DCFCE7", "#047857"),
                "Future": ("#E2E8F0", "#475569"),
            }
            badge_bg, badge_fg = horizon_style[horizon]
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", self.detail_size)
        detail = f"{self.item['planet']} · {self.item['kind']}"
        canvas.drawString(0, detail_y, detail)
        tag_size = 7.2 if self.is_mobile else 8
        tag = horizon
        tag_width = canvas.stringWidth(tag, "Helvetica-Bold", tag_size)
        tag_x = self.width - tag_width - 10
        canvas.setFillColor(colors.HexColor(badge_bg))
        canvas.roundRect(tag_x - 4, detail_y - 2, tag_width + 8, tag_size + 4, 2, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor(badge_fg))
        canvas.setFont("Helvetica-Bold", tag_size)
        canvas.drawString(tag_x, detail_y, tag)

        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        canvas.setLineWidth(0.55)
        canvas.line(0, 0, self.width, 0)


def _merge_transit_periods(
    rows: list[dict[str, Any]],
    bhava: int,
    selected_planets: set[str],
    window_start: date | None = None,
    window_end_exclusive: date | None = None,
    include_boundary_values: bool = False,
) -> list[dict[str, Any]]:
    """Merge adjacent calendar-day intervals for the same planet and bhava."""
    grouped: dict[str, list[tuple[date, date, dict[str, Any]]]] = {}
    for row in rows:
        planet = row.get("planet")
        if planet not in selected_planets or row.get("actual_bhava", row.get("bhava")) != bhava:
            continue
        start = _parse_event_date(row.get("date"))
        end = _parse_event_date(row.get("exit_date"))
        if start is None or end is None or end < start:
            continue
        if window_end_exclusive is not None and start >= window_end_exclusive:
            continue
        if window_start is not None and end < window_start:
            continue
        grouped.setdefault(planet, []).append((start, end, row))

    merged: list[dict[str, str]] = []
    for planet, intervals in grouped.items():
        intervals.sort(key=lambda interval: (
            interval[0], interval[1], _as_utc_datetime(interval[2].get("date")),
        ))
        current_start = current_end = None
        start_row = end_row = None

        def append_current():
            if current_start is None or current_end is None or start_row is None:
                return
            item = {
                "planet": PLANET_ABBREVIATIONS.get(planet, planet),
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
            }
            if include_boundary_values:
                item.update({
                    "planet_name": planet,
                    "start_degree": start_row.get("entry_degree"),
                    "end_degree": end_row.get("exit_degree") if end_row else None,
                })
            merged.append(item)

        for start, end, row in intervals:
            if current_start is None:
                current_start, current_end = start, end
                start_row = end_row = row
            elif start <= current_end + timedelta(days=1):
                if end > current_end or (
                    end == current_end and end_row is not None
                    and _as_utc_datetime(row.get("exit_date")) > _as_utc_datetime(end_row.get("exit_date"))
                ):
                    current_end = max(current_end, end)
                    end_row = row
            else:
                append_current()
                current_start, current_end = start, end
                start_row = end_row = row
        append_current()
    return sorted(merged, key=lambda row: (row["start"], row["planet"], row["end"]))


def _render_period_table(
    entries: list[dict[str, str]],
    headers: list[str],
    columns: list[str],
    widths: list[float],
    usable_width: float,
    cell,
    small_style,
    mark_long_periods: bool = False,
    mark_font_size: float = 7,
    mark_tick_color: str = "#16A34A",
    boundary_font_size: float | None = None,
    row_padding: float = 3,
):
    if not entries:
        return Paragraph("No matching periods.", small_style)
    data = [[cell(header) for header in headers]]
    for row in entries:
        rendered_row = []
        for column in columns:
            if mark_long_periods and column == "planet":
                rendered_row.append(TransitPlanetCell(
                    str(row.get(column, "")), row.get("start"), row.get("end"), mark_font_size, mark_tick_color
                ))
            elif column in {"start", "end"} and row.get(f"{column}_combined_value"):
                summary_size = boundary_font_size or max(4.8, mark_font_size - 1.4)
                summary = re.sub(r"(\([^)]*\))", r"<nobr>\1</nobr>", str(row[f"{column}_combined_value"]))
                rendered_row.append(cell(
                    f"{row.get(column, '')}<br/><font size=\"{summary_size}\" color=\"#64748B\">{summary}</font>"
                ))
            else:
                rendered_row.append(cell(row.get(column, "")))
        data.append(rendered_row)
    table = LongTable(data, colWidths=[width * usable_width for width in widths], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), row_padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), row_padding),
    ]))
    return table


def _marriage_significator_story(
    significators, dba, transits, level1_style, level2_style, level3_style,
    subheading_style, cell_style, small_style, usable_width, body_size, cell,
):
    story = []
    bhava_significators = significators["bhavas"]
    combined_values = significators["combined_values"]
    natal_cusps = significators["cusps"]
    target_bhavas = (7, 3, 11)
    transit_rows = transits.get("transit_periods", [])
    slow_planets = {"Jupiter", "Saturn", "Rahu", "Ketu"}
    location_transit_intervals: dict[int, set[tuple[str, str, str]]] = {}

    def add_category(bhava: int, label: str, planets: list[str]):
        tick_color = "#16A34A" if bhava == 7 else "#D4A017"
        is_cuspal_interlink = label == "Cuspal Interlink"
        story.append(Paragraph(f"Bhava {bhava} — {label}", level2_style))
        if not planets:
            story.append(Paragraph("No planets in this category.", small_style))
            return
        selected = set(planets)
        story.append(Paragraph("Transit", level3_style))
        # Slow-moving transits are included by actual bhava and requested
        # window even when that planet is not among the natal signifiers for
        # this Location/Cuspal Interlink subsection.
        win_start = _parse_event_date(transits.get("from_date"))
        win_end_excl = _parse_event_date(transits.get("end_date_exclusive"))
        transit_entries = _merge_transit_periods(
            transit_rows,
            bhava,
            selected | slow_planets,
            window_start=win_start,
            window_end_exclusive=win_end_excl,
            include_boundary_values=is_cuspal_interlink,
        )
        def full_planet_name(row):
            if row.get("planet_name"):
                return row["planet_name"]
            return next(
                (name for name, abbreviation in PLANET_ABBREVIATIONS.items()
                 if abbreviation == row["planet"]), row["planet"]
            )

        if label == "Location":
            location_transit_intervals[bhava] = {
                (full_planet_name(row), row["start"], row["end"])
                for row in transit_entries
            }
        elif is_cuspal_interlink:
            previously_listed = location_transit_intervals.get(bhava, set())
            transit_entries = [
                row for row in transit_entries
                if (full_planet_name(row), row["start"], row["end"])
                not in previously_listed
            ]
        if is_cuspal_interlink:
            for row in transit_entries:
                planet_name = row.get("planet_name")
                if planet_name:
                    row["start_combined_value"] = _transit_combined_value(
                        planet_name, row.get("start_degree"), natal_cusps
                    )
                    row["end_combined_value"] = _transit_combined_value(
                        planet_name, row.get("end_degree"), natal_cusps
                    )
        slow = [row for row in transit_entries if row["planet"] in {PLANET_ABBREVIATIONS.get(name, name) for name in slow_planets}]
        other = [row for row in transit_entries if row not in slow]
        for subheading, group in (("Slow-moving planets", slow), ("Other planets", other)):
            story.append(Paragraph(subheading, subheading_style))
            story.append(_render_period_table(
                group,
                ["Planet", "From", "To"],
                ["planet", "start", "end"],
                [0.30, 0.35, 0.35],
                usable_width,
                cell,
                small_style,
                mark_long_periods=True,
                mark_font_size=body_size,
                mark_tick_color=tick_color,
                boundary_font_size=max(4.8, body_size - 1.4),
                row_padding=4.5 if body_size < 9 else 3,
            ))
        story.append(Spacer(1, 2 * mm))

        story.append(Paragraph("Vimshottari Dasa", level3_style))
        entries = _dba_planet_periods(
            dba,
            selected,
            combined_values if is_cuspal_interlink else None,
        )
        story.extend(_render_dba_tree(entries, body_size, small_style, tick_color))
        story.append(Spacer(1, 1.5 * mm))

    story.append(Paragraph("Primary Significators", level1_style))
    for category in ("location", "cuspal_interlink"):
        label = "Location" if category == "location" else "Cuspal Interlink"
        add_category(7, label, bhava_significators[7][category])
    story.append(Paragraph("Secondary Significators", level1_style))
    for bhava in target_bhavas[1:]:
        for category in ("location", "cuspal_interlink"):
            label = "Location" if category == "location" else "Cuspal Interlink"
            add_category(bhava, label, bhava_significators[bhava][category])
    return story


def _generic_period_story(dba, transits, section_style, cell_style, small_style, usable_width, cell):
    story = [Paragraph("DBA Periods", section_style)]
    bhuktis = dba.get("bhukti_periods", [])
    if bhuktis:
        data = [[cell("Dasa"), cell("Bhukthi"), cell("From"), cell("To")]]
        data.extend([[cell(row["mahadasha"]), cell(row["bhukthi"]), cell(row["start"][:10]), cell(row["end"][:10])] for row in bhuktis])
        widths = [usable_width * .19, usable_width * .22, usable_width * .30, usable_width * .29]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([table, Spacer(1, 2 * mm)])
    else:
        story.append(Paragraph("No Bhukthi periods overlap this window.", small_style))
    antaras = dba.get("antara_periods", [])
    story.append(Paragraph("Antara Periods", section_style))
    if antaras:
        data = [[cell("Dasa"), cell("Bhukthi"), cell("Antara"), cell("From"), cell("To")]]
        data.extend([[cell(row["mahadasha"]), cell(row["bhukthi"]), cell(row["antara"]), cell(row["start"][:10]), cell(row["end"][:10])] for row in antaras])
        widths = [usable_width * .16, usable_width * .18, usable_width * .20, usable_width * .23, usable_width * .23]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(table)
    else:
        story.append(Paragraph("No Antara periods overlap this window.", small_style))
    story.extend([Spacer(1, 2 * mm), Paragraph("Transit Periods", section_style)])
    rows = transits.get("transit_periods", [])
    if rows:
        data = [[cell("Planet"), cell("Star"), cell("Bhava"), cell("From"), cell("To")]]
        data.extend([[cell(row["planet"]), cell(row["star"]), cell(f"{row['actual_bhava']} ({row['bhava_type']})"), cell(str(row["date"])[:10]), cell(str(row["exit_date"])[:10])] for row in rows])
        widths = [usable_width * .16, usable_width * .25, usable_width * .20, usable_width * .195, usable_width * .195]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(table)
    else:
        story.append(Paragraph("No matching transit periods overlap this window.", small_style))
    return story


def _marriage_summary_items(significators, dba, transits, reference_date: date) -> list[dict[str, str]]:
    """Collect only long, tick-worthy DBA and transit periods for the final page."""
    items: dict[tuple[str, str, str, str], dict[str, str]] = {}
    bhava_significators = significators["bhavas"]
    transit_rows = transits.get("transit_periods", [])
    slow_planets = {"Jupiter", "Saturn", "Rahu", "Ketu"}
    window_start = _parse_event_date(transits.get("from_date"))
    window_end = _parse_event_date(transits.get("end_date_exclusive"))

    present_end_date = add_calendar_years(reference_date, 1)

    def add(
        planet: str, kind: str, start: str, end: str, tick_color: str,
        context: str | None = None,
    ) -> None:
        if not _period_exceeds_six_months(start, end):
            return
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        if end_date < reference_date:
            time_horizon = "Past"
        elif start_date <= present_end_date and end_date >= reference_date:
            time_horizon = "Active Window"
        else:
            time_horizon = "Future"
        display_kind = f"{kind} ({context})" if context else kind
        key = (planet, kind, start, end)
        existing = items.get(key)
        # A primary (green) match takes precedence over a secondary (orange)
        # match when the same period appears in more than one bhava group.
        if existing is None or tick_color == "#16A34A":
            items[key] = {
                "planet": planet,
                "kind": display_kind,
                "start": start,
                "end": end,
                "tick_color": tick_color,
                "time_horizon": time_horizon,
            }

    for bhava in (7, 3, 11):
        tick_color = "#16A34A" if bhava == 7 else "#D4A017"
        for category in ("location", "cuspal_interlink"):
            selected = set(bhava_significators[bhava][category])
            if not selected:
                continue
            for row in _dba_planet_periods(dba, selected):
                if row.get("show_dates"):
                    add(
                        row["planet"], "DBA", row["start"], row["end"],
                        tick_color, row.get("level"),
                    )

            for row in _merge_transit_periods(
                transit_rows,
                bhava,
                selected | slow_planets,
                window_start=window_start,
                window_end_exclusive=window_end,
            ):
                add(row["planet"], "Transit", row["start"], row["end"], tick_color)

    return sorted(items.values(), key=lambda row: (
        row["start"], row["planet"], row["kind"], row["end"]
    ))


def _marriage_summary_story(
    items, dba, title_style, small_style, body_size, is_mobile
):
    story = [Paragraph("Marriage Date Prediction", title_style)]

    period_end = date.fromisoformat(dba["end_date_exclusive"]) - timedelta(days=1)
    research_style = ParagraphStyle(
        "MarriageResearchWindow", parent=small_style,
        fontName="Helvetica-Bold", fontSize=body_size,
        leading=body_size + 2.5, textColor=colors.HexColor("#072A7D"),
        backColor=colors.HexColor("#EFF6FF"), borderColor=colors.HexColor("#BFDBFE"),
        borderWidth=.6, borderPadding=6, spaceAfter=3 * mm,
    )
    research_start = date.fromisoformat(dba["from_date"]).strftime("%d %b %Y")
    research_end_label = period_end.strftime("%d %b %Y")
    story.append(Paragraph(
        f"Research period: {research_start} to {research_end_label}",
        research_style,
    ))
    story.append(Spacer(1, 3 * mm))

    def append_tick_section(
        label: str, tick_color: str, rows: list[dict[str, str]], space_before: float
    ) -> None:
        heading_style = ParagraphStyle(
            f"Marriage{label.replace(' ', '')}Heading", parent=small_style,
            fontName="Helvetica-Bold", fontSize=body_size + 1,
            leading=body_size + 3, textColor=colors.HexColor(tick_color),
            spaceBefore=space_before, spaceAfter=2.5 * mm, keepWithNext=True,
        )
        story.append(Paragraph(label, heading_style))
        if not rows:
            story.append(Paragraph("No matching periods.", small_style))
            story.append(Spacer(1, 2 * mm))
            return
        for row in rows:
            story.append(MarriageSummaryRow(row, is_mobile))
            story.append(Spacer(1, 2.2 * mm if is_mobile else 2.8 * mm))

    green_items = [row for row in items if row["tick_color"] == "#16A34A"]
    orange_items = [row for row in items if row["tick_color"] != "#16A34A"]
    append_tick_section("Strong Alignment Windows (>70% possibility)", "#16A34A", green_items, 1.5 * mm)
    story.append(PageBreak())
    story.extend([
        Paragraph("Marriage Date Prediction", title_style),
        Paragraph(
            f"Research period: {research_start} to {research_end_label}",
            research_style,
        ),
        Spacer(1, 3 * mm),
    ])
    append_tick_section("Moderate Alignment Windows (>50% possibility)", "#D4A017", orange_items, 5 * mm)
    return story

def _prediction_pdf_page(
    dba: dict[str, Any],
    transits: dict[str, Any],
    title: str,
    version: str,
    significators: dict[int, dict[str, list[str]]] | None = None,
    reference_date: date | None = None,
) -> bytes:
    buffer = BytesIO()
    is_mobile = version == "mobile"
    page_size = (MOBILE_W, MOBILE_H) if is_mobile else A4
    margin = 7.5 * mm if is_mobile else 16 * mm
    body_size = 8.6 if is_mobile else 9
    usable_width = page_size[0] - 2 * margin
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PredictionTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=14.5 if is_mobile else 17, leading=17 if is_mobile else 20,
        textColor=colors.HexColor("#072A7D"), alignment=1, spaceAfter=5 * mm,
        keepWithNext=True,
    )
    section_style = ParagraphStyle(
        "PredictionSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=10.5 if is_mobile else 12, leading=13 if is_mobile else 14,
        textColor=colors.HexColor("#1A659E"), spaceBefore=2 * mm, spaceAfter=1.5 * mm,
        keepWithNext=True,
    )
    level1_style = ParagraphStyle(
        "MarriageLevel1", parent=section_style, fontSize=body_size + (3.2 if is_mobile else 4),
        leading=body_size + (5.2 if is_mobile else 6), textColor=colors.HexColor("#072A7D"),
        spaceBefore=3.5 * mm, spaceAfter=1.5 * mm, keepWithNext=True,
    )
    level2_style = ParagraphStyle(
        "MarriageLevel2", parent=section_style, fontSize=body_size + (1.2 if is_mobile else 1.5),
        leading=body_size + (3.2 if is_mobile else 3.5), textColor=colors.HexColor("#1E40AF"),
        spaceBefore=2.5 * mm, spaceAfter=1 * mm, keepWithNext=True,
    )
    level3_style = ParagraphStyle(
        "MarriageLevel3", parent=section_style, fontSize=body_size + (0.2 if is_mobile else 0.5),
        leading=body_size + (2.2 if is_mobile else 2.5), textColor=colors.HexColor("#0F766E"),
        spaceBefore=2 * mm, spaceAfter=1 * mm, keepWithNext=True,
    )
    cell_style = ParagraphStyle(
        "PredictionCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=body_size, leading=body_size + 1,
    )
    small_style = ParagraphStyle(
        "PredictionSmall", parent=cell_style,
        fontSize=7.6 if is_mobile else body_size - 0.3,
        leading=9.6 if is_mobile else body_size + 0.4,
        textColor=colors.HexColor("#475569"),
    )
    subheading_style = ParagraphStyle(
        "MarriageLevel4", parent=small_style, fontName="Helvetica-Bold",
        keepWithNext=True, spaceAfter=0.7 * mm,
    )
    def cell(value: Any, style=cell_style):
        return Paragraph(str(value if value is not None else "—"), style)

    if significators is not None:
        reference_style = ParagraphStyle(
            "AstrologerReference", parent=small_style, fontName="Helvetica-BoldOblique",
            fontSize=body_size, leading=body_size + 2, textColor=colors.HexColor("#64748B"),
            keepWithNext=True,
        )
        story = _marriage_summary_story(
            _marriage_summary_items(
                significators, dba, transits, reference_date or datetime.now().date()
            ),
            dba, title_style, small_style, body_size, is_mobile,
        )
        story.extend([
            PageBreak(),
            Paragraph(title, title_style),
            Paragraph("For Astrologer Reference. Clients may ignore this section.", reference_style),
            Paragraph(
                f"Prediction window: {dba['from_date']} through {(date.fromisoformat(dba['end_date_exclusive']) - timedelta(days=1)).isoformat()}",
                small_style,
            ),
            Spacer(1, 2 * mm),
        ])
        story.extend(_marriage_significator_story(
            significators, dba, transits, level1_style, level2_style,
            level3_style, subheading_style, cell_style, small_style,
            usable_width, body_size, cell,
        ))
    else:
        story = [
            Paragraph(title, title_style),
            Paragraph(
                f"Prediction window: {dba['from_date']} through {(date.fromisoformat(dba['end_date_exclusive']) - timedelta(days=1)).isoformat()}",
                small_style,
            ),
            Spacer(1, 2 * mm),
        ]
        story.extend(_generic_period_story(dba, transits, section_style, cell_style, small_style, usable_width, cell))

    doc = SimpleDocTemplate(
        buffer, pagesize=page_size, leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title=title,
    )
    doc.build(story)
    return buffer.getvalue()


def create_prediction_pdf(request: PredictionReportRequest, kind: str, bhava_number: int) -> bytes:
    period_request = PredictionPeriodsRequest(
        date_of_birth=request.date_of_birth,
        time_of_birth=request.time_of_birth,
        latitude=request.latitude,
        longitude=request.longitude,
        timezone=request.timezone,
        ayanamsa=request.ayanamsa,
        from_date=request.from_date,
        duration_years=request.duration_years,
        bhava_number=bhava_number,
    )
    dba = get_dba_periods(period_request)
    transit = get_transit_periods(period_request, consolidate_house_periods=(kind == "marriage"))
    title = "Marriage Date - Analysis" if kind == "marriage" else "Child Birth Prediction"
    significators = _prediction_significators(request, (7, 3, 11)) if kind == "marriage" else None
    generation_date = datetime.now(timezone(timedelta(hours=request.timezone))).date()
    prediction_pdf = _prediction_pdf_page(
        dba, transit, title, request.version, significators, generation_date
    )
    base_pdf = _report_cover(request, kind)

    try:
        cover = PdfReader(BytesIO(base_pdf)).pages[0]
        prediction_pages = PdfReader(BytesIO(prediction_pdf)).pages
        writer = PdfWriter()
        writer.add_page(cover)
        for page in prediction_pages:
            writer.add_page(page)
        result = BytesIO()
        writer.write(result)
        return result.getvalue()
    except Exception as exc:
        raise HTTPException(500, f"Could not assemble prediction report: {exc}") from None


def get_marriage_prediction_data(request: PredictionPeriodsRequest) -> dict[str, Any]:
    """Return the interactive marriage summary and detailed report sections as JSON."""
    marriage_request = request.model_copy(update={"bhava_number": 7})
    dba = get_dba_periods(marriage_request)
    transits = get_transit_periods(marriage_request, consolidate_house_periods=True)
    significators = _prediction_significators(marriage_request, (7, 3, 11))
    transit_rows = transits.get("transit_periods", [])
    slow_planets = {"Jupiter", "Saturn", "Rahu", "Ketu"}
    full_planet_names = {abbreviation: planet for planet, abbreviation in PLANET_ABBREVIATIONS.items()}
    win_start = _parse_event_date(transits.get("from_date"))
    win_end_excl = _parse_event_date(transits.get("end_date_exclusive"))
    sections: list[dict[str, Any]] = []

    for bhava in (7, 3, 11):
        location_transits: set[tuple[str, str, str]] = set()
        category_sections = []
        for category, label in (("location", "Location"), ("cuspal_interlink", "Cuspal Links")):
            selected = set(significators["bhavas"][bhava][category])
            dba_entries = _dba_planet_periods(
                dba,
                selected,
                significators["combined_values"] if category == "cuspal_interlink" else None,
            )
            dba_tree = _nest_dba_periods(dba_entries)
            transit_entries = _merge_transit_periods(
                transit_rows,
                bhava,
                selected | slow_planets,
                window_start=win_start,
                window_end_exclusive=win_end_excl,
                include_boundary_values=category == "cuspal_interlink",
            ) if selected else []
            if category == "location":
                location_transits = {
                    (row.get("planet_name") or full_planet_names.get(row["planet"], row["planet"]), row["start"], row["end"])
                    for row in transit_entries
                }
            else:
                transit_entries = [
                    row for row in transit_entries
                    if (row.get("planet_name") or full_planet_names.get(row["planet"], row["planet"]), row["start"], row["end"])
                    not in location_transits
                ]
                for row in transit_entries:
                    planet_name = row.get("planet_name")
                    if planet_name:
                        row["start_combined_value"] = _transit_combined_value(
                            planet_name, row.get("start_degree"), significators["cusps"]
                        )
                        row["end_combined_value"] = _transit_combined_value(
                            planet_name, row.get("end_degree"), significators["cusps"]
                        )

            slow_abbreviations = {PLANET_ABBREVIATIONS.get(name, name) for name in slow_planets}
            category_sections.append({
                "category": category,
                "label": label,
                "planets": sorted(selected),
                "transit": {
                    "slow_moving": [row for row in transit_entries if row["planet"] in slow_abbreviations],
                    "other": [row for row in transit_entries if row["planet"] not in slow_abbreviations],
                },
                "dba": dba_tree,
            })
        sections.append({
            "bhava": bhava,
            "title": "Primary Significator" if bhava == 7 else f"Secondary Significator {1 if bhava == 3 else 2}",
            "categories": category_sections,
        })

    reference_date = datetime.now(timezone(timedelta(hours=marriage_request.timezone))).date()
    return {
        "from_date": dba["from_date"],
        "end_date_exclusive": dba["end_date_exclusive"],
        "duration_years": dba["duration_years"],
        "summary": _marriage_summary_items(significators, dba, transits, reference_date),
        "sections": sections,
    }
