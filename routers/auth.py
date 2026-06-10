from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from itsdangerous import URLSafeTimedSerializer
import config as cfg
from services.supabase_client import get_supabase

router = APIRouter()

serializer = URLSafeTimedSerializer(cfg.SECRET_KEY, salt="auth-session")


def create_session_token(data: dict) -> str:
    return serializer.dumps(data)


def read_session_token(token: str) -> dict | None:
    try:
        return serializer.loads(token, max_age=86400 * 7)
    except Exception:
        return None


async def get_current_user(request: Request):
    token = request.cookies.get("session")
    if not token:
        return None
    data = read_session_token(token)
    if not data:
        return None
    return data


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    with open("templates/login.html") as f:
        return HTMLResponse(f.read())


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    sb = get_supabase()
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_db = sb.table("users").select("*").eq("email", email).maybe_single().execute()
        if not user_db.data:
            user_data = user.user_metadata or {}
            sb.table("users").insert({
                "id": user.id,
                "email": email,
                "role": "client",
            }).execute()
            account_id = None
        else:
            account_id = user_db.data.get("account_id")

        # Check account status if account_id exists
        if account_id:
            try:
                acct = sb.table("accounts").select("status").eq("id", account_id).maybe_single().execute()
                if acct and acct.data:
                    acct_status = acct.data.get("status", "active")
                    if acct_status == "pending":
                        with open("templates/login.html") as f:
                            html = f.read()
                        error_html = html.replace(
                            '</form>',
                            f'</form><div class="mt-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm">Your account is pending activation. We\'ll notify you at <strong>{email}</strong> within 24 hours.</div>'
                        )
                        return HTMLResponse(error_html)
                    elif acct_status not in ("active", None):
                        with open("templates/login.html") as f:
                            html = f.read()
                        error_html = html.replace(
                            '</form>',
                            f'</form><div class="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">Your account is not active. Contact yy@flowreach.work</div>'
                        )
                        return HTMLResponse(error_html)
            except Exception as e:
                print(f"[auth] Error checking account status: {e}")
                with open("templates/login.html") as f:
                    html = f.read()
                error_html = html.replace(
                    '</form>',
                    f'</form><div class="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">Account not found. Contact yy@flowreach.work</div>'
                )
                return HTMLResponse(error_html)
        else:
            # No account found
            with open("templates/login.html") as f:
                html = f.read()
            error_html = html.replace(
                '</form>',
                f'</form><div class="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">Account not found. Contact yy@flowreach.work</div>'
            )
            return HTMLResponse(error_html)

        session_data = {
            "user_id": user.id,
            "account_id": account_id,
            "role": user_db.data.get("role", "client") if user_db.data else "client",
            "email": email,
            "is_admin": user_db.data.get("role") == "admin" if user_db.data else False,
        }
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="session", value=create_session_token(session_data), httponly=True, max_age=604800)
        return response
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response