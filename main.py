import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import config as cfg

app = FastAPI(title="AgentFlow", version="2.0.0")

app.add_middleware(SessionMiddleware, secret_key=cfg.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/locales", StaticFiles(directory="locales"), name="locales")

from routers import auth, dashboard, policies, agents, settings, admin, telegram_bot, cron, sales

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(policies.router)
app.include_router(agents.router)
app.include_router(settings.router)
app.include_router(admin.router)
app.include_router(telegram_bot.router)
app.include_router(cron.router)
app.include_router(sales.router)

@app.get("/")
async def root():
    return RedirectResponse(url="/login")

@app.on_event("startup")
async def startup():
    app.state.demo_logs = []
    app.state.demo_accounts = {}
    app.state.demo_policies = []
    # Seed Sales Automation demo data
    from routers.sales import init_sales_demo_data
    init_sales_demo_data(app.state)
    # Seed rich demo logs
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    rich_logs = [
        {"module": "renewal_reminder", "action": "send_reminder", "status": "success", "customer": "Ahmad Razif", "insurance_type": "motor", "policy_id": "d-p1", "account_id": "00000000-0000-0000-0000-000000000001", "message": "Sent 30-day reminder to 60123456789", "created_at": (now - timedelta(minutes=15)).isoformat()},
        {"module": "renewal_reminder", "action": "send_reminder", "status": "demo", "customer": "Tan Wei Ming", "insurance_type": "motor", "policy_id": "d-p2", "account_id": "00000000-0000-0000-0000-000000000001", "message": "DEMO -- Would send to 60198765432: Hi Tan Wei Ming...", "created_at": (now - timedelta(minutes=10)).isoformat()},
        {"module": "renewal_reminder", "action": "send_reminder", "status": "failed", "customer": "Priya Nair", "insurance_type": "medical", "policy_id": "d-p3", "account_id": "00000000-0000-0000-0000-000000000001", "message": "Failed to send to 60112223334", "created_at": (now - timedelta(minutes=5)).isoformat()},
        {"module": "renewal_reminder", "action": "send_reminder", "status": "success", "customer": "Nurul Ain", "insurance_type": "travel", "policy_id": "d-p5", "account_id": "00000000-0000-0000-0000-000000000001", "message": "Sent 7-day reminder to 60134445556", "created_at": (now - timedelta(minutes=2)).isoformat()},
    ]
    app.state.demo_logs.extend(rich_logs)
    missing = []
    required = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY"]
    for var in required:
        if not getattr(cfg, var, None):
            missing.append(var)
    if missing:
        print(f"[AgentFlow] WARNING: Missing env vars: {', '.join(missing)}")
    print(f"[AgentFlow] Demo mode: {cfg.DEMO_MODE}")

    # Set Telegram webhook on startup
    if cfg.TELEGRAM_BOT_TOKEN:
        railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
        if railway_url:
            webhook_url = f"https://{railway_url}/telegram/webhook"
        else:
            webhook_url = "https://agentflow-app-production.up.railway.app/telegram/webhook"
        from services.telegram_bot import set_webhook
        set_webhook(webhook_url, secret_token=cfg.TELEGRAM_BOT_WEBHOOK_SECRET)
    else:
        print("[AgentFlow] TELEGRAM_BOT_TOKEN not set — skipping webhook setup")