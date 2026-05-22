import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_insert
from services import renewal_reminder, birthday_greeting, quotation_formatter
from routers.auth import get_current_user
import config as cfg

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")
    
    account_id = user.get("account_id")
    sb = get_supabase()
    
    account = safe_single(lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(), default={"agency_name": "Demo Insurance Agency"})
    agency_name = account.get("agency_name", "Agency") if account else "Agency"
    
    template = env.get_template("agents.html")
    html = template.render(
        agency_name=agency_name,
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
    )
    return HTMLResponse(html)


@router.post("/agents/run/renewal-reminder")
async def run_renewal_reminder(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")
    result = renewal_reminder.run(account_id, demo_mode=cfg.DEMO_MODE, log_store=request.app.state.demo_logs)
    return JSONResponse(result)


@router.post("/agents/run/birthday-greeting")
async def run_birthday_greeting(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")
    result = birthday_greeting.run(account_id, demo_mode=cfg.DEMO_MODE, log_store=request.app.state.demo_logs)
    return JSONResponse(result)


@router.post("/agents/run/quotation-formatter")
async def run_quotation_formatter(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")
    result = quotation_formatter.run_all(account_id, demo_mode=cfg.DEMO_MODE, log_store=request.app.state.demo_logs)
    return JSONResponse(result)


@router.post("/agents/run/quotation-formatter/{policy_id}")
async def run_quotation_formatter_policy(request: Request, policy_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")
    result = quotation_formatter.run(account_id, policy_id=policy_id, demo_mode=cfg.DEMO_MODE, log_store=request.app.state.demo_logs)
    return JSONResponse(result)


@router.get("/agents/logs")
async def get_logs(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")
    if cfg.DEMO_MODE:
        logs = list(request.app.state.demo_logs)
        logs.reverse()
        return JSONResponse(logs[:50])
    sb = get_supabase()
    logs = safe_multi(
        lambda: sb.table("agent_logs").select("*").eq("account_id", account_id).order("created_at", desc=True).limit(50),
        default=[],
    )
    return JSONResponse(logs)