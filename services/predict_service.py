"""Generic DBA/transit windows and marriage/child-birth prediction reports."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import Any

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from models.schemas import PredictionPeriodsRequest, PredictionReportRequest, ReportRequest
from pdf.desktop_report import render_desktop_pdf
from pdf.mobile_report import H as MOBILE_H, W as MOBILE_W, render_mobile_pdf
from services.chart_service import compute_kp_json
from services.dasa_service import calculate_antaras, calculate_bhuktis, compute_major_dasha
from services.report_service import NoTraitsFoundError, _pdf
from services.transit_service import get_star_transits_for_cusps
from utils.date_utils import get_moon_longitude, to_julian_day


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


def get_transit_periods(request: PredictionPeriodsRequest) -> dict[str, Any]:
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
    rows = get_star_transits_for_cusps(cusps, interval_start, interval_end)
    group = bhava_group(request.bhava_number)
    secondary = [bhava for bhava in group if bhava != request.bhava_number]
    start_utc = datetime.fromisoformat(interval_start)
    end_utc = datetime.fromisoformat(interval_end)
    filtered = []
    for row in rows:
        actual_bhava = row.get("bhava")
        if actual_bhava not in group:
            continue
        try:
            row_start = _as_utc_datetime(row["date"])
            row_end = _as_utc_datetime(row["exit_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if row_start >= end_utc.astimezone(timezone.utc) or row_end <= start_utc.astimezone(timezone.utc):
            continue
        filtered.append({
            **row,
            "actual_bhava": actual_bhava,
            "bhava_type": "primary" if actual_bhava == request.bhava_number else "secondary",
            "primary_bhava": request.bhava_number,
            "secondary_bhavas": secondary,
        })
    return {
        "from_date": start_date.isoformat(),
        "end_date_exclusive": end_date.isoformat(),
        "duration_years": request.duration_years,
        "bhava_number": request.bhava_number,
        "bhava_group": list(group),
        "secondary_bhavas": secondary,
        "transit_periods": filtered,
    }


def _report_cover(request: PredictionReportRequest) -> bytes:
    client = {
        "name": request.name,
        "date_of_birth": request.date_of_birth,
        "time_of_birth": request.time_of_birth,
        "place": request.place,
        "timezone": f"UTC{'+' if request.timezone >= 0 else ''}{request.timezone:g}",
    }
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


def _prediction_pdf_page(
    dba: dict[str, Any],
    transits: dict[str, Any],
    title: str,
    version: str,
) -> bytes:
    buffer = BytesIO()
    is_mobile = version == "mobile"
    page_size = (MOBILE_W, MOBILE_H) if is_mobile else A4
    margin = 5 * mm if is_mobile else 16 * mm
    body_size = 6.7 if is_mobile else 9
    usable_width = page_size[0] - 2 * margin
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PredictionTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=12 if is_mobile else 17, leading=14 if is_mobile else 20,
        textColor=colors.HexColor("#072A7D"), alignment=1, spaceAfter=5 * mm,
    )
    section_style = ParagraphStyle(
        "PredictionSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=8.5 if is_mobile else 12, leading=10 if is_mobile else 14,
        textColor=colors.HexColor("#1A659E"), spaceBefore=2 * mm, spaceAfter=1.5 * mm,
    )
    cell_style = ParagraphStyle(
        "PredictionCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=body_size, leading=body_size + 1,
    )
    small_style = ParagraphStyle(
        "PredictionSmall", parent=cell_style, fontSize=body_size - 0.3,
        leading=body_size + 0.4, textColor=colors.HexColor("#475569"),
    )
    story = [
        Paragraph(title, title_style),
        Paragraph(
            f"Prediction window: {dba['from_date']} through {(date.fromisoformat(dba['end_date_exclusive']) - timedelta(days=1)).isoformat()}",
            small_style,
        ),
        Spacer(1, 2 * mm),
        Paragraph("DBA Periods", section_style),
    ]

    def cell(value: Any, style=cell_style):
        return Paragraph(str(value if value is not None else "—"), style)

    bhuktis = dba["bhukti_periods"]
    if bhuktis:
        data = [[cell("Dasa"), cell("Bhukthi"), cell("From"), cell("To")]]
        data.extend([[cell(row["mahadasha"]), cell(row["bhukthi"]), cell(row["start"][:10]), cell(row["end"][:10])] for row in bhuktis])
        widths = [usable_width * 0.19, usable_width * 0.22, usable_width * 0.30, usable_width * 0.29]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend([table, Spacer(1, 2 * mm)])
    else:
        story.append(Paragraph("No Bhukthi periods overlap this window.", small_style))

    antaras = dba["antara_periods"]
    if antaras:
        data = [[cell("Dasa"), cell("Bhukthi"), cell("Antara"), cell("From"), cell("To")]]
        data.extend([[cell(row["mahadasha"]), cell(row["bhukthi"]), cell(row["antara"]), cell(row["start"][:10]), cell(row["end"][:10])] for row in antaras])
        widths = [usable_width * .16, usable_width * .18, usable_width * .20, usable_width * .23, usable_width * .23]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend([table, Spacer(1, 2 * mm)])
    else:
        story.append(Paragraph("No Antara periods overlap this window.", small_style))

    story.append(Paragraph("Transit Periods", section_style))
    rows = transits["transit_periods"]
    if rows:
        data = [[cell("Planet"), cell("Star"), cell("Bhava"), cell("From"), cell("To")]]
        data.extend([
            [
                cell(row["planet"]), cell(row["star"]),
                cell(f"{row['actual_bhava']} ({row['bhava_type']})"),
                cell(str(row["date"])[:10]), cell(str(row["exit_date"])[:10]),
            ]
            for row in rows
        ])
        widths = [usable_width * .16, usable_width * .25, usable_width * .20, usable_width * .195, usable_width * .195]
        table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0FA")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#072A7D")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No matching transit periods overlap this window.", small_style))

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
    transit = get_transit_periods(period_request)
    title = "Marriage Date Prediction" if kind == "marriage" else "Child Birth Prediction"
    prediction_pdf = _prediction_pdf_page(dba, transit, title, request.version)
    base_pdf = _report_cover(request)

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
