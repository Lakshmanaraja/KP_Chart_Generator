"""Birth-chart generation and Planet Lord Summary calculations."""
from typing import Any

from fastapi import HTTPException

from models.schemas import PlanetLordSummaryRequest
from services.chart_service import compute_kp_json


VIM_SEQ = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
PLANET_ABBREVIATIONS = {
    "Ketu": "Ke", "Venus": "Ve", "Sun": "Su", "Moon": "Mo", "Mars": "Ma",
    "Rahu": "Ra", "Jupiter": "Ju", "Saturn": "Sa", "Mercury": "Me",
}


def _cycle_index(name: str | None, anchor: str | None) -> int:
    if not name:
        return 999
    start = VIM_SEQ.index(anchor) if anchor in VIM_SEQ else 0
    order = VIM_SEQ[start:] + VIM_SEQ[:start]
    return order.index(name) if name in order else 999


def _signature(item: dict[str, Any], anchor: str | None) -> tuple[int, ...]:
    nl = item.get("nakshatra_lord")
    su = item.get("sub_lord")
    ss = item.get("sub_sub_lord")
    return (
        _cycle_index(nl, anchor),
        _cycle_index(su, nl),
        _cycle_index(ss, su),
        _cycle_index(item.get("sub_sub_sub_lord"), ss),
    )


def _star_bhavas(item: dict[str, Any], houses: list[dict[str, Any]]) -> list[int]:
    result: list[int] = []
    for index, house in enumerate(houses):
        next_house = houses[(index + 1) % len(houses)]
        anchor = house.get("nakshatra_lord")
        start = _signature(house, anchor)
        end = _signature(next_house, anchor)
        current = _signature(item, anchor)
        wraps = end <= start
        if current >= start and (wraps or current < end):
            result.append(int(house["house_id"]))
    return sorted(set(result))


def _calculate(extras: dict[str, Any], options: PlanetLordSummaryRequest) -> dict[str, Any]:
    houses = sorted(extras.get("cusps") or [], key=lambda item: item.get("house_id", 0))
    planets = [
        item for item in (extras.get("planets") or [])
        if item.get("name", item.get("planet_name")) != "Ascendant"
    ]
    if len(houses) != 12 or not planets:
        raise HTTPException(422, "Indexed chart is incomplete")

    houses = [{**house, "full_degree": house.get("deg", house.get("full_degree"))} for house in houses]
    planets = [
        {
            **planet,
            "planet_name": planet.get("name", planet.get("planet_name")),
            "full_degree": planet.get("deg", planet.get("full_degree")),
        }
        for planet in planets
    ]

    def location(planet: dict[str, Any]) -> int | str:
        degree = float(planet.get("full_degree") or 0) % 360
        for index, house in enumerate(houses):
            start = float(house.get("full_degree") or 0)
            end = float(houses[(index + 1) % len(houses)].get("full_degree") or 0)
            if (end < start and (degree >= start or degree < end)) or (end >= start and start <= degree < end):
                return int(house["house_id"])
        return planet.get("house", "")

    planets_by_name = {planet["planet_name"]: planet for planet in planets}
    override = options.moon_override if options.moon_override_enabled else None

    def effective(planet: dict[str, Any]) -> dict[str, Any]:
        item = dict(planet)
        if planet["planet_name"] == "Moon" and override:
            item.update({
                "nakshatra_lord": override.get("nl") or item.get("nakshatra_lord"),
                "sub_lord": override.get("psu") or item.get("sub_lord"),
                "sub_sub_lord": override.get("ssl") or item.get("sub_sub_lord"),
                "sub_sub_sub_lord": override.get("skl") or item.get("sub_sub_sub_lord"),
            })
        return item

    def lord_data(name: str | None, field: str, row_location: int | str) -> dict[str, Any]:
        if not name:
            return {"lord": None, "bhavas": []}
        bhavas = sorted(int(house["house_id"]) for house in houses if house.get(field) == name)
        if not bhavas:
            own_planet = planets_by_name.get(name)
            if own_planet:
                bhavas = [int(location(own_planet))]
        if options.location_include:
            try:
                bhavas = sorted(set([int(row_location), *bhavas]))
            except (TypeError, ValueError):
                pass
        return {"lord": name, "bhavas": bhavas}

    rows = []
    for planet in sorted(
        planets,
        key=lambda item: VIM_SEQ.index(item["planet_name"]) if item["planet_name"] in VIM_SEQ else 999,
    ):
        item = effective(planet)
        row_location = location(planet)
        su = lord_data(item.get("sub_lord"), "sub_lord", row_location)
        ss = lord_data(item.get("sub_sub_lord"), "sub_sub_lord", row_location)
        sk = lord_data(item.get("sub_sub_sub_lord"), "sub_sub_sub_lord", row_location)
        rows.append({
            "planet_name": planet["planet_name"], "location": row_location,
            "nl_lord": item.get("nakshatra_lord"), "nl_bhavas": _star_bhavas(item, houses),
            "su_lord": su["lord"], "su_bhavas": su["bhavas"],
            "ss_lord": ss["lord"], "ss_bhavas": ss["bhavas"],
            "sk_lord": sk["lord"], "sk_bhavas": sk["bhavas"],
        })

    original_moon = None
    if options.include_original_moon:
        moon = planets_by_name.get("Moon")
        if moon:
            original_moon = next((row for row in rows if row["planet_name"] == "Moon"), None)
            if override:
                raw_options = options.model_copy(update={"moon_override_enabled": False})
                original_rows = _calculate({"cusps": houses, "planets": planets}, raw_options)["rows"]
                original_moon = next((row for row in original_rows if row["planet_name"] == "Moon"), None)
            if original_moon:
                original_moon = {**original_moon, "planet_name": "OM"}
    return {"rows": rows, "original_moon": original_moon}


def get_planet_lord_summary(options: PlanetLordSummaryRequest) -> dict[str, Any]:
    if options.calculation_mode == "transit":
        if not options.bhava_cusps or not options.transit_planets:
            raise HTTPException(422, "Transit summary requires main-chart bhava cusps and transit planets")
        extras = {"cusps": options.bhava_cusps, "planets": options.transit_planets}
    else:
        # The API accepts both HH:MM and HH:MM:SS; the chart parser expects seconds.
        time_of_birth = options.time_of_birth
        if len(time_of_birth.split(":")) == 2:
            time_of_birth = f"{time_of_birth}:00"
        try:
            chart = compute_kp_json(
                options.date_of_birth,
                time_of_birth,
                options.latitude,
                options.longitude,
                options.timezone,
                options.ayanamsa,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, f"Invalid birth details: {exc}") from None
        extras = {"cusps": chart["houses"], "planets": chart["planets"]}
    result = _calculate(extras, options)
    for row in result["rows"]:
        for field in ("planet_name", "nl_lord", "su_lord", "ss_lord", "sk_lord"):
            name = row[field]
            if name:
                row[field] = PLANET_ABBREVIATIONS.get(name, name)
    return result
