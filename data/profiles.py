"""Target profiles data access layer."""
import uuid
from datetime import datetime
from typing import Optional
from services.supabase_client import get_supabase

_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _sb():
    return get_supabase()


def list_profiles() -> list[dict]:
    result = _sb().table("target_profiles").select("*").eq("account_id", _ACCOUNT_ID).execute()
    return result.data or []


def get_profile(profile_id: str) -> Optional[dict]:
    result = _sb().table("target_profiles").select("*").eq("id", profile_id).single().execute()
    return result.data if result.data else None


def create_profile(data: dict) -> dict:
    data["id"] = str(uuid.uuid4())
    data["account_id"] = _ACCOUNT_ID
    data["created_at"] = datetime.utcnow().isoformat()
    result = _sb().table("target_profiles").insert(data).execute()
    return result.data[0] if result.data else data


def update_profile(profile_id: str, updates: dict):
    _sb().table("target_profiles").update(updates).eq("id", profile_id).execute()


def delete_profile(profile_id: str):
    _sb().table("target_profiles").delete().eq("id", profile_id).execute()


def list_businesses() -> list[dict]:
    result = _sb().table("sales_businesses").select("*").eq("account_id", _ACCOUNT_ID).execute()
    return result.data or []
