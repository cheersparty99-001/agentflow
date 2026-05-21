import os
import traceback
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.responses import PlainTextResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_count, safe_insert, safe_update
from routers.auth import get_current_user, login_page
import config as cfg
from datetime import datetime, timedelta, date

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    account_id = user.get("account_id")
    sb = get_supabase()

    account = safe_single(lambda: sb.table("accounts").select("agency_name,language,reminder_days,modules,monthly_fee,billing_notes,plan_notes,is_active").eq("id", account_id).single(), default={"agency_name": "Demo Insurance Agency", "language": "en", "reminder_days": [30, 14, 7], "modules": {}})
    agency_name = account.get("agency_name", "Agency") if account else "Agency"

    today = date.today()
    thirty = today + timedelta(days=30)
    fourteen = today + timedelta(days=14)
    seven = today + timedelta(days=7)

    total_count = safe_count(
        lambda: sb.table("policies").select("id", count="exact").eq("account_id", account_id),
        default=5,
    )

    exp_30_count = safe_count(
        lambda: sb.table("policies").select("id", count="exact")
            .eq("account_id", account_id)
            .lte("expiry_date", thirty.isoformat())
            .gte("expiry_date", today.isoformat()),
        default=1,
    )

    exp_14_count = safe_count(
        lambda: sb.table("policies").select("id", count="exact")
            .eq("account_id", account_id)
            .lte("expiry_date", fourteen.isoformat())
            .gte("expiry_date", today.isoformat()),
        default=2,
    )

    exp_7_count = safe_count(
        lambda: sb.table("policies").select("id", count="exact")
            .eq("account_id", account_id)
            .lte("expiry_date", seven.isoformat())
            .gte("expiry_date", today.isoformat()),
        default=2,
    )

    logs = safe_multi(
        lambda: sb.table("agent_logs").select("*").eq("account_id", account_id).order("created_at", desc=True).limit(10),
        default=[],
    )

    # In demo mode, use app state logs instead of empty Supabase results
    if cfg.DEMO_MODE and not logs:
        logs = sorted(request.app.state.demo_logs, key=lambda x: x.get("created_at", ""), reverse=True)[:10]

    # Insurance type distribution
    demo_type_counts = {"motor": 3, "medical": 2, "fire": 2, "travel": 1}

    template = env.get_template("dashboard.html")
    html = template.render(
        agency_name=agency_name,
        total_policies=total_count,
        expiring_30=exp_30_count,
        expiring_14=exp_14_count,
        expiring_7=exp_7_count,
        recent_logs=logs,
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
        motor_count=demo_type_counts.get("motor", 0),
        medical_count=demo_type_counts.get("medical", 0),
        fire_count=demo_type_counts.get("fire", 0),
        travel_count=demo_type_counts.get("travel", 0),
    )
    return HTMLResponse(html)