import os
import uuid
import json
import traceback
from datetime import datetime
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_update
from routers.auth import get_current_user
import config as cfg

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


def _sb():
    return get_supabase()


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    account_id = user.get("account_id")
    sb = _sb()
    account = safe_single(lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(), default={"agency_name": "My Agency"})
    agency_name = account.get("agency_name", "My Agency") if account else "My Agency"

    # Load email connection status
    email_status = {"connected": False}
    try:
        from services.sales.oauth import GoogleOAuth
        email_conn = GoogleOAuth().get_connection(account_id)
        if email_conn:
            email_status = {
                "connected": True,
                "provider": email_conn.get("provider"),
                "email": email_conn.get("email"),
                "connected_at": email_conn.get("connected_at"),
            }
    except Exception as e:
        print(f"[Settings] Email status error: {e}")

    # Load businesses for the business selector
    businesses = []
    try:
        biz_result = sb.table("sales_businesses").select("*").eq("account_id", account_id).execute()
        businesses = biz_result.data or []
    except Exception as e:
        print(f"[Settings] Load businesses error: {e}")

    template = env.get_template("settings.html")
    html = template.render(
        agency_name=agency_name,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
        email_status=email_status,
        businesses=businesses,
    )
    return HTMLResponse(html)


@router.get("/api/settings")
async def get_settings(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    sb = _sb()
    data = safe_single(lambda: sb.table("accounts").select("*").eq("id", account_id).single(), default=None)
    if not data:
        return JSONResponse({
            "agency_name": "My Agency",
            "phone": "",
            "email": "demo@flowreach.work",
            "language": "en",
        })

    return JSONResponse({
        "agency_name": data.get("agency_name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "language": data.get("language", "en"),
    })


@router.post("/api/settings")
async def save_settings(
    request: Request,
    agency_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    language: str = Form("en"),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    sb = _sb()

    safe_update("accounts", {
        "agency_name": agency_name,
        "phone": phone,
        "email": email,
        "language": language,
    }, "id", account_id)

    return JSONResponse({"success": True})


# ── Target Profile API ─────────────────────────────────────────────────────


def _load_profiles(account_id: str, sb):
    """Load target profiles joined with business names."""
    profiles = []
    try:
        result = sb.table("target_profiles").select("*").eq("account_id", account_id).order("created_at", desc=True).execute()
        profiles = result.data or []
    except Exception as e:
        print(f"[Settings] Load profiles error: {e}")
        return []

    # Attach business names
    biz_ids = list(set(p.get("business_id", "") for p in profiles if p.get("business_id")))
    biz_map = {}
    if biz_ids:
        try:
            biz_result = sb.table("sales_businesses").select("id, name, description, value_proposition").in_("id", biz_ids).execute()
            biz_map = {b["id"]: b for b in (biz_result.data or [])}
        except:
            pass

    for p in profiles:
        biz = biz_map.get(p.get("business_id", ""), {})
        p["business_name"] = biz.get("name", "Unknown")
        p["business_description"] = biz.get("description", "")
        p["business_value_proposition"] = biz.get("value_proposition", "")

    return profiles


@router.get("/api/target-profiles")
async def api_list_profiles(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    sb = _sb()
    profiles = _load_profiles(user["account_id"], sb)
    return JSONResponse({"profiles": profiles})


@router.post("/api/target-profiles")
async def api_create_profile(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user["account_id"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    business_id = body.get("business_id", "")
    name = body.get("name", "Untitled Profile")
    industries = body.get("industries", [])
    locations = body.get("locations", [])
    company_size = body.get("company_size", "any")
    keywords_include = body.get("keywords_include", [])
    keywords_exclude = body.get("keywords_exclude", [])
    min_ai_score = body.get("min_ai_score", 5)
    is_active = body.get("is_active", True)

    if not business_id:
        return JSONResponse({"error": "business_id is required"}, status_code=400)

    sb = _sb()
    record = {
        "id": str(uuid.uuid4()),
        "account_id": account_id,
        "business_id": business_id,
        "name": name,
        "industries": industries,
        "locations": locations,
        "company_size": company_size,
        "keywords_include": keywords_include,
        "keywords_exclude": keywords_exclude,
        "min_ai_score": min_ai_score,
        "is_active": is_active,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        result = sb.table("target_profiles").insert(record).execute()
        created = result.data[0] if result.data else record
        return JSONResponse({"success": True, "profile": created})
    except Exception as e:
        print(f"[Settings] Create profile error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/target-profiles/{profile_id}")
async def api_update_profile(profile_id: str, request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    # Only send fields that exist in the table
    allowed_keys = {"name", "business_id", "industries", "locations", "company_size",
                    "keywords_include", "keywords_exclude", "min_ai_score", "is_active"}
    updates = {k: v for k, v in body.items() if k in allowed_keys}

    sb = _sb()
    try:
        sb.table("target_profiles").update(updates).eq("id", profile_id).eq("account_id", user["account_id"]).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[Settings] Update profile error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/target-profiles/{profile_id}")
async def api_delete_profile(profile_id: str, request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    sb = _sb()
    try:
        sb.table("target_profiles").delete().eq("id", profile_id).eq("account_id", user["account_id"]).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[Settings] Delete profile error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Business info API ──────────────────────────────────────────────────────


@router.get("/api/businesses")
async def api_list_businesses(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    sb = _sb()
    try:
        result = sb.table("sales_businesses").select("*").eq("account_id", user["account_id"]).execute()
        return JSONResponse({"businesses": result.data or []})
    except Exception as e:
        print(f"[Settings] Load businesses error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/businesses/{business_id}")
async def api_update_business(business_id: str, request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    allowed_keys = {"description", "value_proposition", "target_industries", "name"}
    updates = {k: v for k, v in body.items() if k in allowed_keys}

    sb = _sb()
    try:
        sb.table("sales_businesses").update(updates).eq("id", business_id).eq("account_id", user["account_id"]).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[Settings] Update business error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Follow-up Settings API (stored in accounts.followup_settings JSON) ──────


@router.get("/api/followup-settings")
async def api_get_followup_settings(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    sb = _sb()
    account = safe_single(
        lambda: sb.table("accounts").select("followup_settings").eq("id", account_id).single(),
        default=None,
    )
    settings = account.get("followup_settings", {}) if account else {}

    defaults = {
        "first_followup_days": 3,
        "second_followup_days": 5,
        "send_start_hour": 9,
        "send_end_hour": 18,
        "max_followups": 2,
        "timezone": "Asia/Kuala_Lumpur",
    }
    for k, v in defaults.items():
        settings.setdefault(k, v)

    return JSONResponse({"settings": settings})


@router.post("/api/followup-settings")
async def api_save_followup_settings(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    sb = _sb()
    try:
        sb.table("accounts").update({"followup_settings": body}).eq("id", account_id).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[Settings] Followup settings error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Dashboard Banner API ────────────────────────────────────────────────


@router.get("/api/banners")
async def api_list_banners(request: Request):
    """List active banners (visible to all authenticated users)."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"banners": []})

    sb = _sb()
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        result = (
            sb.table("dashboard_banners")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        banners = result.data or []
        # Filter by expiry
        active = [b for b in banners if not b.get("expires_at") or b["expires_at"] > now]
        return JSONResponse({"banners": active})
    except Exception as e:
        print(f"[Settings] Banner error: {e}")
        return JSONResponse({"banners": []})