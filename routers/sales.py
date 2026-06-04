import os
import uuid
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from routers.auth import get_current_user
import config as cfg
from data import leads as data_leads, profiles as data_profiles, usage as data_usage

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))

# ── Demo Data ──────────────────────────────────────────────────────────────────
LEAD_STATUSES = ["cold", "contacted", "replied", "interested", "closed_lost", "closed_won"]
BUSINESSES = ["Boleh AI", "Wise Solutions"]

# ── Normalization helpers ───────────────────────────────────────────────────────

# Map business_id -> business name (also used in templates)
_BUSINESS_NAME_MAP = {
    "b1000000-0000-0000-0000-000000000001": "Boleh AI",
    "b1000000-0000-0000-0000-000000000002": "Wise Solutions",
}

def _normalize_lead(ld: dict) -> dict:
    """Convert DB lead fields to template-compatible format."""
    if ld is None:
        return None
    ld["name"] = ld.get("company_name") or ld.get("name") or ""
    ld["contact"] = ld.get("contact_name") or ld.get("contact") or ""
    ld["score"] = ld.get("ai_score") or ld.get("score") or 0
    ld["location"] = ld.get("city") or ld.get("location") or ""
    # Resolve business name
    biz_id = ld.get("business_id", "")
    biz_name = _BUSINESS_NAME_MAP.get(biz_id, "")
    if not biz_name and ld.get("name"):
        # Possible the lead was stored with a 'business' field directly
        biz_name = ld.get("business", "")
    ld["business"] = biz_name
    return ld


def _normalize_activities(acts: list) -> list:
    """Convert DB activity fields to template-compatible format."""
    result = []
    for a in (acts or []):
        result.append({
            "lead_id": a.get("lead_id", ""),
            "type": a.get("activity_type") or a.get("type") or "note",
            "summary": a.get("description") or a.get("summary") or "",
            "detail": a.get("detail") or "",
            "created_at": a.get("created_at", ""),
        })
    return result


def _make_create_lead_data(name: str, contact: str, phone: str, email: str,
                            industry: str, location: str, business: str,
                            source: str, notes: str, score: int = 7,
                            status: str = "cold") -> dict:
    """Build a dict suitable for data_leads.create_lead()."""
    biz_id = None
    for bid, bname in _BUSINESS_NAME_MAP.items():
        if bname == business:
            biz_id = bid
            break
    return {
        "company_name": name,
        "contact_name": contact,
        "phone": phone,
        "email": email,
        "industry": industry,
        "city": location,
        "location": location,
        "business_id": biz_id or "",
        "source": source,
        "notes": notes,
        "ai_score": score,
        "score": score,
        "status": status,
    }


# ── Utility ────────────────────────────────────────────────────────────────────

async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


# ── DB Seeder ─────────────────────────────────────────────────────────────────

def seed_db_with_demo_data():
    """Seed Supabase with demo data if empty."""
    existing = data_leads.get_all_leads()
    if existing:
        print(f"[Sales] DB already has {len(existing)} leads, skipping seed")
        return

    seeds = [
        {"company_name": "Poblano KL", "industry": "food_beverage", "business_id": "b1000000-0000-0000-0000-000000000001", "ai_score": 7, "status": "cold", "contact_name": "", "phone": "", "email": "", "location": "Kuala Lumpur", "notes": "Mexican restaurant in KL"},
        {"company_name": "KB Insurance Agency", "industry": "insurance", "business_id": "b1000000-0000-0000-0000-000000000001", "ai_score": 9, "status": "interested", "contact_name": "Khalid Bashir", "phone": "+60 13-456 7890", "email": "khalid@kbinsurance.my", "location": "Penang", "notes": "Interested in AI for claims"},
        {"company_name": "Beauty Palace Ampang", "industry": "beauty", "business_id": "b1000000-0000-0000-0000-000000000001", "ai_score": 8, "status": "replied", "contact_name": "Mei Ling Wong", "phone": "+60 16-789 0123", "email": "", "location": "Ampang", "notes": "Demo scheduled"},
        {"company_name": "Shah Alam Wholesale", "industry": "wholesale", "business_id": "b1000000-0000-0000-0000-000000000001", "ai_score": 9, "status": "cold", "contact_name": "Ravi Chandran", "phone": "+60 17-890 1234", "email": "", "location": "Shah Alam", "notes": "Large distributor"},
        {"company_name": "PrestoPay Malaysia", "industry": "fintech", "business_id": "b2000000-0000-0000-0000-000000000002", "ai_score": 9, "status": "interested", "contact_name": "Tan Li Wei", "phone": "+60 11-2345 6789", "email": "", "location": "Kuala Lumpur", "notes": "Series A startup"},
        {"company_name": "MediTech Solutions", "industry": "healthcare", "business_id": "b2000000-0000-0000-0000-000000000002", "ai_score": 8, "status": "replied", "contact_name": "Dr. Sarah Lim", "phone": "+60 18-901 2345", "email": "", "location": "Selangor", "notes": "Hospital chain"},
        {"company_name": "EduSmart Learning", "industry": "education", "business_id": "b2000000-0000-0000-0000-000000000002", "ai_score": 7, "status": "contacted", "contact_name": "Prof. Amir Hassan", "phone": "+60 19-012 3456", "email": "", "location": "Cyberjaya", "notes": "EdTech platform"},
        {"company_name": "ShopEase Malaysia", "industry": "ecommerce", "business_id": "b2000000-0000-0000-0000-000000000002", "ai_score": 8, "status": "replied", "contact_name": "Nadia Osman", "phone": "+60 10-1234 5678", "email": "", "location": "Petaling Jaya", "notes": "Wants AI recommendations"},
        {"company_name": "LogiSwift MY", "industry": "logistics", "business_id": "b2000000-0000-0000-0000-000000000002", "ai_score": 9, "status": "interested", "contact_name": "Ganesh Krishnan", "phone": "+60 15-678 9012", "email": "", "location": "Port Klang", "notes": "Fleet of 200 vehicles"},
        {"company_name": "Marvelous Retail", "industry": "retail", "business_id": "b1000000-0000-0000-0000-000000000001", "ai_score": 7, "status": "cold", "contact_name": "Siti Nurhaliza", "phone": "+60 14-567 8901", "email": "", "location": "Johor Bahru", "notes": "Chain of stores"},
    ]

    for s in seeds:
        lead = data_leads.create_lead(s)
        data_leads.create_activity(lead["id"], "note", f"Seed lead: {s['company_name']}", {})

    print(f"[Sales] Seeded {len(seeds)} demo leads to Supabase")


