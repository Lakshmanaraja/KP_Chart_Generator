from unittest import result
import json
import pandas as pd

from database.chart_database import ClientDatabase
import os

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
chart_db = ClientDatabase(supabase_url, supabase_key)

def find_patterns(client_ids: list[str], bhava_number: str, cusp_bh_column: str = "house_id", planet_bh_column: str = "planet", cusp_cols: tuple[str] = ("nakshatra_lord", "sub_lord", "sub_sub_lord","sub_sub_sub_lord"), planet_cols: tuple[str] = ("name","nakshatra_lord", "sub_lord", "sub_sub_lord", "sub_sub_sub_lord")):  
    # Implementation for finding patterns

    # i want to pass list of client ids to this function and find patterns in their charts. 
    # I want to return a list of bhava-planet patterns common between the list of dataframes with the accuracy of each pattern.
    chart_json_list = chart_db.get_client_data(client_ids)

    # Convert JSON data to DataFrames
    #charts = [pd.DataFrame(json_data["cusps"]) for json_data in chart_json_list]
    result = []
    if (bhava_number =="All" or bhava_number == "all" or bhava_number == "None" or bhava_number == "none"):
        for bhava in range(1, 13):
            bhava_result = bhava_planet_patterns(chart_json_list, bhava, cusp_bh_column, planet_bh_column, cusp_cols, planet_cols)
            result.append(bhava_result)
    else:
        res = (bhava_planet_patterns(chart_json_list, bhava_number, cusp_bh_column, planet_bh_column, cusp_cols, planet_cols))
        result.append(res)

    return pd.concat(result).reset_index(drop=True)

def bhava_planet_patterns(
    chart_json_list,
    bhava_number,
    cusp_bh_column="house_id",
    planet_bh_column="planet",
    cusp_cols=(
        "nakshatra_lord",
        "sub_lord",
        "sub_sub_lord",
        "sub_sub_sub_lord",
    ),
    planet_cols=(
        "name",
        "nakshatra_lord",
        "sub_lord",
        "sub_sub_lord",
        "sub_sub_sub_lord",
    )
):
    """
    chart_json_list format:
    [
        (client_id_1, {"cusps": [...], "planets": [...]}),
        (client_id_2, {"cusps": [...], "planets": [...]}),
    ]

    Only the 'cusps' data is used.
    """

    total_charts = len(chart_json_list)
    all_client_ids = set()
    planet_to_matched_client_ids = {}

    # Unpack each database row: (client_id, chart_json)
    for client_id, chart_json in chart_json_list:
        client_id = str(client_id)
        all_client_ids.add(client_id)

        # Use this only if chart_json arrives as a JSON string.
        if isinstance(chart_json, str):
            chart_json = json.loads(chart_json)
        # A planet is counted once per client chart for this bhava.
        planets_in_chart = set()
        
        cusp_values = pd.DataFrame(chart_json.get("cusps", []))
        planets_in_chart.update(planets_in_chart_fn(cusp_values, bhava_number, cusp_bh_column, cusp_cols,planets_in_chart))
        print(f"Client ID: {client_id}, Bhava: {bhava_number}, Planets in chart: {planets_in_chart}")

        pl_values = pd.DataFrame(chart_json.get("planets", []))
        planets_in_chart.update(planets_in_chart_fn(pl_values, bhava_number, planet_bh_column, planet_cols,planets_in_chart))
        print(f"Client ID: {client_id}, Bhava: {bhava_number}, Planets in chart: {planets_in_chart}")

        for planet in planets_in_chart:
            planet_to_matched_client_ids.setdefault(planet, set()).add(client_id)

    results = []

    for planet, matched_client_ids in planet_to_matched_client_ids.items():
        matched_client_ids = sorted(matched_client_ids)
        failed_client_ids = sorted(all_client_ids - set(matched_client_ids))

        results.append({
            "bhava": bhava_number,
            "planet": planet,
            "charts_matched": len(matched_client_ids),
            "total_charts": total_charts,
            "accuracy_percent": round(
                len(matched_client_ids) / total_charts * 100, 2
            ) if total_charts else 0,
            "matched_client_ids": matched_client_ids,
            "failed_client_ids": failed_client_ids,
        })

    columns = [
        "bhava", "planet", "charts_matched", "total_charts",
        "accuracy_percent", "matched_client_ids", "failed_client_ids",
    ]

    return (
        pd.DataFrame(results, columns=columns)
        .sort_values(["charts_matched", "planet"], ascending=[False, True])
        .reset_index(drop=True)
    )

def planets_in_chart_fn(chart_values, bhava_number, bh_column,cols,planets_in_chart=set()):
    # Extract only cusps; planets data is ignored.
    #pl_list =set()        
    if chart_values.empty or bh_column not in chart_values.columns:
        return planets_in_chart

    bhava_rows = chart_values[
        chart_values[bh_column].astype(str).str.strip() == str(bhava_number)
    ]

    if bhava_rows.empty: 
        return planets_in_chart

    for column in cols:
        if column not in bhava_rows.columns:
            continue

        values = bhava_rows[column].dropna().astype(str).str.strip()

        planets_in_chart.update(
            value
            for value in values
            if value and value.lower() not in {"nan", "none", "-"}
        )
        return planets_in_chart
