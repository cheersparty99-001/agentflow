"""Cron job endpoints — scheduled tasks for daily operations."""

from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, date, timedelta
import config as cfg
from services.renewal_reminder import run as run_renewal_check
from services.telegram_bot import send_message
from services.enquiry_handler import get_chat_id_by_phone
from services.supabase_client import safe_single, safe_multi, safe_insert

router = APIRouter()


def verify_cron(request: Request):
    """Verify Authorization header for cron endpoints."""
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {cfg.SECRET_KEY}"
    if auth != expected:
        raise HTTPException(status_code=403, detail="Invalid cron auth")


@router.get("/cron/daily-renewal-check")
async def daily_renewal_check(request: Request):
    """
    Daily renewal reminder check. Called by Railway Cron.
    Scans policies expiring in 30/14/7 days and sends Telegram reminders
    to linked customers.
    Authorization: Bearer <SECRET_KEY>
    """
    verify_cron(request)

    account_id = "00000000-0000-0000-0000-000000000001"  # demo account
    today = date.today()
    reminder_days = [30, 14, 7]

    scanned = 0
    sent = 0
    skipped = 0
    errors = []
    logs = []

    if cfg.DEMO_MODE:
        print(f"[Cron] DEMO MODE — daily renewal check")

    # Get all active policies for this account
    sb = None
    if not cfg.DEMO_MODE:
        from services.supabase_client import get_supabase
        sb = get_supabase()

    for days in reminder_days:
        threshold_date = today + timedelta(days=days)

        policies = []
        if sb:
            policies = safe_multi(
                lambda: sb.table("policies")
                    .select("*")
                    .eq("account_id", account_id)
                    .eq("status", "Active")
                    .eq("expiry_date", threshold_date.isoformat()),
                default=[],
            )
        elif cfg.DEMO_MODE:
            # DEMO_MODE — inline demo policies handled in fallback below
            policies = []

        if not policies and cfg.DEMO_MODE:
            # Generate demo policies matching thresholds
            policies = [
                {"id": "d-p1", "customer_name": "Ahmad Razif", "phone": "60123456789",
                 "car_plate": "WXY 1234", "expiry_date": (today + timedelta(days=30)).isoformat(),
                 "insurance_type": "motor", "status": "Active", "policy_number": "MTR-2026-001", "ncd": "25%"},
                {"id": "d-p2", "customer_name": "Tan Wei Ming", "phone": "60198765432",
                 "car_plate": "JHB 5678", "expiry_date": (today + timedelta(days=14)).isoformat(),
                 "insurance_type": "motor", "status": "Active", "policy_number": "MTR-2026-002", "ncd": "38%"},
                {"id": "d-p5", "customer_name": "Nurul Ain", "phone": "60134445556",
                 "car_plate": "SGR 7890", "expiry_date": (today + timedelta(days=7)).isoformat(),
                 "insurance_type": "travel", "status": "Active", "policy_number": "TRV-2026-001", "ncd": "25%"},
            ]
            # Filter to match this threshold
            policies = [p for p in policies if p["expiry_date"] == threshold_date.isoformat()]

        for policy in policies:
            scanned += 1
            phone = policy.get("phone", "")
            customer_name = policy.get("customer_name", "Customer")
            car_plate = policy.get("car_plate", "")
            expiry = policy.get("expiry_date", "")
            ins_type = policy.get("insurance_type", "motor")
            policy_number = policy.get("policy_number", "")

            # Build reminder message
            type_labels = {
                "motor": "Motor Insurance",
                "medical": "Medical Insurance",
                "fire": "Fire Insurance",
                "travel": "Travel Insurance",
            }
            label = type_labels.get(ins_type, ins_type.capitalize())

            urgency = "⚠️" if days <= 7 else "📋"
            if days == 30:
                urgency = "📋"
            elif days == 7:
                urgency = "🔴"

            message = (
                f"{urgency} <b>Renewal Reminder</b>\n\n"
                f"Hi <b>{customer_name}</b>,\n"
                f"Your {label} ({car_plate}) will expire in <b>{days} days</b> on {expiry}.\n\n"
                f"Policy: {policy_number}\n"
            )
            if days <= 7:
                message += "\n<b>Please renew immediately to avoid lapse in coverage.</b>"
            elif days <= 14:
                message += "\nYour renewal options are ready. Contact us to confirm."
            else:
                message += "\nWe will prepare your renewal quotation soon. Reply if any details have changed."

            message += "\n\n<i>Reply with \"help\" to see available commands.</i>"

            # Look up chat_id by phone
            chat_id = get_chat_id_by_phone(phone)

            if chat_id:
                if cfg.DEMO_MODE:
                    print(f"[Cron] DEMO — Would send Telegram to {customer_name} (chat:{chat_id})")
                    sent += 1
                    logs.append({
                        "module": "telegram_cron",
                        "action": f"send_{days}d_reminder",
                        "policy_id": policy.get("id", ""),
                        "status": "demo",
                        "message": f"DEMO — Would send {days}d reminder to {customer_name} at chat {chat_id}",
                        "created_at": datetime.utcnow().isoformat(),
                    })
                else:
                    success = send_message(chat_id, message)
                    if success:
                        sent += 1
                        logs.append({
                            "module": "telegram_cron",
                            "action": f"send_{days}d_reminder",
                            "status": "success",
                            "message": f"Sent {days}d reminder to {customer_name} at chat {chat_id}",
                            "created_at": datetime.utcnow().isoformat(),
                        })
                    else:
                        errors.append(f"Failed to send to {customer_name} (chat:{chat_id})")
                        skipped += 1
            else:
                skipped += 1
                print(f"[Cron] No chat linked for {customer_name} ({phone})")
                logs.append({
                    "module": "telegram_cron",
                    "action": "skip_unlinked",
                    "policy_id": policy.get("id", ""),
                    "status": "skipped",
                    "message": f"No chat linked for {customer_name} ({phone})",
                    "created_at": datetime.utcnow().isoformat(),
                })

    # Log results
    if not cfg.DEMO_MODE:
        for log in logs:
            safe_insert("agent_logs", log)

    result = {
        "status": "ok",
        "scanned": scanned,
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }
    print(f"[Cron] Daily renewal check complete: {result}")
    return result