# ── Helper functions for template rendering ────────────────────────────────────

def _render(request, template_name, **extra):
    user = request.state.user if hasattr(request.state, "user") else {}
    tmpl = env.get_template(template_name)
    html = tmpl.render(
        demo_mode=cfg.DEMO_MODE,
        current_path=request.url.path,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
        **extra,
    )
    return HTMLResponse(html)


# ── Shared email send helper ─────────────────────────────────────────────────────

def _send_single_email(account_id: str, lead_id: str, to_email: str, subject: str, body: str) -> dict:
    """Send one email via the account's Gmail OAuth connection.
    Returns dict with keys: ok (bool), message (str, on success), error (str, on failure).
    """
    from services.sales.gmail_client import GmailClient

    gmail = GmailClient(account_id=account_id)
    if not gmail.is_authenticated:
        gmail.authenticate()
    if not gmail.is_authenticated:
        return {"ok": False, "error": "Email not connected — connect your email in Settings first"}

    result = gmail.send_message(to_email=to_email, subject=subject, body=body)
    if result.get("status") == "sent":
        # Record usage for monthly counting
        try:
            from services.supabase_client import get_supabase
            get_supabase().table("sales_messages").insert({
                "id": str(uuid.uuid4()),
                "account_id": account_id,
                "lead_id": lead_id,
                "direction": "outbound",
                "channel": "email",
                "subject": subject,
                "content": body,
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            print(f"[Sales/SendEmail] Usage recording skipped: {e}")
        return {"ok": True, "message": f"Email sent to {to_email}"}
    else:
        error = result.get("error", result.get("reason", "Send failed"))
        return {"ok": False, "error": error}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/sales/dashboard", response_class=HTMLResponse)
async def sales_dashboard(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Use data layer for stats
    leads = data_leads.get_all_leads()
    activities = data_leads.list_activities(limit=50)
    biz_stats = data_leads.get_biz_stats()

    # Normalize leads for template
    normalized = [_normalize_lead(ld) for ld in leads]

    # Recent activity feed (last 15)
    acts_normalized = _normalize_activities(activities[:15])

    # Escalation alerts: leads needing attention (interested or with replies)
    escalations = [l for l in normalized if l["status"] in ("interested", "replied")]

    return _render(request, "sales/dashboard.html",
                   biz_stats=biz_stats,
                   total_leads=len(normalized),
                   recent_activities=acts_normalized,
                   escalations=escalations,
                   leads_status_counts={s: len([l for l in normalized if l["status"] == s]) for s in LEAD_STATUSES},
                   )


@router.get("/sales/leads", response_class=HTMLResponse)
async def sales_leads(
    request: Request,
    status: str = "",
    business: str = "",
    industry: str = "",
    search: str = "",
    page: int = 1,
    format: str = "",
):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    # Return JSON if format=json
    if format == "json":
        leads_json, _ = data_leads.list_leads(status=status, page=1, per_page=1000)
        return JSONResponse({"leads": leads_json})

    # Use data layer with filtering and pagination
    # data_leads.list_leads uses different field names for filtering
    page_leads_db, total = data_leads.list_leads(status=status, page=page, per_page=10)
    
    # Normalize for template
    page_leads = [_normalize_lead(ld) for ld in page_leads_db]
    
    per_page = 10
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    # Get all leads for industry filter options
    all_leads = data_leads.get_all_leads()
    all_industries = sorted(set(
        ld.get("industry", "") or ld.get("industry", "")
        for ld in all_leads if ld.get("industry")
    ))

    return _render(request, "sales/leads.html",
                   leads=page_leads,
                   page=page,
                   total_pages=total_pages,
                   total=total,
                   all_statuses=LEAD_STATUSES,
                   all_businesses=BUSINESSES,
                   all_industries=all_industries,
                   filters={"status": status, "business": business, "industry": industry, "search": search},
                   )


@router.post("/sales/leads/add")
async def add_lead(
    request: Request,
    name: str = Form(...),
    contact: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    industry: str = Form(""),
    location: str = Form(""),
    business: str = Form("Boleh AI"),
    source: str = Form("manual"),
    notes: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})
    
    lead_data = _make_create_lead_data(
        name=name, contact=contact, phone=phone, email=email,
        industry=industry, location=location, business=business,
        source=source, notes=notes,
    )
    new_lead = data_leads.create_lead(lead_data)
    
    # Log activity
    data_leads.create_activity(
        new_lead["id"], "note",
        f"Lead added manually by {user.get('email', 'user')}",
        {"added_by": user.get("email", "user")},
    )
    
    return JSONResponse({"ok": True, "id": new_lead["id"]})


@router.get("/sales/leads/{lead_id}/generate-email")
async def generate_email(request: Request, lead_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})
    
    lead = data_leads.get_lead(lead_id)
    if not lead:
        return JSONResponse({"ok": False, "error": "Lead not found"})
    
    # Normalize lead for template field access
    lead = _normalize_lead(lead)
    
    business = lead.get("business", "Boleh AI")
    industry = lead.get("industry", "").replace("_", " ")
    name = lead.get("name", "your company")
    contact = lead.get("contact", "there")
    location = lead.get("location", "Malaysia")
    
    subjects = {
        "food_beverage": f"Helping {name} save time with AI",
        "retail": f"How {name} can automate customer follow-ups",
        "insurance": f"Streamlining claims for {name}",
        "healthcare": f"AI patient scheduling for {name}",
        "technology": f"Scaling {name} with AI agents",
        "finance": f"Financial automation for {name}",
        "logistics": f"Route optimization for {name}",
        "education": f"EdTech solutions for {name}",
        "wholesale": f"AI for {name}\u2019s distribution",
        "ecommerce": f"Growing {name} with AI recommendations",
        "hospitality": f"Booking automation for {name}",
        "professional_services": f"AI tools for {name}",
    }
    subject = subjects.get(industry.replace(" ", "_"), f"Hello from {business}")
    
    body = f"Hi {contact},\n\nI noticed {name} in {location} is doing well in the {industry} space. Many {industry} businesses we work with spend hours on repetitive tasks like follow-ups, lead qualification, and customer outreach.\n\nWe help companies like yours save 10+ hours per week by automating these with AI agents. Would you be open to a quick chat to see if this could work for {name}?\n\nBest regards,\nThe {business} Team"
    
    return JSONResponse({"ok": True, "subject": subject, "body": body})


@router.post("/sales/leads/{lead_id}/send-email")
async def send_email(
    request: Request,
    lead_id: str,
    subject: str = Form(""),
    body: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})

    lead = data_leads.get_lead(lead_id)
    if not lead:
        return JSONResponse({"ok": False, "error": "Lead not found"})

    to_email = lead.get("email", "")
    if not to_email:
        return JSONResponse({"ok": False, "error": "Lead has no email address"})

    if not subject or not body:
        return JSONResponse({"ok": False, "error": "Subject and body are required"})

    account_id = user.get("account_id", "")
    result = _send_single_email(account_id, lead_id, to_email, subject, body)

    if not result.get("ok"):
        # Log failed attempt
        data_leads.create_activity(
            lead_id, "email",
            f"Email FAILED: {result.get('error', 'Unknown error')}",
            {"detail": f"To: {to_email}\nSubject: {subject}\nError: {result.get('error', '')}"},
        )
        return JSONResponse({"ok": False, "error": result.get("error", "Send failed")})

    # Success — log activity
    data_leads.create_activity(
        lead_id, "email",
        f"Email sent to {to_email}",
        {"subject": subject, "body_preview": body[:200]},
    )

    # Update status to contacted if cold
    if lead.get("status") == "cold":
        data_leads.update_lead_status(lead_id, "contacted")
        data_leads.create_activity(
            lead_id, "note",
            "Status changed to Contacted",
            {"detail": "Auto-updated after email outreach"},
        )

    return JSONResponse({"ok": True, "message": f"Email sent to {to_email}"})


