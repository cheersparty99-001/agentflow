import os
import traceback
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.responses import PlainTextResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_count, safe_insert, safe_update
from routers.auth import get_current_user
import config as cfg
from datetime import datetime, timedelta, date

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

    account = safe_single(lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(), default={"agency_name": "Demo Insurance Agency"})
    agency_name = account.get("agency_name", "Agency") if account else "Agency"

    template = env.get_template("settings.html")
    html = template.render(
        agency_name=agency_name,
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
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
            "agency_name": "Demo Insurance Agency",
            "phone": "0123456789",
            "email": "demo@agentflow.my",
            "business_hours": "Mon-Fri 9AM-6PM, Sat 9AM-1PM",
            "twilio_sid": "",
            "twilio_token": "",
            "whatsapp_from": "",
            "language": "en",
            "reminder_days": [30, 14, 7],
            "modules": {"renewal_reminder": True, "enquiry_handler": False, "quotation_formatter": False, "claims_tracker": False},
        })

    return JSONResponse({
        "agency_name": data.get("agency_name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "business_hours": data.get("business_hours", ""),
        "twilio_sid": data.get("twilio_sid", ""),
        "twilio_token": data.get("twilio_token", ""),
        "whatsapp_from": data.get("whatsapp_from", ""),
        "language": data.get("language", "en"),
        "reminder_days": data.get("reminder_days", [30, 14, 7]),
        "modules": data.get("modules", {}),
    })


@router.post("/api/settings")
async def save_settings(
    request: Request,
    agency_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    business_hours: str = Form(""),
    twilio_sid: str = Form(""),
    twilio_token: str = Form(""),
    whatsapp_from: str = Form(""),
    language: str = Form("en"),
    reminder_days: list[str] = Form([]),
    module_renewal_reminder: str = Form("off"),
    module_enquiry_handler: str = Form("off"),
    module_quotation_formatter: str = Form("off"),
    module_claims_tracker: str = Form("off"),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    sb = get_supabase()

    days = [int(d) for d in reminder_days if d.strip()]
    modules = {
        "renewal_reminder": module_renewal_reminder == "on",
        "enquiry_handler": module_enquiry_handler == "on",
        "quotation_formatter": module_quotation_formatter == "on",
        "claims_tracker": module_claims_tracker == "on",
    }

    safe_update("accounts", {
        "agency_name": agency_name,
        "phone": phone,
        "email": email,
        "business_hours": business_hours,
        "twilio_sid": twilio_sid,
        "twilio_token": twilio_token,
        "whatsapp_from": whatsapp_from,
        "language": language,
        "reminder_days": days,
        "modules": modules,
    }, "id", account_id)

    return JSONResponse({"success": True})