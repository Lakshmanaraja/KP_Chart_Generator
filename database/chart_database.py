from supabase import create_client

class ClientDatabase:

    def __init__(self, url, key):
        self.supabase = create_client(url, key)

    def get_client_data(self, client_ids):
        #return self.supabase.from_("client_chart_index").select("client_id", "extras").in_("client_id", client_ids).execute()
        if not client_ids:
            return []

        response = (
            self.supabase
            .table("client_chart_index")
            .select("client_id, extras")
            .in_("client_id", client_ids)
            .execute()
        )

        return [
            (row["client_id"], row["extras"])
            for row in response.data
        ]
    