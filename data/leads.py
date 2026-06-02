"""Leads and activities data access layer."""
import uuid
from datetime import datetime
from typing import Optional
from services.supabase_client import get_supabase, safe_single

_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _sb():
    return get_supabase()


def list_leads(status: str = "", business: str = "", industry: str = "", search: str = "", page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
    """Return (leads, total_count)."""
    query = _sb().table("leads").select("*", count="exact").eq("account_id", _ACCOUNT_ID).order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if business:
        query = query.eq("business_id", business)
    if industry:
        query = query.eq("industry", industry)
    if search:
        query = query.or_(f"company_name.ilike.%{search}%,contact_name.ilike.%{search}%,notes.ilike.%{search}%")
    offset = (page - 1) * per_page
    result = query.range(offset, offset + per_page - 1).execute()
    return result.data, result.count or 0


def get_lead(lead_id: str) -> Optional[dict]:
    result = _sb().table("leads").select("*").eq("id", lead_id).single().execute()
    return result.data if result.data else None


def create_lead(data: dict) -> dict:
    data["id"] = str(uuid.uuid4())
    data["account_id"] = _ACCOUNT_ID
    data["created_at"] = datetime.utcnow().isoformat()
    data["updated_at"] = data["created_at"]
    result = _sb().table("leads").insert(data).execute()
    return result.data[0] if result.data else data


def update_lead(lead_id: str, updates: dict):
    updates["updated_at"] = datetime.utcnow().isoformat()
    _sb().table("leads").update(updates).eq("id", lead_id).execute()


def update_lead_status(lead_id: str, status: str):
    update_lead(lead_id, {"status": status})


def count_by_status() -> dict:
    """Return dict of {status: count}."""
    result = _sb().table("leads").select("status", count="exact").eq("account_id", _ACCOUNT_ID).execute()
    counts = {}
    for s in ["cold", "contacted", "replied", "interested", "closed_won", "closed_lost"]:
        q = _sb().table("leads").select("id", count="exact").eq("account_id", _ACCOUNT_ID).eq("status", s).execute()
        counts[s] = q.count or 0
    return counts


def get_leads_by_status(status: str) -> list[dict]:
    result = _sb().table("leads").select("*").eq("account_id", _ACCOUNT_ID).eq("status", status).execute()
    return result.data or []


def get_all_leads() -> list[dict]:
    result = _sb().table("leads").select("*").eq("account_id", _ACCOUNT_ID).order("created_at", desc=True).execute()
    return result.data or []


# ── Activities ──────────────────────────────────────────────────────


def create_activity(lead_id: str, activity_type: str, description: str, metadata: Optional[dict] = None):
    record = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "account_id": _ACCOUNT_ID,
        "activity_type": activity_type,
        "description": description,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    _sb().table("lead_activities").insert(record).execute()
    return record


def list_activities(lead_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    query = _sb().table("lead_activities").select("*").eq("account_id", _ACCOUNT_ID).order("created_at", desc=True).limit(limit)
    if lead_id:
        query = query.eq("lead_id", lead_id)
    result = query.execute()
    return result.data or []


def get_biz_stats():
    """Return per-business stats."""
    businesses = _sb().table("sales_businesses").select("*").eq("account_id", _ACCOUNT_ID).execute()
    stats = {}
    for biz in (businesses.data or []):
        leads = _sb().table("leads").select("score,industry,status").eq("account_id", _ACCOUNT_ID).eq("business_id", biz["id"]).execute()
        lead_list = leads.data or []
        total = len(lead_list)
        by_status = {}
        for s in ["cold", "contacted", "replied", "interested", "closed_won", "closed_lost"]:
            by_status[s] = len([l for l in lead_list if l.get("status") == s])
        avg_score = round(sum(l.get("score", 0) for l in lead_list) / total, 1) if total else 0
        industries = list(set(l.get("industry", "") for l in lead_list if l.get("industry")))
        stats[biz["name"]] = {"total": total, "by_status": by_status, "avg_score": avg_score, "industries": industries}
    return stats
