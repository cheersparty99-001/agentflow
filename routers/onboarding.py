import uuid
import datetime
import httpx
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_insert, safe_update
import config as cfg

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"), autoescape=True)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, token: str = ""):
    """GET /register — show the registration form or an error page."""
    state = "form"
    error_msg = ""

    if not token:
        state = "invalid"
        error_msg = "Missing registration token. Please use the link from your invitation email."
    else:
        try:
            sb = get_supabase()
            result = sb.table("onboarding_tokens").select("*").eq("token", token).maybe_single().execute()
            tok = result.data if result else None
        except Exception:
            tok = None

        if not tok:
            state = "invalid"
            error_msg = "Invalid registration token. Please check your invitation link."
        elif tok.get("used"):
            state = "used"
            error_msg = "This registration link has already been used. Please contact yy@flowreach.work if you need a new one."
        else:
            try:
                expires = tok.get("expires_at")
                if expires:
                    # Parse ISO format timestamp
                    if isinstance(expires, str):
                        expires_dt = datetime.datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    else:
                        expires_dt = expires
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if now > expires_dt:
                        state = "expired"
                        error_msg = "This registration link has expired. Please contact yy@flowreach.work for a new invitation."
            except Exception as e:
                print(f"[register] Error parsing expiry: {e}")

    template = env.get_template("register.html")
    html = template.render(
        state=state,
        error_msg=error_msg,
        token=token,
    )
    return HTMLResponse(html)


@router.post("/register")
async def register_submit(request: Request):
    """POST /register — handle registration form submission."""
    # Parse JSON body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON body"})

    token_str = body.get("token", "")
    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    company = body.get("company", "").strip()

    # Basic validation
    errors = []
    if not token_str:
        errors.append("Missing registration token")
    if not name:
        errors.append("Name is required")
    if not email or "@" not in email:
        errors.append("Valid email is required")
    if not password or len(password) < 6:
        errors.append("Password must be at least 6 characters")
    if not company:
        errors.append("Company name is required")
    if errors:
        return JSONResponse(status_code=400, content={"detail": "; ".join(errors)})

    sb = get_supabase()

    # Step 1: Verify token exists, not used, not expired
    try:
        result = sb.table("onboarding_tokens").select("*").eq("token", token_str).maybe_single().execute()
        tok = result.data if result else None
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": f"Error verifying token: {str(e)}"})

    if not tok:
        return JSONResponse(status_code=400, content={"detail": "Invalid registration token"})
    if tok.get("used"):
        return JSONResponse(status_code=400, content={"detail": "This token has already been used"})
    try:
        expires = tok.get("expires_at")
        if expires:
            if isinstance(expires, str):
                expires_dt = datetime.datetime.fromisoformat(expires.replace("Z", "+00:00"))
            else:
                expires_dt = expires
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > expires_dt:
                return JSONResponse(status_code=400, content={"detail": "This token has expired"})
    except Exception as e:
        print(f"[register] Error checking expiry: {e}")

    # Step 2: Sign up with Supabase Auth
    try:
        res = sb.auth.sign_up({"email": email, "password": password})
        user = res.user
        if not user:
            return JSONResponse(status_code=500, content={"detail": "Failed to create user account"})
    except Exception as e:
        error_msg = str(e)
        if "already" in error_msg.lower():
            return JSONResponse(status_code=400, content={"detail": "An account with this email already exists"})
        return JSONResponse(status_code=500, content={"detail": f"Authentication error: {error_msg}"})

    # Step 3: Create account record
    account_id = str(uuid.uuid4())
    try:
        sb.table("accounts").insert({
            "id": account_id,
            "agency_name": company,
            "status": "pending",
            "plan": None,
        }).execute()
    except Exception as e:
        print(f"[register] Error creating account: {e}")
        return JSONResponse(status_code=500, content={"detail": "Failed to create account"})

    # Step 4: Create user record
    try:
        sb.table("users").insert({
            "id": user.id,
            "email": email,
            "account_id": account_id,
            "role": "client",
        }).execute()
    except Exception as e:
        print(f"[register] Error creating user: {e}")
        return JSONResponse(status_code=500, content={"detail": "Failed to create user profile"})

    # Step 5: Mark token as used
    try:
        sb.table("onboarding_tokens").update({
            "used": True,
            "account_id": account_id,
        }).eq("token", token_str).execute()
    except Exception as e:
        print(f"[register] Error marking token used: {e}")

    # Step 6: Send notification email to yy@flowreach.work
    if cfg.RESEND_API_KEY:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        email_body = f"""New Registration — {company}

Name: {name}
Company: {company}
Email: {email}
Registered at: {now_str}
Account ID: {account_id}

A new client has registered and is pending activation. Please review and approve in the admin panel.
"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                req_body = {
                    "from": "Flowreach <yy@flowreach.work>",
                    "to": ["yy@flowreach.work"],
                    "subject": f"New Registration — {company}",
                    "text": email_body,
                }
                print(f"[register] Sending notification to yy@flowreach.work")
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {cfg.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=req_body,
                )
                if resp.status_code >= 400:
                    print(f"[register] Resend notification error: {resp.status_code} {resp.text[:200]}")
                else:
                    print(f"[register] Notification sent successfully")
        except Exception as e:
            print(f"[register] Resend API error: {e}")
    else:
        print("[register] RESEND_API_KEY not configured — skipping notification email")

    # Step 7: Return success
    template = env.get_template("register.html")
    html = template.render(
        state="success",
        error_msg="",
        token=token_str,
    )
    return HTMLResponse(html)