import os
import traceback
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_update
from routers.auth import get_current_user
import config as cfg

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    account_id = user.get("account_id")
    sb = get_supabase()
    account = safe_single(lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(), default={"agency_name": "My Agency"})
    agency_name = account.get("agency_name", "My Agency") if account else "My Agency"

    # Load target profiles
    target_profiles = getattr(request.app.state, 'sales_target_profiles', [])
    if not target_profiles:
        target_profiles = []

    template = env.get_template("settings.html")
    html = template.render(
        agency_name=agency_name,
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
        target_profiles=target_profiles,
    )
    return HTMLResponse(html)


@router.get("/api/settings")
async def get_settings(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    sb = get_supabase()
    data = safe_single(lambda: sb.table("accounts").select("*").eq("id", account_id).single(), default=None)
    if not data:
        return JSONResponse({
            "agency_name": "My Agency",
            "phone": "",
            "email": "demo@agentflow.my",
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
    sb = get_supabase()

    safe_update("accounts", {
        "agency_name": agency_name,
        "phone": phone,
        "email": email,
        "language": language,
    }, "id", account_id)

    return JSONResponse({"success": True})
