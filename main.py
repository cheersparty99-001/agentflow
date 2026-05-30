import os
import signal
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import config as cfg

app = FastAPI(title="AgentFlow", version="2.0.0")

# Clean shutdown on SIGTERM/SIGINT
def cleanup(signum, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

app.add_middleware(SessionMiddleware, secret_key=cfg.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/locales", StaticFiles(directory="locales"), name="locales")

from routers import auth, dashboard, settings, admin, sales, landing

app.include_router(landing.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(settings.router)
app.include_router(admin.router)
app.include_router(sales.router)

@app.on_event("startup")
async def startup():
    app.state.demo_logs = []
    app.state.demo_accounts = {}
    # Seed Sales Automation demo data
    from routers.sales import init_sales_demo_data
    init_sales_demo_data(app.state)
    missing = []
    required = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY"]
    for var in required:
        if not getattr(cfg, var, None):
            missing.append(var)
    if missing:
        print(f"[AgentFlow] WARNING: Missing env vars: {', '.join(missing)}")
    print(f"[AgentFlow] Demo mode: {cfg.DEMO_MODE}")
