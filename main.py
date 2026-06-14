import os
import signal
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import config as cfg

app = FastAPI(title="Flowreach", version="2.0.0")

# Prevent Railway edge from serving stale cached content
@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Clean shutdown on SIGTERM/SIGINT
def cleanup(signum, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

app.add_middleware(SessionMiddleware, secret_key=cfg.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/locales", StaticFiles(directory="locales"), name="locales")

from routers import auth, dashboard, settings, admin, sales, landing, email_auth, onboarding, ai_chat

app.include_router(landing.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(admin.router)
app.include_router(sales.router)
app.include_router(email_auth.router)
app.include_router(onboarding.router)
app.include_router(ai_chat.router)

_REQUIRED_ENV_VARS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SECRET_KEY",
]
# GMAIL vars are optional — only needed for the Connect Email feature
_GMAIL_ENV_VARS = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"]
_missing_required = [var for var in _REQUIRED_ENV_VARS if not getattr(cfg, var, None)]
if _missing_required:
    print(
        f"[Flowreach] FATAL: Missing required env vars: {', '.join(_missing_required)}",
        file=sys.stderr,
    )
    sys.exit(1)
missing_gmail = [var for var in _GMAIL_ENV_VARS if not getattr(cfg, var, None)]
if missing_gmail:
    print(
        f"[Flowreach] WARNING: Gmail env vars not set: {', '.join(missing_gmail)}. "
        "Connect Email feature will be unavailable.",
    )

@app.on_event("startup")
async def startup():
    or_key = cfg.OPENROUTER_API_KEY
    if or_key:
        print(f"[Flowreach] OPENROUTER_API_KEY: present (len={len(or_key)})")
    else:
        print("[Flowreach] WARNING: OPENROUTER_API_KEY is empty — AI scoring will use fallback")
