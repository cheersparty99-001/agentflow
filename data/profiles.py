"""Target profiles data access layer.

Multi-tenant: all functions require an explicit account_id.
No hardcoded IDs -- each caller passes the real account_id from the session.
"""
import uuid
from datetime import datetime
from typing import Optional
from services.supabase_client import get_supabase


def _sb():
    return get_supabase()


def list_profiles(account_id: str) -> list[dict]:
    result = _sb().table("target_profiles").select("*").eq("account_id", account_id).execute()
    return result.data or []


def get_profile(profile_id: str, account_id: str) -> Optional[dict]:
    result = _sb().table("target_profiles").select("*").eq("id", profile_id).eq("account_id", account_id).single().execute()
    return result.data if result.data else None


def create_profile(data: dict, account_id: str = "") -> dict:
    data["id"] = str(uuid.uuid4())
    data["account_id"] = account_id or data.get("account_id", "")
    data["created_at"] = datetime.utcnow().isoformat()
    result = _sb().table("target_profiles").insert(data).execute()
    return result.data[0] if result.data else data


def update_profile(profile_id: str, updates: dict, account_id: str):
    _sb().table("target_profiles").update(updates).eq("id", profile_id).eq("account_id", account_id).execute()


def delete_profile(profile_id: str, account_id: str):
    _sb().table("target_profiles").delete().eq("id", profile_id).eq("account_id", account_id).execute()


def list_businesses(account_id: str) -> list[dict]:
    result = _sb().table("sales_businesses").select("*").eq("account_id", account_id).execute()
    return result.data or []