@router.post("/sales/outreach/send")
async def outreach_send(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})
    
    try:
        body = await request.json()
    except:
        return JSONResponse({"ok": False, "error": "Invalid JSON"})
    
    lead_ids = body.get("lead_ids", [])
    business = body.get("business", "Boleh AI")
    
    if not lead_ids:
        return JSONResponse({"ok": False, "error": "No leads selected"})
    
    sent = 0
    for lid in lead_ids:
        lead = data_leads.get_lead(lid)
        if lead and lead.get("status") == "cold":
            data_leads.update_lead_status(lid, "contacted")
            data_leads.create_activity(
                lid, "email",
                f"Outreach sent ({business})",
                {"detail": f"Auto-generated outreach message for {lead.get('company_name', lead.get('name', 'lead'))}"},
            )
            sent += 1
    
    return JSONResponse({"ok": True, "sent": sent})


@router.get("/sales/leads/{lead_id}", response_class=HTMLResponse)
async def sales_lead_detail(request: Request, lead_id: str):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    lead = data_leads.get_lead(lead_id)
    if not lead:
        return RedirectResponse(url="/sales/leads")

    lead = _normalize_lead(lead)
    acts = _normalize_activities(data_leads.list_activities(lead_id=lead_id, limit=100))

    return _render(request, "sales/lead_detail.html", lead=lead, activities=acts)


