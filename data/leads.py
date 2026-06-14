"""Leads and activities data access layer.

Multi-tenant: all functions require an explicit account_id.
No hardcoded IDs -- each caller passes the real account_id from the session.
"""
import uuid
from datetime import datetime
from typing import Optional
from services.supabase_client import get_supabase, safe_single


def _sb():
    return get_supabase()


def list_leads(account_id: str, status: str = "", business: str = "", industry: str = "", search: str = "", page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
    """Return (leads, total_count)."""
    query = _sb().table("leads").select("*", count="exact").eq("account_id", account_id).order("created_at", desc=True)
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


def get_lead(lead_id: str, account_id: str) -> Optional[dict]:
    result = _sb().table("leads").select("*").eq("id", lead_id).eq("account_id", account_id).single().execute()
    return result.data if result.data else None


def create_lead(data: dict, account_id: str = "") -> dict:
    """Create a lead. account_id can be passed explicitly or via data['account_id']."""
    data["id"] = str(uuid.uuid4())
    data["account_id"] = account_id or data.get("account_id", "")
    data["created_at"] = datetime.utcnow().isoformat()
    data["updated_at"] = data["created_at"]
    result = _sb().table("leads").insert(data).execute()
    return result.data[0] if result.data else data


def update_lead(lead_id: str, updates: dict, account_id: str):
    updates["updated_at"] = datetime.utcnow().isoformat()
    _sb().table("leads").update(updates).eq("id", lead_id).execute()


def update_lead_status(lead_id: str, status: str, account_id: str):
    update_lead(lead_id, {"status": status}, account_id)


def count_by_status(account_id: str) -> dict:
    """Return dict of {status: count}."""
    counts = {}
    for s in ["cold", "contacted", "replied", "interested", "closed_won", "closed_lost"]:
        q = _sb().table("leads").select("id", count="exact").eq("account_id", account_id).eq("status", s).execute()
        counts[s] = q.count or 0
    return counts


def get_leads_by_status(status: str, account_id: str) -> list[dict]:
    result = _sb().table("leads").select("*").eq("account_id", account_id).eq("status", status).execute()
    return result.data or []


def get_all_leads(account_id: str) -> list[dict]:
    result = _sb().table("leads").select("*").eq("account_id", account_id).order("created_at", desc=True).execute()
    return result.data or []


def delete_lead(lead_id: str, account_id: str):
    """Delete a lead and its activities from Supabase."""
    _sb().table("lead_activities").delete().eq("lead_id", lead_id).eq("account_id", account_id).execute()
    _sb().table("sales_messages").delete().eq("lead_id", lead_id).execute()
    _sb().table("leads").delete().eq("id", lead_id).eq("account_id", account_id).execute()


# ── Activities ──────────────────────────────────────────────────────


def create_activity(lead_id: str, activity_type: str, description: str, metadata: Optional[dict] = None, account_id: str = ""):
    acct = account_id
    record = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "account_id": acct,
        "activity_type": activity_type,
        "description": description,
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat(),
    }
    _sb().table("lead_activities").insert(record).execute()
    return record


def list_activities(lead_id: Optional[str] = None, limit: int = 50, account_id: str = "") -> list[dict]:
    acct = account_id
    query = _sb().table("lead_activities").select("*").eq("account_id", acct).order("created_at", desc=True).limit(limit)
    if lead_id:
        query = query.eq("lead_id", lead_id)
    result = query.execute()
    return result.data or []


def get_biz_stats(account_id: str):
    """Return per-business stats."""
    acct = account_id
    businesses = _sb().table("sales_businesses").select("*").eq("account_id", acct).execute()
    stats = {}
    for biz in (businesses.data or []):
        leads = _sb().table("leads").select("score,industry,status").eq("account_id", acct).eq("business_id", biz["id"]).execute()
        lead_list = leads.data or []
        total = len(lead_list)
        by_status = {}
        for s in ["cold", "contacted", "replied", "interested", "closed_won", "closed_lost"]:
            by_status[s] = len([l for l in lead_list if l.get("status") == s])
        avg_score = round(sum(l.get("score", 0) for l in lead_list) / total, 1) if total else 0
        industries = list(set(l.get("industry", "") for l in lead_list if l.get("industry")))
        stats[biz["name"]] = {"total": total, "by_status": by_status, "avg_score": avg_score, "industries": industries}
    return stats