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
            .table("planet_transits")
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
                .table("planet_transits")
                .select("*")
                .eq("planet", planet)
                .eq("star_lord", star_lord)
                .gte("entry_datetime", start_date)
                .lte("entry_datetime", end_date)
            )

        return query.order("entry_datetime").execute().data

    def get_star_transits_for_year_range(self, from_year: int, to_year: int):
        """Return star transit intervals overlapping the requested calendar years."""
        start_date = f"{from_year}-01-01T00:00:00"
        end_date = f"{to_year}-12-31T23:59:59"
        page_size = 1000
        offset = 0
        rows = []
        while True:
            page = (
                self.supabase
                .table("planet_transits")
                .select("id, planet, longitude_start, longitude_end, nakshatra, entry_datetime, exit_datetime")
                .gte("exit_datetime", start_date)
                .lte("entry_datetime", end_date)
                .order("entry_datetime")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
            )
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return rows
    
    # def get_kp_planet_star_sub_transits(
    #     self,
    #     planet:str,
    #     beg_star_lord:str,
    #     beg_sub_lord:str,
    #     end_star_lord:str,
    #     end_sub_lord:str,
    #     start_date:str,
    #     end_date:str
    # ):
    #     query = (
    #             self.supabase
    #             .table("kp_planet_star_sub_transits")
    #             .select("*")
    #             .eq("planet", planet)
    #             .eq("star_lord", star_lord)
    #             .eq("sub_star_lord", sub_star_lord)
    #             .gte("entry_datetime", start_date)
    #             .lte("entry_datetime", end_date)
    #         )

    #     return query.order("entry_datetime").execute().data
