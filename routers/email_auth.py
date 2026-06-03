"""Email connection auth endpoints — Google OAuth, Outlook, SMTP.

/email/connect/google     → redirects to Google OAuth consent
/email/callback/google    → handles OAuth callback, stores tokens
/email/status             → returns current email connection state
/email/disconnect         → removes stored connection
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

from routers.auth import get_current_user
from services.sales.oauth import GoogleOAuth
import config as cfg

router = APIRouter()
google_oauth = GoogleOAuth()


@router.get("/email/connect/google")
async def email_connect_google(request: Request):
    """Redirect the user to Google OAuth consent screen."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    account_id = user.get("account_id", "")
    # Determine redirect_uri based on host
    host = request.base_url
    redirect_uri = f"{host}email/callback/google"

    # DEBUG: confirm runtime value of GMAIL_CLIENT_ID
    raw = cfg.GMAIL_CLIENT_ID
    print(f"[DEBUG email_connect_google] GMAIL_CLIENT_ID len={len(raw)} first4={raw[:4]!r} last4={raw[-4:]!r}")

    # DEBUG: confirm redirect_uri exactly as sent to Google
    print(f"[DEBUG email_connect_google] redirect_uri={redirect_uri!r}")

    auth_url = google_oauth.get_auth_url(account_id, redirect_uri)
    return RedirectResponse(url=auth_url)


@router.get("/email/callback/google")
async def email_callback_google(request: Request, code: str = "", state: str = "", error: str = ""):
    """Handle Google OAuth callback — exchange code for tokens."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    if error:
        print(f"[EmailAuth] Google OAuth error: {error}")
        return RedirectResponse(url="/settings?email_error=" + error)

    account_id = state or user.get("account_id", "")
    redirect_uri = f"{request.base_url}email/callback/google"

    try:
        conn = google_oauth.handle_callback(code, account_id, str(redirect_uri))
        print(f"[EmailAuth] Google connected: {conn.get('email', '')}")
        return RedirectResponse(url="/settings?email_connected=google")
    except Exception as e:
        print(f"[EmailAuth] Callback error: {e}")
        return RedirectResponse(url="/settings?email_error=" + str(e)[:50])


@router.get("/email/status")
async def email_status(request: Request):
    """Return the current email connection status for the logged-in account."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"connected": False}, status_code=401)

    account_id = user.get("account_id", "")
    conn = google_oauth.get_connection(account_id)

    if conn:
        return JSONResponse({
            "connected": True,
            "provider": "google",
            "email": conn.get("email", ""),
            "connected_at": conn.get("connected_at", ""),
        })
    return JSONResponse({"connected": False})


@router.post("/email/disconnect")
async def email_disconnect(request: Request):
    """Remove the Google email connection for this account."""
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id", "")
    ok = google_oauth.disconnect(account_id)
    return JSONResponse({"disconnected": ok})