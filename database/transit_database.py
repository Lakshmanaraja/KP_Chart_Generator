from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

class TransitDatabase:

    def __init__(self, url, key):
        self.supabase = create_client(url, key)

    def get_planet_between_degree(
        self,
        planet,
        start_degree,
        end_degree,
        start_date, #Birth Date
        end_date = None
    ):

        result = (
            self.supabase
            .table("planet_positions")
            .select("*")
            .eq("planet", planet)
            #.eq("event_type", "RASI")
            .eq("longitude", round(start_degree))
            #.lte("longitude", end_degree)
            .gte("utc_datetime", start_date)
            .lte("utc_datetime", end_date)
            .order("utc_datetime")
            .execute()
        )

        return result.data

    def get_events(
        self,
        planet,
        event_type=None
    ):

        query = (
            self.supabase
            .table("planet_events")
            .select("*")
            .eq("planet", planet)
        )

        if event_type:
            query = query.eq("event_type", event_type)

        return query.order("event_datetime").execute().data

    def get_planet_star_transit_dates(
        self,
        planet:str,
        star_lord:str,
        start_date:str,
        end_date:str
    ):
        query = (
                self.supabase
                .table("kp_planet_star_transits")
                .select("*")
                .eq("planet", planet)
                .eq("star_lord", star_lord)
                .gte("entry_datetime", start_date)
                .lte("entry_datetime", end_date)
            )

        return query.order("entry_datetime").execute().data
 