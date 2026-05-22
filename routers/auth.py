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
    if cfg.DEMO_MODE:
        if not password or len(password) < 4:
            raise HTTPException(status_code=401, detail="Invalid demo credentials")
        if email == "admin@agentflow.my":
            session_data = {
                "user_id": "admin-user",
                "account_id": "00000000-0000-0000-0000-000000000001",
                "role": "admin",
                "email": email,
                "is_admin": True,
            }
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(key="session", value=create_session_token(session_data), httponly=True, max_age=604800)
            return response
        if email == "demo@agentflow.my":
            session_data = {
                "user_id": "demo-user",
                "account_id": "00000000-0000-0000-0000-000000000001",
                "role": "client",
                "email": email,
                "is_admin": False,
            }
            response = RedirectResponse(url="/dashboard", status_code=302)
            response.set_cookie(key="session", value=create_session_token(session_data), httponly=True, max_age=604800)
            return response
        raise HTTPException(status_code=401, detail="Demo: use demo@agentflow.my")

    sb = get_supabase()
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_db = sb.table("users").select("*").eq("email", email).single().execute()
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

        session_data = {
            "user_id": user.id,
            "account_id": account_id,
            "role": user_db.data.get("role", "client") if user_db.data else "client",
            "email": email,
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