@router.post("/sales/leads/{lead_id}/status")
async def sales_lead_update_status(request: Request, lead_id: str, status: str = Form(...)):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    lead = data_leads.get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    data_leads.update_lead_status(lead_id, status)
    data_leads.create_activity(
        lead_id, "note",
        f"Status changed to {status}",
        {"detail": f"Lead status updated from previous to '{status}' by agent."},
    )
    return JSONResponse({"ok": True, "status": status})


@router.post("/sales/leads/{lead_id}/note")
async def sales_lead_add_note(request: Request, lead_id: str, summary: str = Form(...), detail: str = Form("")):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    lead = data_leads.get_lead(lead_id)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    act = data_leads.create_activity(lead_id, "note", summary, {"detail": detail})
    data_leads.update_lead(lead_id, {})
    return JSONResponse({"ok": True, "activity": _normalize_activities([act])[0]})


@router.post("/sales/leads/upload")
async def sales_leads_upload(request: Request, file: UploadFile = File(...)):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except Exception:
        text = content.decode("latin-1")

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    imported = 0
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        lead_data = _make_create_lead_data(
            name=parts[0],
            contact=parts[4] if len(parts) > 4 else "",
            phone=parts[5] if len(parts) > 5 else "",
            email=parts[6] if len(parts) > 6 else "",
            industry=parts[1] if len(parts) > 1 else "other",
            location=parts[7] if len(parts) > 7 else "",
            business=parts[2] if len(parts) > 2 else "Boleh AI",
            source="import",
            notes=parts[8] if len(parts) > 8 else "",
            score=int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 5,
        )
        data_leads.create_lead(lead_data)
        imported += 1

    return JSONResponse({"ok": True, "imported": imported})


