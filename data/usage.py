"""Usage limits data access layer.

Multi-tenant: all functions require an explicit account_id.
No hardcoded IDs — each caller passes the real account_id from the session.
"""
from datetime import date, datetime, timezone
from services.supabase_client import get_supabase


def _sb():
    return get_supabase()


def _first_of_month_iso() -> str:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def get_limits(account_id: str):
    """Fetch usage limits for a specific account."""
    result = _sb().table("usage_limits").select("*").eq("account_id", account_id).maybe_single().execute()
    return result.data


def get_leads_count_this_month(account_id: str):
    """Count leads created this month for a specific account."""
    first_of_month = _first_of_month_iso()
    result = _sb().table("leads").select("id", count="exact").eq("account_id", account_id).gte("created_at", first_of_month).execute()
    return result.count or 0


def get_messages_count_this_month(account_id: str):
    """Count messages sent this month for a specific account."""
    first_of_month = _first_of_month_iso()
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", account_id).gte("created_at", first_of_month).execute()
    return result.count or 0


def get_today_messages(account_id: str):
    """Count messages sent today for a specific account."""
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", account_id).gte("sent_at", date.today().isoformat()).execute()
    return result.count or 0
