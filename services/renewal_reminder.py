"""Renewal Reminder Agent - checks policies and sends WhatsApp reminders."""

import config as cfg
from datetime import datetime, date, timedelta
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_insert, safe_update
from services import whatsapp

TEMPLATES = {
    "30": {
        "en": "Hi {customer_name}, this is {agency_name}. Your motor insurance for {car_plate} will expire on {expiry_date}. We will prepare your renewal quotation soon. Reply if any details have changed.",
        "bm": "Hi {customer_name}, ini peringatan dari {agency_name}. Insurans motor {car_plate} anda akan tamat pada {expiry_date}. Kami akan sediakan sebutan harga pembaharuan tidak lama lagi.",
    },
    "14": {
        "en": "Hi {customer_name}, your motor insurance for {car_plate} expires in 14 days on {expiry_date}. Your renewal options are ready. Please contact us to confirm.",
        "bm": "Hi {customer_name}, insurans motor {car_plate} anda tamat dalam 14 hari pada {expiry_date}. Sila hubungi kami untuk mengesahkan pembaharuan.",
    },
    "7": {
        "en": "Hi {customer_name}, URGENT — your motor insurance for {car_plate} expires in 7 days on {expiry_date}. Please renew immediately to avoid lapse in coverage.",
        "bm": "Hi {customer_name}, SEGERA — insurans motor {car_plate} anda tamat dalam 7 hari pada {expiry_date}. Sila perbaharui segera.",
    },
}


def run(account_id: str, demo_mode: bool = True, log_store: list = None) -> dict:
    sb = get_supabase()

    # Load account with safe_single
    account = safe_single(
        lambda: sb.table("accounts").select("*").eq("id", account_id).single(),
        default={
            "agency_name": "Demo Insurance Agency",
            "language": "en",
            "reminder_days": [30, 14, 7],
        },
    )
    if not account:
        return {"error": "Account not found", "scanned": 0, "sent": 0, "skipped": 0}

    agency_name = account.get("agency_name", "Agency")
    language = account.get("language", "en")
    reminder_days = account.get("reminder_days", [30, 14, 7])

    today = date.today()
    scanned = 0
    sent = 0
    skipped = 0

    # In demo mode, use hardcoded policies if Supabase returns none
    demo_policies = None
    if demo_mode:
        demo_policies = [
            {"id": "demo-1", "customer_name": "Ahmad Razif", "phone": "60123456789", "car_plate": "WXY 1234", "expiry_date": (today + timedelta(days=30)).isoformat(), "ncd": "25%", "reminder_30_sent": None, "reminder_14_sent": None, "reminder_7_sent": None},
            {"id": "demo-2", "customer_name": "Tan Wei Ming", "phone": "60198765432", "car_plate": "JHB 5678", "expiry_date": (today + timedelta(days=14)).isoformat(), "ncd": "38%", "reminder_30_sent": None, "reminder_14_sent": None, "reminder_7_sent": None},
            {"id": "demo-3", "customer_name": "Priya Nair", "phone": "60112223334", "car_plate": "PEN 9012", "expiry_date": (today + timedelta(days=7)).isoformat(), "ncd": "55%", "reminder_30_sent": None, "reminder_14_sent": None, "reminder_7_sent": None},
            {"id": "demo-4", "customer_name": "Lim Chee Keong", "phone": "60167778889", "car_plate": "KLM 3456", "expiry_date": (today + timedelta(days=45)).isoformat(), "ncd": "0%", "reminder_30_sent": None, "reminder_14_sent": None, "reminder_7_sent": None},
            {"id": "demo-5", "customer_name": "Nurul Ain", "phone": "60134445556", "car_plate": "SGR 7890", "expiry_date": (today + timedelta(days=7)).isoformat(), "ncd": "25%", "reminder_30_sent": None, "reminder_14_sent": None, "reminder_7_sent": None},
        ]

    for days in reminder_days:
        threshold_date = today + timedelta(days=days)

        policies = safe_multi(
            lambda: sb.table("policies")
                .select("*")
                .eq("account_id", account_id)
                .eq("status", "Active")
                .eq("expiry_date", threshold_date.isoformat()),
            default=[],
        )

        # Fallback to demo policies if real query returned empty and we have demo data
        if not policies and demo_policies:
            policies = [p for p in demo_policies if p["expiry_date"] == threshold_date.isoformat()]

        for policy in policies:
            scanned += 1
            policy_id = policy["id"]
            customer_name = policy["customer_name"]
            phone = policy["phone"]
            car_plate = policy["car_plate"]
            expiry_date = policy["expiry_date"]
            ncd = policy.get("ncd", "")

            sent_col = f"reminder_{days}_sent"
            if policy.get(sent_col):
                skipped += 1
                continue

            template = TEMPLATES[str(days)]
            lang_key = "en" if language == "both" else (language if language in ("en", "bm") else "en")
            message = template[lang_key].format(
                customer_name=customer_name,
                agency_name=agency_name,
                car_plate=car_plate,
                expiry_date=expiry_date,
                ncd=ncd,
            )

            if demo_mode:
                log_message = f"DEMO -- Would send to {phone}: {message[:60]}..."
                if log_store is not None:
                    log_store.append({
                        "module": "renewal_reminder",
                        "action": "send_reminder",
                        "policy_id": policy_id,
                        "status": "demo",
                        "message": log_message,
                        "created_at": datetime.utcnow().isoformat(),
                    })
                sent += 1
            else:
                success = whatsapp.send_message(
                    {
                        "twilio_sid": account.get("twilio_sid"),
                        "twilio_token": account.get("twilio_token"),
                        "whatsapp_from": account.get("whatsapp_from"),
                    },
                    phone,
                    message,
                )
                if success:
                    safe_update("policies", {sent_col: today.isoformat()}, "id", policy_id)
                    safe_insert("agent_logs", {
                        "account_id": account_id,
                        "module": "renewal_reminder",
                        "action": "send_reminder",
                        "policy_id": policy_id,
                        "status": "success",
                        "message": f"Sent to {phone}",
                    })
                    sent += 1
                else:
                    safe_insert("agent_logs", {
                        "account_id": account_id,
                        "module": "renewal_reminder",
                        "action": "send_reminder",
                        "policy_id": policy_id,
                        "status": "failed",
                        "message": f"Failed to send to {phone}",
                    })
                    skipped += 1

    return {"scanned": scanned, "sent": sent, "skipped": skipped}