from database.transit_database import TransitDatabase
from database.chart_database import ClientDatabase
from services.matcher_service import house_of_degree
from utils.date_utils import get_nak_charan_and_pos
import os
import json
from datetime import datetime, timezone

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
transit_db = TransitDatabase(supabase_url, supabase_key)
chart_db = ClientDatabase(supabase_url, supabase_key)

_RASI_NAMES_TAMIL = (
    "Mesham", "Rishabam", "Mithunam", "Kadagam", "Simham", "Kanni",
    "Thulam", "Viruchigam", "Dhanusu", "Magaram", "Kumbam", "Meenam",
)
_SIGN_LORDS = (
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
)
_STAR_NAMES_TAMIL = {
    "Ashwini": "Aswini", "Bharani": "Bharani", "Krittika": "Karthigai",
    "Rohini": "Rohini", "Mrigashira": "Mirugasirisham", "Ardra": "Thiruvathirai",
    "Punarvasu": "Punarpoosam", "Pushya": "Poosam", "Ashlesha": "Ayilyam",
    "Magha": "Magam", "Purva Phalguni": "Pooram", "Uttara Phalguni": "Uthiram",
    "Hasta": "Hastham", "Chitra": "Chithirai", "Swati": "Swathi",
    "Vishakha": "Visakam", "Anuradha": "Anusham", "Jyeshtha": "Kettai",
    "Mula": "Moolam", "Purva Ashadha": "Pooradam", "Uttara Ashadha": "Uthiradam",
    "Shravana": "Thiruvonam", "Dhanishta": "Avittam", "Shatabhisha": "Sathayam",
    "Purva Bhadrapada": "Poorattadhi", "Uttara Bhadrapada": "Uthirattadhi",
    "Revati": "Revathi",
}


def _rasi_index(longitude):
    sign_index = int((float(longitude) % 360) // 30)
    return sign_index

def get_planet_between_degrees(planet: str, start_degree: float, end_degree: float, start_date: str, end_date: str = None):
 
    
    result = transit_db.get_planet_between_degree(planet, start_degree, end_degree, start_date, end_date)

    if not result:
        return {"message": "No data found for the specified planet and degree range."}

    return result

def get_planet_star_transit_dates(planet:str,star_lord:str,start_date:str,end_date:str):
  
    result = transit_db.get_planet_star_transit_dates(planet, star_lord, start_date, end_date)

    if not result:
        return {"message": "No data found for the specified planet and star lord."}

    return result


def _as_utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _star_transits_for_cusps(cusps, transits, date_format=None):
    results = []
    for transit in transits:
        entry_degree = transit.get("longitude_start")
        exit_degree = transit.get("longitude_end")
        if entry_degree is None:
            continue
        entry_degree = float(entry_degree)
        rasi_index = _rasi_index(entry_degree)
        _, star_name, _, _, _, _ = get_nak_charan_and_pos(entry_degree)
        results.append({
            "date": transit.get("entry_datetime"),
            "exit_date": transit.get("exit_datetime"),
            "planet": transit.get("planet"),
            "star": _STAR_NAMES_TAMIL.get(star_name, star_name),
            "rasi": _RASI_NAMES_TAMIL[rasi_index],
            "sign_lord": _SIGN_LORDS[rasi_index],
            "entry_degree": entry_degree,
            "exit_degree": float(exit_degree) if exit_degree is not None else None,
            "bhava": house_of_degree(entry_degree, cusps),
        })

    # Combine intervals from consecutive transit-table rows while the planet,
    # star, rasi and natal bhava remain unchanged.
    grouped = {}
    for row in results:
        grouped.setdefault((row["planet"], row["star"], row["rasi"], row["bhava"]), []).append(row)

    consolidated = []
    for intervals in grouped.values():
        intervals.sort(key=lambda row: _as_utc(row["date"]))
        current = intervals[0].copy()
        current_end = _as_utc(current["exit_date"])
        for interval in intervals[1:]:
            interval_start = _as_utc(interval["date"])
            interval_end = _as_utc(interval["exit_date"])
            if interval_start <= current_end:
                if interval_end > current_end:
                    current["exit_date"] = interval["exit_date"]
                    current["exit_degree"] = interval["exit_degree"]
                    current_end = interval_end
            else:
                consolidated.append(current)
                current = interval.copy()
                current_end = interval_end
        consolidated.append(current)

    consolidated.sort(key=lambda row: (_as_utc(row["date"]), row["planet"]))
    if date_format:
        for row in consolidated:
            row["date"] = _as_utc(row["date"]).strftime(date_format)
            row["exit_date"] = _as_utc(row["exit_date"]).strftime(date_format)
    return consolidated


def get_star_transits_for_cusps(cusps, start_datetime: str, end_datetime: str):
    """Return consolidated transit intervals with houses computed from supplied cusps."""
    transits = transit_db.get_star_transits_for_date_range(start_datetime, end_datetime)
    return _star_transits_for_cusps(cusps, transits)


def get_client_star_transits_for_year(client_id: str, from_year: int, to_year: int):
    """List star transit intervals with bhavas calculated from the client's cusps."""
    if from_year > to_year:
        return {"message": "from_year must be less than or equal to to_year."}

    charts = chart_db.get_client_data([client_id])
    if not charts:
        return {"message": f"No chart found for client {client_id}."}

    chart = charts[0][1]
    if isinstance(chart, str):
        chart = json.loads(chart)
    raw_cusps = chart.get("cusps") or chart.get("houses") or []
    cusps = [
        {"house_id": cusp["house_id"], "full_degree": cusp.get("full_degree", cusp.get("deg"))}
        for cusp in raw_cusps
        if cusp.get("house_id") is not None
        and cusp.get("full_degree", cusp.get("deg")) is not None
    ]
    if len(cusps) < 2:
        return {"message": f"No usable cusp degrees found for client {client_id}."}

    transits = transit_db.get_star_transits_for_year_range(from_year, to_year)
    return _star_transits_for_cusps(cusps, transits, "%d-%m-%Y")
