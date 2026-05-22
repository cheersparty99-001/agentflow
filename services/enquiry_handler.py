"""Enquiry Handler — processes customer messages and looks up policies."""

from datetime import datetime, date
from services.supabase_client import get_supabase, safe_multi
import config as cfg

# Demo policies for DEMO_MODE fallback
DEMO_POLICIES = [
    {"id": "d-p1", "customer_name": "Ahmad Razif", "phone": "60123456789", "car_plate": "WXY 1234",
     "expiry_date": str(date.today().replace(day=min(28, date.today().day)) if False else (date.today()).isoformat()),
     "ncd": "25%", "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-001",
     "insurer": "Etiqa", "sum_insured": 85000, "premium": 1850},
    {"id": "d-p2", "customer_name": "Tan Wei Ming", "phone": "60198765432", "car_plate": "JHB 5678",
     "expiry_date": str(date.today().replace(day=min(28, date.today().day)) if False else (date.today()).isoformat()),
     "ncd": "38%", "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-002",
     "insurer": "Allianz", "sum_insured": 120000, "premium": 2200},
    {"id": "d-p3", "customer_name": "Priya Nair", "phone": "60112223334", "car_plate": "PEN 9012",
     "expiry_date": str(date.today().replace(day=min(28, date.today().day)) if False else (date.today()).isoformat()),
     "ncd": "55%", "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-001",
     "insurer": "Great Eastern", "sum_insured": 500000, "premium": 3600},
    {"id": "d-p5", "customer_name": "Nurul Ain", "phone": "60134445556", "car_plate": "SGR 7890",
     "expiry_date": str(date.today().replace(day=min(28, date.today().day)) if False else (date.today()).isoformat()),
     "ncd": "25%", "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-001",
     "insurer": "AIA", "sum_insured": 200000, "premium": 350},
]

# Set expiry dates relative to today for demo
from datetime import timedelta
DEMO_POLICIES[0]["expiry_date"] = (date.today() + timedelta(days=30)).isoformat()
DEMO_POLICIES[1]["expiry_date"] = (date.today() + timedelta(days=14)).isoformat()
DEMO_POLICIES[2]["expiry_date"] = (date.today() + timedelta(days=7)).isoformat()
DEMO_POLICIES[3]["expiry_date"] = (date.today() + timedelta(days=100)).isoformat()


# ── Message parser ──────────────────────────────────────────────

def parse_message(text: str) -> dict:
    """
    Parse incoming customer message.
    Returns { action: "help" | "link_phone" | "lookup_phone" | "lookup_policy", value: str }
    """
    text = text.strip()

    # Help commands
    if text.lower() in ("help", "h", "start", "帮助", "指令", "菜单", "menu"):
        return {"action": "help", "value": ""}

    # Policy number pattern: POL-xxx, MTR-xxx, etc.
    if "-" in text and any(c.isdigit() for c in text):
        return {"action": "lookup_policy", "value": text}

    # Treat as phone number
    digits = "".join(c for c in text if c.isdigit())
    if len(digits) >= 8:
        return {"action": "lookup_phone", "value": digits}

    return {"action": "unknown", "value": text}


# ── Policy lookup ───────────────────────────────────────────────

def _fmt_policy(p: dict) -> str:
    """Format a single policy into a readable message block."""
    ins_type = p.get("insurance_type", "motor")
    type_labels = {
        "motor": "Motor Insurance",
        "medical": "Medical Insurance",
        "fire": "Fire Insurance",
        "travel": "Travel Insurance",
    }
    label = type_labels.get(ins_type, ins_type.capitalize())

    # Vehicle detail for motor policies
    car_info = ""
    car_plate = p.get("car_plate", "")
    car_make = p.get("car_make", "")
    car_model = p.get("car_model", "")
    if car_plate:
        car_info = f" ({car_plate})"
        if car_make and car_model:
            car_info = f" ({car_make} {car_model}, {car_plate})"

    # Expiry
    expiry = p.get("expiry_date", "")
    days_left = 999
    try:
        exp_date = datetime.strptime(expiry[:10], "%Y-%m-%d").date() if expiry else date.today()
        days_left = (exp_date - date.today()).days
    except Exception:
        pass

    if days_left < 0:
        expiry_line = f"Expired on: {expiry}"
    elif days_left == 0:
        expiry_line = f"Expires: Today!"
    else:
        expiry_line = f"Expires: {expiry} ({days_left} days left)"

    lines = [
        f"📋 <b>{p.get('customer_name', 'Customer')}</b>",
        f"• {label}{car_info}",
        f"• Policy: {p.get('policy_number', 'N/A')}",
        f"• Insurer: {p.get('insurer', 'N/A')}",
        f"• {expiry_line}",
        f"• Status: {p.get('status', 'N/A')}",
    ]
    return "\n".join(lines)


