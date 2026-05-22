"""Birthday Greeting Agent — sends automated birthday wishes to customers."""

import config as cfg
from datetime import datetime, date, timedelta
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_insert

BIRTHDAY_TEMPLATES = {
    "en": "🎂 Happy Birthday, {customer_name}! 🎉\n\nWishing you a wonderful day filled with joy and happiness. From all of us at {agency_name}.\n\nAs a token of our appreciation, here's a special birthday discount on your next insurance renewal — just reply to this message to claim it!",
    "bm": "🎂 Selamat Hari Lahir, {customer_name}! 🎉\n\nSemoga hari yang indah ini dipenuhi dengan kegembiraan dan kebahagiaan. Daripada kami semua di {agency_name}.\n\nSebagai tanda penghargaan, berikut adalah diskaun hari jadi khas untuk pembaharuan insurans anda — balas mesej ini untuk menuntutnya!",
    "zh": "🎂 {customer_name}，生日快乐！🎉\n\n祝你度过充满欢乐和幸福的美好一天。来自 {agency_name} 全体成员的祝福。\n\n为表心意，我们为您准备了生日专属续保折扣——回复此消息即可领取！",
}

# Demo customers with birthdays for DEMO_MODE
DEMO_BIRTHDAY_CUSTOMERS = []  # initialized in run() if needed


def run(account_id: str, demo_mode: bool = True, log_store: list = None) -> dict:
    """Scan customers and send birthday greetings. Returns stats."""
    global DEMO_BIRTHDAY_CUSTOMERS
    DEMO_BIRTHDAY_CUSTOMERS = []  # reset each run
    sb = get_supabase()
    today = date.today()
    scanned = 0
    sent = 0
    skipped = 0

    account = safe_single(
        lambda: sb.table("accounts").select("agency_name, language").eq("id", account_id).single(),
        default={"agency_name": "Demo Insurance Agency", "language": "en"},
    )
    if not account:
        return {"error": "Account not found", "scanned": 0, "sent": 0, "skipped": 0}

    agency_name = account.get("agency_name", "Agency")
    language = account.get("language", "en")

    # Determine which language templates to use
    lang_key = language if language in ("en", "bm", "zh") else "en"

    # Fetch customers with birthdays
    if demo_mode:
        if not DEMO_BIRTHDAY_CUSTOMERS:
            base = today
            DEMO_BIRTHDAY_CUSTOMERS.extend([
                {"id": "b-demo-1", "customer_name": "Ahmad Razif", "phone": "60123456789",
                 "birthday": base.isoformat(), "last_greeted_year": None},
                {"id": "b-demo-2", "customer_name": "Siti Fatimah", "phone": "60167778889",
                 "birthday": (base + timedelta(days=1)).isoformat(), "last_greeted_year": None},
                {"id": "b-demo-3", "customer_name": "Raj Kumar", "phone": "60156667770",
                 "birthday": (base - timedelta(days=1)).isoformat(), "last_greeted_year": None},
            ])
        birthday_people = DEMO_BIRTHDAY_CUSTOMERS
    else:
        # In production, query policies table for customers with birthdays
        # We assume policies table stores ic_number which can derive birth date,
        # or we add a birthday field to customers/policies in the future
        birthday_people = safe_multi(
            lambda: sb.table("policies").select("*").eq("account_id", account_id).neq("ic_number", None),
            default=[],
        )
        # Filter by today's month and day from ic_number (YYMMDD format)
        today_md = (today.month, today.day)
        birthday_people = [
            p for p in birthday_people
            if p.get("ic_number") and len(p["ic_number"]) >= 8
            and _extract_birthday(p["ic_number"]) == today_md
        ]

    for customer in birthday_people:
        scanned += 1
        name = customer.get("customer_name", "Valued Customer")
        phone = customer.get("phone", "")
        customer_id = customer.get("id", "")

        # Skip if already greeted this year
        last_year = customer.get("last_greeted_year")
        if last_year == today.year:
            skipped += 1
            continue

        message = BIRTHDAY_TEMPLATES[lang_key].format(
            customer_name=name,
            agency_name=agency_name,
        )

        if demo_mode:
            log_msg = f"DEMO -- Would send birthday greeting to {phone}: {message[:60]}..."
            if log_store is not None:
                log_store.append({
                    "module": "birthday_greeting",
                    "action": "send_greeting",
                    "policy_id": customer_id,
                    "customer": name,
                    "status": "demo",
                    "message": log_msg,
                    "created_at": datetime.utcnow().isoformat(),
                })
            sent += 1
        else:
            from services import whatsapp
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
                # Mark as greeted this year
                if not demo_mode:
                    safe_insert("agent_logs", {
                        "account_id": account_id,
                        "module": "birthday_greeting",
                        "action": "send_greeting",
                        "policy_id": customer_id,
                        "customer": name,
                        "status": "success",
                        "message": f"Birthday greeting sent to {phone} ({name})",
                    })
                sent += 1
            else:
                if not demo_mode:
                    safe_insert("agent_logs", {
                        "account_id": account_id,
                        "module": "birthday_greeting",
                        "action": "send_greeting",
                        "policy_id": customer_id,
                        "customer": name,
                        "status": "failed",
                        "message": f"Failed to send birthday greeting to {phone}",
                    })
                skipped += 1

    return {"scanned": scanned, "sent": sent, "skipped": skipped}


def _extract_birthday(ic_number: str) -> tuple:
    """Extract (month, day) from Malaysian IC number (YYMMDD-XXXX-XXXX)."""
    digits = "".join(c for c in ic_number if c.isdigit())
    if len(digits) >= 12:
        # YYMMDD
        month = int(digits[2:4])
        day = int(digits[4:6])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (month, day)
    return (0, 0)