@router.get("/sales/pipeline", response_class=HTMLResponse)
async def sales_pipeline(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    leads = [_normalize_lead(ld) for ld in data_leads.get_all_leads()]

    columns = {}
    for s in LEAD_STATUSES:
        columns[s] = [l for l in leads if l["status"] == s]

    return _render(request, "sales/pipeline.html", columns=columns, all_statuses=LEAD_STATUSES)


@router.post("/sales/outreach/trigger")
async def sales_outreach_trigger(
    request: Request,
    campaign: str = Form(""),
    channel: str = Form("whatsapp"),
    lead_id: str = Form(""),
    test_override_email: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Target specific lead or batch
    if lead_id:
        single = data_leads.get_lead(lead_id)
        targets = [_normalize_lead(single)] if single else []
    else:
        all_leads = [_normalize_lead(ld) for ld in data_leads.get_all_leads()]
        targets = [l for l in all_leads if l["status"] in ("cold", "contacted")]

    sent_count = 0
    errors = []
    for target in targets[:5]:
        # Determine email recipient
        to_email = test_override_email or target.get("email", "")

        if channel == "email" and to_email:
            # Real Gmail send (per-account or config fallback)
            from services.sales.gmail_client import GmailClient
            account_id = user.get("account_id", "")
            gmail = GmailClient(account_id=account_id)
            if not gmail.is_authenticated:
                gmail.authenticate()

            body = f"""Hi {target.get('contact', target.get('name', ''))},

I came across {target.get('name', 'your company')} and wanted to reach out.

{target.get('notes', 'We help Malaysian businesses automate with AI solutions.')}

Would you be open to a quick chat?

Best regards,
Edwin
Boleh AI"""

            result = gmail.send_message(
                to_email=to_email,
                subject=f"Quick question about {target.get('name', 'your business')}",
                body=body,
            )

            if result.get("status") == "sent":
                sent_count += 1
                detail = f"Email sent to {to_email} — ID: {result.get('id', result.get('message_id', 'unknown'))}"
            else:
                errors.append(result.get("error", "Send failed"))
                detail = f"Email FAILED to {to_email}: {result.get('error', 'Unknown error')}"
        else:
            # Demo or WhatsApp mode
            sent_count += 1
            detail = f"Sent automated {channel} message to {target.get('contact', '')} at {target.get('name', '')}."
            if test_override_email:
                detail += f" (would send to {test_override_email})"

        data_leads.create_activity(
            target["id"], "message",
            f"Outreach via {channel}" + (f" — {campaign}" if campaign else ""),
            {"detail": detail},
        )

    return JSONResponse({"ok": True, "sent": sent_count, "channel": channel, "campaign": campaign, "errors": errors})


# (replaced below with expanded version including google_maps support)


@router.post("/sales/webhook/whatsapp")
async def sales_webhook_whatsapp(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    phone = body.get("from", "") or body.get("phone", "") or "unknown"
    message = body.get("message", "") or body.get("text", "") or ""
    name = body.get("name", "Unknown")

    all_leads = [_normalize_lead(ld) for ld in data_leads.get_all_leads()]

    # Accept lead_id directly, or match by phone/name
    lead = None
    if "lead_id" in body:
        lead = next((l for l in all_leads if l["id"] == body["lead_id"]), None)
    if not lead:
        matched = [l for l in all_leads if phone in l.get("phone", "")]
        if not matched:
            matched = [l for l in all_leads if name.lower() in l["name"].lower()]
        lead = matched[0] if matched else None

    result = {"matched": 1 if lead else 0}

    if lead and message:
        # Route to reply_handler for sentiment analysis
        from services.sales.reply_handler import handle_reply
        intent_result = handle_reply(
            reply_text=message,
            from_email=lead.get("email", ""),
            from_name=lead.get("contact", ""),
            lead=lead,
            lead_id=lead["id"],
            auto_reply_enabled=True,
        )

        sentiment = intent_result.get("sentiment", "neutral")
        result["intent"] = sentiment
        result["confidence"] = intent_result.get("confidence", 0.8)
        result["auto_reply"] = intent_result.get("auto_reply", "")

        # Map sentiment to status action
        if sentiment in ("negative", "unsubscribe"):
            action = "stop"
            new_status = "closed_lost"
        elif sentiment == "positive":
            action = "escalate"
            new_status = "interested"
        else:
            action = "wait"
            new_status = lead["status"]

        result["action"] = action

        # Log activity
        data_leads.create_activity(
            lead["id"], "message",
            f"Inbound WhatsApp from {name} — Sentiment: {sentiment}",
            {"detail": f"Message: {message[:500]}\n\nAI Analysis:\nSentiment: {sentiment}\nAction: {action}\nAuto-reply: {intent_result.get('auto_reply', '(none)')[:200]}"},
        )

        # Update lead status based on sentiment
        if sentiment in ("negative", "unsubscribe"):
            data_leads.update_lead_status(lead["id"], "closed_lost")
            lead["status"] = "closed_lost"
        elif sentiment == "positive":
            data_leads.update_lead_status(lead["id"], "interested")
            lead["status"] = "interested"

        # Build escalation notification for positive intent
        if sentiment == "positive":
            notification = (
                f"Sales Alert — Action Required\n\n"
                f"Business: {lead['business']}\n"
                f"Lead: {lead['name']}\n"
                f"Status: {new_status}\n\n"
                f'Their message:\n"{message}"\n\n'
                f"Suggested next step:\n{intent_result.get('auto_reply', 'Schedule a call')}\n\n"
                f"View lead: /sales/leads/{lead['id']}"
            )
            result["notification"] = notification

    return JSONResponse(result)


@router.post("/sales/webhook/gmail")
async def sales_webhook_gmail(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    sender = body.get("from", "") or body.get("sender", "") or "unknown"
    subject = body.get("subject", "") or "(no subject)"
    snippet = body.get("snippet", "") or body.get("body", "") or ""

    all_leads = data_leads.get_all_leads()
    matched = [l for l in all_leads if sender.lower() in (l.get("email") or "").lower()]

    for lead in matched:
        data_leads.create_activity(
            lead["id"], "email",
            f"Inbound email: {subject}",
            {"detail": f"From: {sender}\nSubject: {subject}\n\n{snippet[:500]}"},
        )
        data_leads.update_lead(lead["id"], {})

    return JSONResponse({"ok": True, "matched": len(matched)})


@router.post("/sales/outreach/check-replies")
async def sales_check_replies(request: Request, since_minutes: int = Form(60)):
    """Check Gmail inbox for replies to our sent emails.
    Routes found replies to reply_handler and notification."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    results = {"checked": 0, "replies": [], "notifications": []}

    if cfg.DEMO_MODE:
        # Demo: simulate a reply
        from services.sales.reply_handler import handle_reply
        from services.sales.notification import notify_edwin_reply

        reply = {
            "from_email": "ahmad@tamansari.my",
            "from_name": "Ahmad bin Ismail",
            "subject": "Re: Quick question about Restoran Taman Sari",
            "body": "Hi! I'm interested. Can you tell me more about your AI solutions?",
        }

        all_leads = [_normalize_lead(ld) for ld in data_leads.get_all_leads()]
        lead = next((l for l in all_leads if "ahmad" in (l.get("email") or "").lower()), None)
        if lead:
            intent_result = handle_reply(reply["body"], reply["from_email"], reply["from_name"], reply["subject"], lead=lead)
            sentiment = intent_result.get("sentiment", "neutral")

            data_leads.create_activity(
                lead["id"], "email",
                f"Inbound reply: {reply['subject']} — Sentiment: {sentiment}",
                {"detail": f"From: {reply['from_name']} <{reply['from_email']}>\nSubject: {reply['subject']}\n\n{reply['body']}\n\nAI Analysis:\nSentiment: {sentiment}\nAuto-reply: {intent_result.get('auto_reply', '(none)')}"},
            )

            if sentiment == "positive":
                data_leads.update_lead_status(lead["id"], "interested")
                lead["status"] = "interested"
                notify_edwin_reply(lead, reply["body"], sentiment, 0.9, intent_result.get("auto_reply", ""))
                results["notifications"].append({"lead_id": lead["id"], "action": "escalate"})
            elif sentiment in ("negative", "unsubscribe"):
                data_leads.update_lead_status(lead["id"], "closed_lost")
                lead["status"] = "closed_lost"

            results["replies"].append({"from": reply["from_email"], "sentiment": sentiment, "lead_id": lead["id"]})

        results["checked"] = 1
        print(f"[Sales/Outreach] Reply check (DEMO): Found {results['checked']} reply, sentiment={results['replies'][0]['sentiment'] if results['replies'] else 'N/A'}")
        return JSONResponse({"ok": True, "demo": True, **results})

    # Production: use Gmail API
    from services.sales.gmail_client import GmailClient
    from services.sales.reply_handler import handle_reply
    from services.sales.notification import notify_edwin_reply

    gmail = GmailClient()
    if not gmail.is_authenticated:
        gmail.authenticate()

    replies = gmail.check_replies(since_minutes=since_minutes)
    results["checked"] = len(replies)
    all_leads = [_normalize_lead(ld) for ld in data_leads.get_all_leads()]

    for reply in replies:
        # Match to lead by email
        sender_email = reply["from_email"]
        # Parse out email from "Name <email>" format
        import re
        match = re.search(r'<([^>]+)>', sender_email)
        if match:
            sender_email = match.group(1)

        lead = next((l for l in all_leads if sender_email.lower() in (l.get("email") or "").lower()), None)
        if not lead:
            results["replies"].append({"from": sender_email, "matched": False})
            continue

        intent_result = handle_reply(reply["body"], sender_email, reply["from_name"], reply["subject"], lead=lead)
        sentiment = intent_result.get("sentiment", "neutral")

        data_leads.create_activity(
            lead["id"], "email",
            f"Inbound reply: {reply['subject']} — Sentiment: {sentiment}",
            {"detail": f"From: {reply['from_name']} <{sender_email}>\nSubject: {reply['subject']}\n\n{reply['body'][:500]}\n\nAI Analysis:\nSentiment: {sentiment}\nAuto-reply: {intent_result.get('auto_reply', '(none)')}"},
        )

        if sentiment == "positive":
            data_leads.update_lead_status(lead["id"], "interested")
            lead["status"] = "interested"
            notify_edwin_reply(lead, reply["body"], sentiment, 0.9, intent_result.get("auto_reply", ""))
            results["notifications"].append({"lead_id": lead["id"], "action": "escalate"})
        elif sentiment in ("negative", "unsubscribe"):
            data_leads.update_lead_status(lead["id"], "closed_lost")
            lead["status"] = "closed_lost"

        results["replies"].append({"from": sender_email, "sentiment": sentiment, "lead_id": lead["id"], "matched": True})

    return JSONResponse({"ok": True, **results})


# ── Target Profiles ────────────────────────────────────────────────────────────


@router.get("/sales/target-profiles", response_class=HTMLResponse)
async def sales_target_profiles_list(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    profiles = data_profiles.list_profiles()
    businesses = data_profiles.list_businesses()
    return _render(request, "sales/target_profile.html", profiles=profiles, businesses=businesses)


@router.post("/sales/target-profiles")
async def sales_target_profiles_create(
    request: Request,
    name: str = Form(...),
    business_id: str = Form(""),
    industries: list[str] = Form([]),
    locations: list[str] = Form([]),
    company_size: str = Form("any"),
    keywords_include: str = Form(""),
    keywords_exclude: str = Form(""),
    min_ai_score: int = Form(7),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    businesses = data_profiles.list_businesses()
    biz = next((b for b in businesses if b["id"] == business_id), None)

    profile_data = {
        "business_id": business_id,
        "business_name": biz["name"] if biz else business_id,
        "name": name,
        "industries": industries if isinstance(industries, list) else [industries],
        "locations": locations if isinstance(locations, list) else [locations],
        "company_size": company_size,
        "keywords_include": [kw.strip() for kw in keywords_include.split(",") if kw.strip()],
        "keywords_exclude": [kw.strip() for kw in keywords_exclude.split(",") if kw.strip()],
        "min_ai_score": min_ai_score,
        "is_active": True,
    }
    data_profiles.create_profile(profile_data)
    return RedirectResponse(url="/sales/target-profiles", status_code=303)


@router.get("/sales/target-profiles/{profile_id}")
async def sales_target_profiles_get(request: Request, profile_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    profile = data_profiles.get_profile(profile_id)
    if not profile:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(profile)


@router.post("/sales/target-profiles/{profile_id}")
async def sales_target_profiles_update(
    request: Request,
    profile_id: str,
    name: str = Form(...),
    business_id: str = Form(""),
    industries: list[str] = Form([]),
    locations: list[str] = Form([]),
    company_size: str = Form("any"),
    keywords_include: str = Form(""),
    keywords_exclude: str = Form(""),
    min_ai_score: int = Form(7),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    existing = data_profiles.get_profile(profile_id)
    if not existing:
        return JSONResponse({"error": "Not found"}, status_code=404)

    businesses = data_profiles.list_businesses()
    biz = next((b for b in businesses if b["id"] == business_id), None)

    data_profiles.update_profile(profile_id, {
        "name": name,
        "business_id": business_id,
        "business_name": biz["name"] if biz else business_id,
        "industries": industries if isinstance(industries, list) else [industries],
        "locations": locations if isinstance(locations, list) else [locations],
        "company_size": company_size,
        "keywords_include": [kw.strip() for kw in keywords_include.split(",") if kw.strip()],
        "keywords_exclude": [kw.strip() for kw in keywords_exclude.split(",") if kw.strip()],
        "min_ai_score": min_ai_score,
    })
    return RedirectResponse(url="/sales/target-profiles", status_code=303)


@router.delete("/sales/target-profiles/{profile_id}")
async def sales_target_profiles_delete(request: Request, profile_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    data_profiles.delete_profile(profile_id)
    return JSONResponse({"ok": True})


# ── Onboarding / Sampling ─────────────────────────────────────────────────────


@router.post("/sales/onboarding/start-sampling")
async def sales_onboarding_start_sampling(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Get current onboarding state from accounts table
    from services.supabase_client import get_supabase as sb
    account = sb().table("accounts").select("sales_onboarding_status,sampling_start_date,sampling_lead_count").eq("id", "00000000-0000-0000-0000-000000000001").single().execute()
    current_status = account.data.get("sales_onboarding_status", "pending") if account.data else "pending"

    if current_status == "sampling":
        return JSONResponse({"error": "Already sampling"}, status_code=400)

    # Create 30 sample leads
    sample_count = 0
    for i in range(30):
        lead_data = _make_create_lead_data(
            name=f"Sample Lead #{i+1}",
            contact=f"contact{i}@sample.com",
            phone=f"+60 1{i:02d}-{i:07d}",
            email=f"sample{i}@leads.my",
            industry=["Food & Beverage", "Retail", "Technology", "Healthcare", "Manufacturing"][i % 5],
            location=["Kuala Lumpur", "Selangor", "Penang", "Johor"][i % 4],
            business="Boleh AI",
            source="sample",
            notes="Sample lead for onboarding evaluation",
            score=5 + (i % 4),
        )
        lead_data["is_sample"] = True
        data_leads.create_lead(lead_data)
        sample_count += 1

    # Update onboarding state in accounts table
    sb().table("accounts").update({
        "sales_onboarding_status": "sampling",
        "sampling_start_date": datetime.utcnow().isoformat(),
        "sampling_lead_count": sample_count,
    }).eq("id", "00000000-0000-0000-0000-000000000001").execute()

    return JSONResponse({"ok": True, "samples_created": sample_count, "status": "sampling"})


@router.get("/sales/onboarding/samples")
async def sales_onboarding_list_samples(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    all_leads = data_leads.get_all_leads()
    samples = [l for l in all_leads if l.get("is_sample")]
    return JSONResponse({"samples": samples, "count": len(samples)})


@router.post("/sales/onboarding/confirm")
async def sales_onboarding_confirm(request: Request, quality_rating: int = Form(7), notes: str = Form("")):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    from services.supabase_client import get_supabase as sb
    account = sb().table("accounts").select("sales_onboarding_status").eq("id", "00000000-0000-0000-0000-000000000001").single().execute()
    status = account.data.get("sales_onboarding_status", "") if account.data else ""

    if status != "sampling":
        return JSONResponse({"error": "Not in sampling phase"}, status_code=400)

    sb().table("accounts").update({
        "sales_onboarding_status": "confirmed",
        "plan_notes": notes,
    }).eq("id", "00000000-0000-0000-0000-000000000001").execute()

    return JSONResponse({"ok": True, "status": "confirmed", "quality_rating": quality_rating})


@router.post("/sales/onboarding/activate")
async def sales_onboarding_activate(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if not user.get("is_admin", False):
        return JSONResponse({"error": "Admin only"}, status_code=403)

    from services.supabase_client import get_supabase as sb
    account = sb().table("accounts").select("sales_onboarding_status").eq("id", "00000000-0000-0000-0000-000000000001").single().execute()
    status = account.data.get("sales_onboarding_status", "") if account.data else ""

    if status != "confirmed":
        return JSONResponse({"error": "Must confirm sampling first"}, status_code=400)

    sb().table("accounts").update({
        "sales_onboarding_status": "active",
    }).eq("id", "00000000-0000-0000-0000-000000000001").execute()

    return JSONResponse({"ok": True, "status": "active", "message": "Real outreach enabled"})


# ── Usage & Limits ─────────────────────────────────────────────────────────────


@router.get("/sales/usage")
async def sales_usage_get(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    limits = data_usage.get_limits() or {}
    usage = {
        "total_leads_scraped": data_usage.get_leads_count_this_month(),
        "total_outreach_sent": data_usage.get_messages_count_this_month(),
        "total_samples": 0,
        "sampling_limit": limits.get("sampling_limit", 30),
        "monthly_outreach_limit": limits.get("monthly_outreach_limit", 500),
        "daily_scrape_limit": limits.get("daily_scrape_limit", 200),
    }
    return JSONResponse(usage)


@router.post("/sales/usage/limits")
async def sales_usage_set_limits(
    request: Request,
    sampling_limit: int = Form(30),
    monthly_outreach_limit: int = Form(500),
    daily_scrape_limit: int = Form(200),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    limits = {
        "sampling_limit": sampling_limit,
        "monthly_outreach_limit": monthly_outreach_limit,
        "daily_scrape_limit": daily_scrape_limit,
    }
    return JSONResponse({"ok": True, "limits": limits})


# ── Updated Scraper (google_maps support) ──────────────────────────────────────


@router.post("/sales/scraper/run")
async def scraper_run(
    request: Request,
    industry: str = Form(""),
    location: str = Form(""),
    max_results: int = Form(20),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})

    # Call real Google Maps scraper
    from services.sales.scraper import scrape_google_maps

    # Build search query from industry + location
    query = f"{industry} {location}" if location else industry

    leads = await scrape_google_maps(query, "", max_results)
    imported = 0
    for ld in leads:
        # Clean company name: remove common suffixes
        name = ld.get("company_name", "")
        for suffix in [" Sdn Bhd", " Sdn. Bhd.", " Bhd", " & Co", " Enterprise", " Trading"]:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break

        lead_data = _make_create_lead_data(
            name=name.strip(),
            contact=ld.get("contact_name", ""),
            phone=ld.get("phone", ""),
            email=ld.get("email", ""),
            industry=industry.lower().replace(" ", "_"),
            location=ld.get("city", "") or location,
            business="Boleh AI",
            source="google_maps",
            notes=ld.get("notes", f"Google Maps scrape — rating: {ld.get('rating', 'N/A')}"),
            score=min(10, int(ld.get("rating", 0) * 2)),
        )
        new_lead = data_leads.create_lead(lead_data)
        data_leads.create_activity(
            new_lead["id"], "note",
            f"Lead found via Google Maps scrape ({industry}, {location})",
            {"detail": f"Found {len(leads)} leads in {location} for {industry} industry"},
        )
        imported += 1

    return JSONResponse({"ok": True, "found": imported})


# ── Real API Scraping ───────────────────────────────────────────────────────────


@router.post("/sales/scraper/google-maps")
async def sales_scraper_google_maps(
    request: Request,
    query: str = Form(...),
    location: str = Form(""),
    max_results: int = Form(10),
    api_key: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Google Maps Places API call via scraper module
    from services.sales.scraper import scrape_google_maps as maps_scraper
    leads = await maps_scraper(query, location, max_results)

    # Import as leads (scraper.py returns _build_record format)
    imported = 0
    for ld in leads:
        lead_data = _make_create_lead_data(
            name=ld.get("company_name", ""),
            contact=ld.get("contact_name", ""),
            phone=ld.get("phone", ""),
            email=ld.get("email", ""),
            industry="other",
            location=ld.get("city", "") or location,
            business="Boleh AI",
            source="google_maps",
            notes=f"Google Maps — rating: {ld.get('rating', 'N/A')}, reviews: {ld.get('review_count', 0)}",
            score=min(10, int((ld.get("rating") or 0) * 2)),
        )
        data_leads.create_lead(lead_data)
        imported += 1

    return JSONResponse({"ok": True, "source": "google_maps", "places_found": len(leads), "imported": imported})


@router.post("/sales/scraper/news")
async def sales_scraper_news(request: Request, query: str = Form(...), max_results: int = Form(10)):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # News RSS via scraper module
    from services.sales.scraper import scrape_news_leads as news_scraper
    leads = await news_scraper(query.split(), max_results)

    # Import as leads
    imported = 0
    for ld in leads:
        lead_data = _make_create_lead_data(
            name=ld.get("company_name", ""),
            contact="",
            phone="",
            email="",
            industry="other",
            location="",
            business="Wise Solutions",
            source="news",
            notes=ld.get("notes", f"Google News lead"),
            score=6,
        )
        data_leads.create_lead(lead_data)
        imported += 1

    return JSONResponse({"ok": True, "source": "news", "articles_found": len(leads), "imported": imported})