def lookup_by_phone(phone: str) -> list:
    """Find policies matching a phone number. Returns list of policy dicts."""
    try:
        sb = get_supabase()
        policies = safe_multi(
            lambda: sb.table("policies").select("*").eq("phone", phone),
            default=[],
        )
    except Exception:
        policies = []
    if not policies and cfg.DEMO_MODE:
        # Search demo policies
        policies = [p for p in DEMO_POLICIES if str(p.get("phone", "")) == phone]
    return policies


def lookup_by_policy_number(policy_number: str) -> list:
    """Find policies matching a policy number. Returns list of policy dicts."""
    try:
        sb = get_supabase()
        policies = safe_multi(
            lambda: sb.table("policies").select("*").eq("policy_number", policy_number),
            default=[],
        )
    except Exception:
        policies = []
    if not policies and cfg.DEMO_MODE:
        policies = [p for p in DEMO_POLICIES if p.get("policy_number", "").upper() == policy_number.upper()]
    return policies


# ── Link chat_id to phone ───────────────────────────────────────

def link_chat_to_phone(phone: str, chat_id: int, customer_name: str = "") -> bool:
    """Save chat_id + phone mapping so reminders can be sent."""
    from services.supabase_client import safe_insert
    safe_insert("customer_bot_links", {
        "phone": phone,
        "telegram_chat_id": chat_id,
        "customer_name": customer_name,
    })
    return True


def get_chat_id_by_phone(phone: str):
    """Look up a chat_id from a linked phone number."""
    sb = get_supabase()
    links = safe_multi(
        lambda: sb.table("customer_bot_links").select("*").eq("phone", phone),
        default=[],
    )
    if links:
        return links[0].get("telegram_chat_id")
    return None


# ── Help text ───────────────────────────────────────────────────

HELP_TEXT = """<b>🤖 AgentFlow Bot</b>

Welcome! I help you check your insurance policies.

<b>Send me:</b>
• Your <b>phone number</b> (e.g. 0123456789) — to see all your policies
• Your <b>policy number</b> (e.g. POL-001 or MTR-2026-001) — to check a specific policy
• <b>"help"</b> — to see this menu again

Example: <code>0123456789</code>
Or: <code>MTR-2026-001</code>

<i>Your first enquiry will link your chat to your phone number for future renewal reminders.</i>"""


def handle_enquiry(text: str, chat_id: int) -> str:
    """
    Main entry point. Parses a message and returns a reply string.
    Uses en/zh where appropriate.
    """
    parsed = parse_message(text)
    action = parsed["action"]
    value = parsed["value"]

    if action == "help":
        return HELP_TEXT

    if action == "unknown":
        return ("I didn't understand that. Send your phone number, policy number, or "
                "\"help\" to see options.\n\n"
                "我不明白。请发送您的手机号码、保单号码，或发送 \"help\" 查看选项。")

    if action == "lookup_policy":
        # Try exact match first
        policies = lookup_by_policy_number(value)
        if not policies:
            return f"No policy found for <code>{value}</code>.\n\nCheck the number and try again, or send your phone number to see all policies."

        # Link this chat to the policyholder's phone
        first = policies[0]
        if first.get("phone"):
            link_chat_to_phone(first["phone"], chat_id, first.get("customer_name", ""))

        results = "\n\n".join(_fmt_policy(p) for p in policies)
        return f"<b>📋 Policy Found</b>\n\n{results}"

    if action == "lookup_phone":
        policies = lookup_by_phone(value)
        if not policies:
            return (f"No policies found for phone <code>{value}</code>.\n\n"
                    "Please check your number or contact your agent.")

        # Link this chat to phone
        link_chat_to_phone(value, chat_id, policies[0].get("customer_name", ""))

        results = "\n\n".join(_fmt_policy(p) for p in policies)
        customer = policies[0].get("customer_name", "")
        total = len(policies)
        header = f"<b>📋 Policies for {customer}</b> ({total} found)\n\n"
        footer = "\n\n<i>✅ You are now linked. You'll receive renewal reminders here.</i>"
        return header + results + footer

    return "Something went wrong. Please try again."