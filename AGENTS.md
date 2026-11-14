# API architecture

- Resolve saved report gender at the request boundary with a validated user Bearer token, the shared client-access RPC, and user-scoped RLS reads; never use the live-rules database connection or service-role credentials for client lookup, because a supplied client ID is not authorization.