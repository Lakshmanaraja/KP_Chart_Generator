"""Resolve saved gender only through the caller's authenticated client access."""
import os

import requests
from fastapi import HTTPException

from models.schemas import ReportRequest


def resolve_report_gender(req: ReportRequest, authorization: str | None) -> ReportRequest:
    # Explicit gender (including neutral/unknown) remains the caller's choice.
    if (req.gender and req.gender.strip()) or req.client_id is None:
        return req

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Sign in to use saved client gender")
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not base.startswith("https://") or not key:
        raise HTTPException(503, "Saved client gender lookup is not configured")

    # Never use DATABASE_URL or a service-role key: preserve auth.uid() and RLS.
    headers = {"apikey": key, "Authorization": f"Bearer {token.strip()}"}
    try:
        user = requests.get(f"{base}/auth/v1/user", headers=headers, timeout=10)
        if user.status_code in (401, 403):
            raise HTTPException(401, "Invalid or expired sign-in")
        user.raise_for_status()
        if not user.json().get("id"):
            raise HTTPException(401, "Invalid or expired sign-in")

        allowed = requests.post(
            f"{base}/rest/v1/rpc/can_access_assigned_client",
            headers=headers, json={"_client_id": str(req.client_id)}, timeout=10,
        )
        allowed.raise_for_status()
        if allowed.json() is not True:
            raise HTTPException(403, "Client is unavailable or access is not permitted")

        saved = requests.get(
            f"{base}/rest/v1/client_details", headers=headers,
            params={"select": "gender", "id": f"eq.{req.client_id}", "limit": "1"},
            timeout=10,
        )
        saved.raise_for_status()
        rows = saved.json()
        if not isinstance(rows, list) or len(rows) != 1:
            raise HTTPException(403, "Client is unavailable or access is not permitted")
        gender = rows[0].get("gender")
        if gender is not None and not isinstance(gender, str):
            raise ValueError("Unexpected gender response")
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        # Do not expose tokens, upstream response bodies or client details.
        raise HTTPException(503, "Saved client gender lookup is temporarily unavailable") from None

    return req.model_copy(update={"gender": gender})