"""Usage limits data access layer."""
from datetime import date
from services.supabase_client import get_supabase

_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _sb():
    return get_supabase()


def get_limits():
    result = _sb().table("usage_limits").select("*").eq("account_id", _ACCOUNT_ID).maybe_single().execute()
    return result.data


def get_leads_count_this_month():
    result = _sb().table("leads").select("id", count="exact").eq("account_id", _ACCOUNT_ID).execute()
    return result.count or 0


def get_messages_count_this_month():
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", _ACCOUNT_ID).execute()
    return result.count or 0


def get_today_messages():
    result = _sb().table("sales_messages").select("id", count="exact").eq("account_id", _ACCOUNT_ID).gte("sent_at", date.today().isoformat()).execute()
    return result.count or 0
