"""Usage limits data access layer."""
from datetime import date, datetime, timezone
from services.supabase_client import get_supabase

_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _sb():
    return get_supabase()


def _first_of_month_iso() -> str:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def get_limits():
    result = _sb().table("usage_limits").select("*").eq("account_id", _ACCOUNT_ID).maybe_single().execute()
    return result.data


def get_leads_count_this_month():
    first_of_month = _first_of_month_iso()
    result = _sb().table("leads").select("id", count="exact").eq("account_id", _ACCOUNT_ID).gte("created_at", first_of_month).execute()
    return result.count or 0


def get_messages_count_this_month():
    first_of_month = _first_of_month_iso()
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", _ACCOUNT_ID).gte("created_at", first_of_month).execute()
    return result.count or 0


def get_today_messages():
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", _ACCOUNT_ID).gte("sent_at", date.today().isoformat()).execute()
    return result.count or 0
