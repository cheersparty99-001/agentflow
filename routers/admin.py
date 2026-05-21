import os
import html
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_count, safe_insert, safe_update
from routers.auth import get_current_user
import config as cfg
from datetime import datetime, date

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


async def require_admin(request: Request):
    user = await get_current_user(request)
    if not user or not user.get("is_admin"):
        return None
    return user


# --- Demo in-memory data ---
DEMO_ACCOUNTS = [
    {"id": "a1", "agency_name": "Demo Insurance Agency", "phone": "0123456789", "email": "demo@agentflow.my", "monthly_fee": 99.00, "is_active": True, "plan_notes": "Active Plan", "billing_notes": "", "created_at": "2026-01-15T08:00:00"},
    {"id": "a2", "agency_name": "Puncak Insurance Brokers", "phone": "0134567890", "email": "admin@puncak.com", "monthly_fee": 199.00, "is_active": True, "plan_notes": "Premium Plan", "billing_notes": "", "created_at": "2026-02-01T10:00:00"},
    {"id": "a3", "agency_name": "Jalan Insurance Agency", "phone": "0145678901", "email": "info@jalanins.com", "monthly_fee": 49.00, "is_active": False, "plan_notes": "Suspended - overdue", "billing_notes": "Invoice #INV-003 overdue 45 days", "created_at": "2026-03-10T09:00:00"},
]


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")
    
    html = """
    <html><head><meta http-equiv="refresh" content="0;url=/admin/accounts"></head><body></body></html>
    """
    return HTMLResponse(html)


@router.get("/admin/accounts", response_class=HTMLResponse)
async def admin_accounts(request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    accounts = DEMO_ACCOUNTS if cfg.DEMO_MODE else []
    template = env.get_template("admin/accounts.html")
    html = template.render(
        accounts=accounts,
        agency_name="Admin Panel",
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=True,
        user_email=user.get("email", ""),
    )
    return HTMLResponse(html)


@router.get("/admin/accounts/create", response_class=HTMLResponse)
async def admin_create_account_page(request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")
    return HTMLResponse("""
    <html><body><h1>Create Account</h1><p>Form coming soon.</p><a href="/admin/accounts">Back</a></body></html>
    """)


@router.post("/admin/accounts/create")
async def admin_create_account(
    request: Request,
    agency_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    monthly_fee: str = Form("0"),
):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    if cfg.DEMO_MODE:
        new_id = f"a{len(DEMO_ACCOUNTS) + 1}"
        DEMO_ACCOUNTS.append({
            "id": new_id,
            "agency_name": agency_name,
            "phone": phone,
            "email": email,
            "monthly_fee": float(monthly_fee),
            "is_active": True,
            "plan_notes": "New Account",
            "billing_notes": "",
            "created_at": datetime.utcnow().isoformat(),
        })
        return JSONResponse({"success": True, "id": new_id})

    return JSONResponse({"success": True})


@router.get("/admin/accounts/edit/{account_id}", response_class=HTMLResponse)
async def admin_edit_account_page(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    account = None
    if cfg.DEMO_MODE:
        for a in DEMO_ACCOUNTS:
            if a["id"] == account_id:
                account = a
                break

    if not account:
        return HTMLResponse("<html><body><h1>Account not found</h1></body></html>", status_code=404)

    return HTMLResponse(f"""
    <html>
    <body>
        <h1>Edit Account: {html.escape(account['agency_name'])}</h1>
        <form method="post" action="/admin/accounts/edit/{account_id}">
            <p>Agency Name: <input name="agency_name" value="{html.escape(account['agency_name'])}"></p>
            <p>Phone: <input name="phone" value="{html.escape(account['phone'])}"></p>
            <p>Email: <input name="email" value="{html.escape(account['email'])}"></p>
            <p>Monthly Fee: <input name="monthly_fee" value="{html.escape(account['monthly_fee'])}"></p>
            <p><button type="submit">Save</button></p>
        </form>
        <a href="/admin/accounts">Back</a>
    </body>
    </html>
    """)


@router.post("/admin/accounts/edit/{account_id}")
async def admin_edit_account(
    account_id: str,
    request: Request,
    agency_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    monthly_fee: str = Form("0"),
):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    if cfg.DEMO_MODE:
        for a in DEMO_ACCOUNTS:
            if a["id"] == account_id:
                a["agency_name"] = agency_name
                a["phone"] = phone
                a["email"] = email
                a["monthly_fee"] = float(monthly_fee)
                break
        return RedirectResponse(url="/admin/accounts", status_code=302)

    return RedirectResponse(url="/admin/accounts", status_code=302)


@router.post("/admin/accounts/suspend/{account_id}")
async def admin_suspend_account(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    if cfg.DEMO_MODE:
        for a in DEMO_ACCOUNTS:
            if a["id"] == account_id:
                a["is_active"] = not a["is_active"]
                a["plan_notes"] = "Active" if a["is_active"] else "Suspended"
                break

    return JSONResponse({"success": True})


@router.get("/admin/account/{account_id}", response_class=HTMLResponse)
async def admin_account_detail(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    account = None
    logs = []
    if cfg.DEMO_MODE:
        for a in DEMO_ACCOUNTS:
            if a["id"] == account_id:
                account = a
                break
        logs = [l for l in request.app.state.demo_logs if l.get("account_id", "00000000-0000-0000-0000-000000000001") == "00000000-0000-0000-0000-000000000001"]
        logs = logs[:20]

    if not account:
        return HTMLResponse("<html><body><h1>Account not found</h1></body></html>", status_code=404)

    template = env.get_template("admin/account_detail.html")
    html = template.render(
        account=account,
        logs=logs,
        agency_name="Admin Panel",
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=True,
        user_email=user.get("email", ""),
    )
    return HTMLResponse(html)


@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    logs = []
    if cfg.DEMO_MODE:
        logs = sorted(request.app.state.demo_logs, key=lambda x: x.get("created_at", ""), reverse=True)

    template = env.get_template("admin/logs.html")
    html = template.render(
        logs=logs[:100],
        agency_name="Admin Panel",
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=True,
        user_email=user.get("email", ""),
    )
    return HTMLResponse(html)


@router.get("/admin/api/logs")
async def admin_api_logs(request: Request, module: str = "", status: str = "", limit: int = 50):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    logs = []
    if cfg.DEMO_MODE:
        logs = list(request.app.state.demo_logs)
        if module:
            logs = [l for l in logs if l.get("module", "") == module]
        if status:
            logs = [l for l in logs if l.get("status", "") == status]
        logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return JSONResponse(logs[:limit])


@router.get("/admin/api/logs/export")
async def admin_export_logs(request: Request):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    logs = []
    if cfg.DEMO_MODE:
        logs = sorted(request.app.state.demo_logs, key=lambda x: x.get("created_at", ""), reverse=True)

    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Module", "Action", "Customer", "Insurance Type", "Status", "Message"])
    for l in logs:
        writer.writerow([
            l.get("created_at", ""),
            l.get("module", ""),
            l.get("action", ""),
            l.get("customer", ""),
            l.get("insurance_type", ""),
            l.get("status", ""),
            l.get("message", ""),
        ])
    csv_content = output.getvalue()
    output.close()

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agent_logs.csv"})