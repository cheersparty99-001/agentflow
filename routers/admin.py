import os
import html
import uuid
import httpx
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_count, safe_insert, safe_update
from routers.auth import get_current_user
import config as cfg
from datetime import datetime, date, timedelta, timezone

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


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

    # Fetch pending accounts and onboarding tokens from DB
    pending_accounts = []
    onboarding_tokens = []
    try:
        sb = get_supabase()
        pa = sb.table("accounts").select("*").eq("status", "pending").execute()
        if pa and pa.data:
            # For each pending account, try to find the associated user email
            for acct in pa.data:
                user_rec = sb.table("users").select("email").eq("account_id", acct["id"]).maybe_single().execute()
                pending_accounts.append({
                    "id": acct["id"],
                    "agency_name": acct.get("agency_name", ""),
                    "email": user_rec.data.get("email", "") if user_rec and user_rec.data else "",
                    "created_at": acct.get("created_at", ""),
                })
    except Exception as e:
        print(f"[admin] Error fetching pending accounts: {e}")

    # Fetch all active accounts
    accounts = []
    try:
        sb = get_supabase()
        result = sb.table("accounts").select("*").eq("status", "active").execute()
        accounts = result.data if result.data else []
    except Exception as e:
        print(f"[admin] Error fetching accounts: {e}")

    try:
        sb = get_supabase()
        ot = sb.table("onboarding_tokens").select("*").order("created_at", desc=True).execute()
        if ot and ot.data:
            onboarding_tokens = ot.data
    except Exception as e:
        print(f"[admin] Error fetching onboarding tokens: {e}")

    template = env.get_template("admin/accounts.html")
    html = template.render(
        accounts=accounts,
        pending_accounts=pending_accounts,
        onboarding_tokens=onboarding_tokens,
        agency_name="Admin Panel",
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

    try:
        sb = get_supabase()
        new_id = str(uuid.uuid4())
        sb.table("accounts").insert({
            "id": new_id,
            "agency_name": agency_name,
            "phone": phone,
            "email": email,
            "monthly_fee": float(monthly_fee),
            "is_active": True,
            "plan_notes": "New Account",
            "billing_notes": "",
        }).execute()
        return JSONResponse({"success": True, "id": new_id})
    except Exception as e:
        print(f"[admin] Error creating account: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/admin/accounts/edit/{account_id}", response_class=HTMLResponse)
async def admin_edit_account_page(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    # Look up the account by ID
    try:
        sb = get_supabase()
        result = sb.table("accounts").select("*").eq("id", account_id).maybe_single().execute()
        account = result.data if result else None
    except Exception as e:
        print(f"[admin] Error fetching account {account_id}: {e}")
        account = None

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

    try:
        sb = get_supabase()
        sb.table("accounts").update({
            "agency_name": agency_name,
            "phone": phone,
            "email": email,
            "monthly_fee": float(monthly_fee),
        }).eq("id", account_id).execute()
    except Exception as e:
        print(f"[admin] Error updating account: {e}")

    return RedirectResponse(url="/admin/accounts", status_code=302)


@router.post("/admin/accounts/suspend/{account_id}")
async def admin_suspend_account(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    try:
        sb = get_supabase()
        acct = sb.table("accounts").select("is_active").eq("id", account_id).maybe_single().execute()
        if acct and acct.data:
            current = acct.data.get("is_active", True)
            new_active = not current
            sb.table("accounts").update({
                "is_active": new_active,
                "plan_notes": "Active" if new_active else "Suspended",
            }).eq("id", account_id).execute()
    except Exception as e:
        print(f"[admin] Error toggling account status: {e}")

    return JSONResponse({"success": True})


@router.get("/admin/account/{account_id}", response_class=HTMLResponse)
async def admin_account_detail(account_id: str, request: Request):
    user = await require_admin(request)
    if not user:
        return RedirectResponse(url="/login")

    account = None
    logs = []
    try:
        sb = get_supabase()
        acct = sb.table("accounts").select("*").eq("id", account_id).maybe_single().execute()
        if acct and acct.data:
            account = acct.data
        # Fetch recent logs for this account
        log_result = sb.table("agent_logs").select("*").eq("account_id", account_id).order("created_at", desc=True).limit(20).execute()
        if log_result and log_result.data:
            logs = log_result.data
    except Exception as e:
        print(f"[admin] Error fetching account detail: {e}")

    if not account:
        return HTMLResponse("<html><body><h1>Account not found</h1></body></html>", status_code=404)

    template = env.get_template("admin/account_detail.html")
    html = template.render(
        account=account,
        logs=logs,
        agency_name="Admin Panel",
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
    try:
        sb = get_supabase()
        result = sb.table("agent_logs").select("*").order("created_at", desc=True).limit(100).execute()
        if result and result.data:
            logs = result.data
    except Exception as e:
        print(f"[admin] Error fetching logs: {e}")

    template = env.get_template("admin/logs.html")
    html = template.render(
        logs=logs[:100],
        agency_name="Admin Panel",
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
    try:
        sb = get_supabase()
        query = sb.table("agent_logs").select("*")
        if module:
            query = query.eq("module", module)
        if status:
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).limit(limit).execute()
        if result and result.data:
            logs = result.data
    except Exception as e:
        print(f"[admin] Error fetching API logs: {e}")

    return JSONResponse(logs)


@router.get("/admin/api/logs/export")
async def admin_export_logs(request: Request):
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    logs = []
    try:
        sb = get_supabase()
        result = sb.table("agent_logs").select("*").order("created_at", desc=True).execute()
        if result and result.data:
            logs = result.data
    except Exception as e:
        print(f"[admin] Error fetching logs for export: {e}")

    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Module", "Action", "Customer", "Type", "Status", "Message"])
    for l in logs:
        writer.writerow([
            l.get("created_at", ""),
            l.get("module", ""),
            l.get("action", ""),
            l.get("customer", ""),
            l.get("status", ""),
            l.get("message", ""),
        ])
    csv_content = output.getvalue()
    output.close()

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=agent_logs.csv"})


# --- Onboarding API Routes ---

@router.get("/api/onboarding/tokens")
async def api_onboarding_tokens(request: Request):
    """List all onboarding tokens."""
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    tokens = []
    try:
        sb = get_supabase()
        result = sb.table("onboarding_tokens").select("*").order("created_at", desc=True).execute()
        if result and result.data:
            tokens = result.data
    except Exception as e:
        print(f"[admin] Error fetching tokens: {e}")

    return JSONResponse(tokens)


@router.post("/api/onboarding/generate-token")
async def api_onboarding_generate_token(request: Request):
    """Generate a new onboarding token (7 day expiry)."""
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    try:
        sb = get_supabase()
        token_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=7)

        sb.table("onboarding_tokens").insert({
            "token": token_uuid,
            "created_by": user.get("email", ""),
            "expires_at": expires_at.isoformat(),
        }).execute()

        return JSONResponse({
            "token": token_uuid,
            "url": f"https://flowreach.work/register?token={token_uuid}"
        })
    except Exception as e:
        print(f"[admin] Error generating token: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/onboarding/approve")
async def api_onboarding_approve(request: Request):
    """Approve a pending account — set status=active, assign plan, create usage_limits, send activation email."""
    user = await require_admin(request)
    if not user:
        return JSONResponse({"error": "Not authorized"}, status_code=403)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    account_id = body.get("account_id", "")
    plan = body.get("plan", "")

    if not account_id or not plan:
        return JSONResponse({"error": "account_id and plan are required"}, status_code=400)

    if plan not in ("Starter", "Growth", "Pro"):
        return JSONResponse({"error": "Invalid plan. Must be Starter, Growth, or Pro"}, status_code=400)

    # Define plan limits
    plan_limits = {
        "Starter": {"leads_per_month": 100, "messages_per_month": 300},
        "Growth": {"leads_per_month": 300, "messages_per_month": 1000},
        "Pro": {"leads_per_month": 800, "messages_per_month": 3000},
    }
    limits = plan_limits[plan]

    sb = get_supabase()

    # Update account status and plan
    try:
        sb.table("accounts").update({
            "status": "active",
            "plan": plan,
        }).eq("id", account_id).execute()
    except Exception as e:
        return JSONResponse({"error": f"Failed to update account: {str(e)}"}, status_code=500)

    # Create usage_limits record
    try:
        sb.table("usage_limits").insert({
            "account_id": account_id,
            "monthly_lead_limit": limits["leads_per_month"],
            "monthly_message_limit": limits["messages_per_month"],
        }).execute()
    except Exception as e:
        print(f"[admin] Error creating usage_limits: {e}")

    # Find user email for activation email
    customer_email = ""
    customer_name = ""
    try:
        user_rec = sb.table("users").select("email").eq("account_id", account_id).maybe_single().execute()
        if user_rec and user_rec.data:
            customer_email = user_rec.data.get("email", "")
    except Exception:
        pass

    try:
        acct_rec = sb.table("accounts").select("agency_name").eq("id", account_id).maybe_single().execute()
        if acct_rec and acct_rec.data:
            customer_name = acct_rec.data.get("agency_name", "")
    except Exception:
        pass

    # Send activation email
    if cfg.RESEND_API_KEY and customer_email:
        email_body = f"""Hi {customer_name},

Your Flowreach account is ready!

Log in here: https://flowreach.work/login

Email: {customer_email}
Plan: {plan}

Your team will be in touch shortly to help you get started.

Best,
The Flowreach Team
"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                req_body = {
                    "from": "Flowreach <yy@flowreach.work>",
                    "to": [customer_email],
                    "subject": "Your Flowreach account is ready",
                    "text": email_body,
                }
                print(f"[admin] Sending activation email to {customer_email}")
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {cfg.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=req_body,
                )
                if resp.status_code >= 400:
                    print(f"[admin] Resend activation error: {resp.status_code} {resp.text[:200]}")
                else:
                    print(f"[admin] Activation email sent successfully")
        except Exception as e:
            print(f"[admin] Resend API error: {e}")
    else:
        print(f"[admin] RESEND_API_KEY not configured or no email — skipping activation email")

    return JSONResponse({"success": True, "message": f"Account approved with {plan} plan"})