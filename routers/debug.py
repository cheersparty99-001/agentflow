"""Debug router — 500 error diagnostics, NOT for production."""
import traceback
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader

from routers.auth import get_current_user
from services.supabase_client import get_supabase, safe_single, safe_update
import config as cfg

router = APIRouter()
env = Environment(loader=FileSystemLoader("templates"))


@router.get("/debug/settings-test")
async def debug_settings_test(request: Request):
    """Exact clone of /settings logic, but returns traceback on error.
    Accessible without login — shows partial results if not authenticated."""
    lines = []
    def log(msg):
        lines.append(msg)

    try:
        user = await get_current_user(request)
        log(f"user={user.get('email') if user else 'NOT LOGGED IN'}")

        if not user:
            log("ERROR: No authenticated user — cannot test full settings page")
            return HTMLResponse("<pre>" + "\n".join(lines) + "\n\nLogin required to test settings page.</pre>")

        account_id = user.get("account_id")
        sb = get_supabase()

        # Account query
        try:
            account_raw = sb.table("accounts").select("agency_name").eq("id", account_id).single().execute()
            account = account_raw.data or {"agency_name": "My Agency"}
            log(f"account={account.get('agency_name')}")
        except Exception as e:
            log(f"account query ERROR: {e}")
            account = {"agency_name": "My Agency"}

        agency_name = account.get("agency_name", "My Agency")

        # Target profiles
        target_profiles = getattr(request.app.state, 'sales_target_profiles', [])
        log(f"target_profiles from state={len(target_profiles)}")

        # Email status
        email_status = {"connected": False}
        try:
            from services.sales.oauth import GoogleOAuth
            log("GoogleOAuth imported OK")
            email_conn = GoogleOAuth().get_connection(account_id)
            log(f"get_connection returned: {email_conn}")
            if email_conn:
                email_status = {
                    "connected": True,
                    "provider": email_conn.get("provider"),
                    "email": email_conn.get("email"),
                    "connected_at": email_conn.get("connected_at"),
                }
        except Exception as e:
            log(f"Email status ERROR: {type(e).__name__}: {e}")
            tb = traceback.format_exc()
            log(tb)

        # Template
        try:
            tmpl = env.get_template("settings.html")
            log("template loaded OK")
            html = tmpl.render(
                agency_name=agency_name,
                current_path=request.url.path,
                is_admin=user.get("is_admin", False),
                user_email=user.get("email", ""),
                target_profiles=target_profiles,
                email_status=email_status,
            )
            log(f"template rendered OK ({len(html)} bytes)")
            return HTMLResponse(html)
        except Exception as e:
            log(f"Template ERROR: {type(e).__name__}: {e}")
            tb = traceback.format_exc()
            log(tb)
    except Exception as e:
        log(f"Outer ERROR: {type(e).__name__}: {e}")
        tb = traceback.format_exc()
        log(tb)

    return HTMLResponse("<pre>" + "\n".join(lines) + "</pre>")