from database.transit_database import TransitDatabase
import os

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
transit_db = TransitDatabase(supabase_url, supabase_key)

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