import os
import uuid
import json
import random
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from routers.auth import get_current_user
import config as cfg
from data import leads as data_leads, profiles as data_profiles, usage as data_usage

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"), autoescape=True)

# ── Demo Data ──────────────────────────────────────────────────────────────────
LEAD_STATUSES = ["cold", "contacted", "replied", "interested", "closed_lost", "closed_won"]
BUSINESSES = ["Boleh AI", "Wise Solutions", "Flowreach"]

# ── Normalization helpers ───────────────────────────────────────────────────────

# Map business_id -> business name (also used in templates)
_BUSINESS_NAME_MAP = {
    "b1000000-0000-0000-0000-000000000001": "Boleh AI",
    "b2000000-0000-0000-0000-000000000002": "Wise Solutions",
    "b3000000-0000-0000-0000-000000000003": "Flowreach",
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


# ── Helper functions for template rendering ────────────────────────────────────

async def _render(request, template_name, **extra):
    from routers.auth import get_current_user
    user = await get_current_user(request) or {}
    tmpl = env.get_template(template_name)
    html = tmpl.render(
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


# ── Business hours check ─────────────────────────────────────────────────────────

def _is_business_hours() -> tuple[bool, str]:
    """Check if current time is within Malaysian business hours (Mon-Fri, 9am-6pm MYT / UTC+8).
    Returns (True, "") if within hours, or (False, reason_msg) if outside.
    """
    now_utc = datetime.utcnow()
    myt_offset = timedelta(hours=8)
    now_myt = now_utc + myt_offset
    weekday = now_myt.weekday()  # 0=Mon, 6=Sun
    hour = now_myt.hour
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if weekday >= 5:
        return False, f"Outside business hours — today is {day_names[weekday]} (MYT). Sends only run Mon-Fri, 9am-6pm MYT."
    if hour < 9 or hour >= 18:
        return False, f"Outside business hours — current time is {now_myt.strftime('%H:%M')} MYT. Sends only run 9am-6pm MYT."
    return True, ""


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

    return await _render(request, "sales/dashboard.html",
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

    return await _render(request, "sales/leads.html",
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
    
    account_id = user.get("account_id", "")
    agent_name = user.get("name", "The Flowreach Team")
    agent_title = user.get("title", "B2B Sales Automation")
    
    from services.sales.message_gen import generate_message
    
    try:
        result = generate_message(
            lead=lead,
            channel="email",
            message_type="cold",
            agent_name=agent_name,
            agent_title=agent_title,
            account_id=account_id,
        )
        return JSONResponse({
            "ok": True,
            "subject": result["subject"],
            "body": result["body"],
            "generated_by": result.get("generated_by", "ai"),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": f"Failed to generate email: {str(e)}"})


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


@router.post("/api/leads/{lead_id}/score")
async def score_lead(request: Request, lead_id: str):
    """Score a single lead using AI. For testing/verification."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id", "")
    if not account_id:
        return JSONResponse({"ok": False, "error": "No account_id in session"}, status_code=400)

    lead = data_leads.get_lead(lead_id)
    if not lead:
        return JSONResponse({"ok": False, "error": "Lead not found"}, status_code=404)

    from services.sales.qualifier import qualify_lead

    try:
        result = qualify_lead(lead, account_id=account_id)

        # Persist score back to leads table
        data_leads.update_lead(lead_id, {
            "ai_score": result.get("ai_score"),
            "ai_score_reason": result.get("ai_score_reason"),
            "score": result.get("score"),
            "status": result.get("status"),
        })

        return JSONResponse({
            "ok": True,
            "company_name": lead.get("company_name", ""),
            "ai_score": result.get("ai_score"),
            "ai_score_reason": result.get("ai_score_reason"),
            "status": result.get("status"),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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
    business = body.get("business", "")
    message_type = body.get("message_type", "cold")
    channel = body.get("channel", "email")

    if not lead_ids:
        return JSONResponse({"ok": False, "error": "No leads selected"})

    account_id = user.get("account_id", "")
    agent_name = user.get("name", "The Flowreach Team")
    agent_title = user.get("title", "B2B Sales Automation")

    # ── 1. Business hours check ──
    ok, msg = _is_business_hours()
    if not ok:
        return JSONResponse({"ok": False, "error": msg})

    # ── 2. Cap at 20 leads per batch ──
    total = len(lead_ids)
    queued = 0
    if total > 20:
        queued = total - 20
        lead_ids = lead_ids[:20]

    # ── 3. Process each lead ──
    from services.sales.message_gen import generate_message
    from services.sales import usage as sales_usage

    sent = 0
    results = []
    stopped_early = False

    for i, lid in enumerate(lead_ids):
        lead = data_leads.get_lead(lid)
        if not lead:
            results.append({"lead_id": lid, "company_name": "?", "status": "skipped", "error": "Lead not found"})
            continue

        company_name = lead.get("company_name", lead.get("name", "Unknown"))
        to_email = lead.get("email", "")

        if not to_email:
            results.append({"lead_id": lid, "company_name": company_name, "status": "skipped", "error": "No email address"})
            continue

        # Check monthly/daily usage limits
        limit_check = sales_usage.check_limits(account_id, "message")
        if not limit_check.get("allowed"):
            stopped_early = True
            results.append({
                "lead_id": lid, "company_name": company_name,
                "status": "skipped", "error": limit_check.get("reason", "Usage limit reached"),
            })
            break

        # Generate AI copy
        try:
            message = generate_message(
                lead=lead,
                channel=channel,
                message_type=message_type,
                agent_name=agent_name,
                agent_title=agent_title,
                account_id=account_id,
                company_name_override=business,
            )
        except Exception as e:
            err_msg = f"Message generation failed: {str(e)}"
            print(f"[Sales/Outreach] {err_msg}")
            results.append({"lead_id": lid, "company_name": company_name, "status": "failed", "error": err_msg})
            continue

        subject = message.get("subject", "")
        body_text = message.get("body", "")

        # Send the email via Gmail API
        send_result = _send_single_email(account_id, lid, to_email, subject, body_text)

        if send_result.get("ok"):
            # ── Success ──
            if lead.get("status") in ("cold", "qualified"):
                data_leads.update_lead_status(lid, "contacted")
            data_leads.create_activity(
                lid, "email",
                f"Outreach sent to {to_email}",
                {"subject": subject, "detail": f"Auto-generated outreach message for {company_name}"},
            )
            sent += 1
            results.append({"lead_id": lid, "company_name": company_name, "status": "sent"})
            print(f"[Sales/Outreach] Sent to {company_name}: success")
        else:
            # ── Failure — log and continue ──
            error = send_result.get("error", "Send failed")
            data_leads.create_activity(
                lid, "email",
                f"Email FAILED: {error}",
                {"detail": f"To: {to_email}, Subject: {subject}, Error: {error}"},
            )
            results.append({"lead_id": lid, "company_name": company_name, "status": "failed", "error": error})
            print(f"[Sales/Outreach] Sent to {company_name}: fail — {error}")

        # Random delay between sends (30-60 seconds)
        if i < len(lead_ids) - 1:
            delay = random.uniform(30, 60)
            print(f"[Sales/Outreach] Waiting {delay:.0f}s before next send...")
            time.sleep(delay)

    # ── Build response ──
    resp = {
        "ok": True,
        "total": total,
        "sent": sent,
        "failed": len([r for r in results if r["status"] == "failed"]),
        "skipped": len([r for r in results if r["status"] == "skipped"]),
        "results": results,
    }
    if queued:
        resp["queued"] = queued
        resp["message"] = (
            f"Processed first 20 leads. {queued} lead(s) remaining — "
            f"submit a new request with their lead_ids to process the rest."
        )
    if stopped_early:
        resp["stopped_early"] = True

    return JSONResponse(resp)


@router.get("/sales/outreach/preview")
async def outreach_preview(request: Request):
    """Preview leads ready for outreach (score >= 7, status=cold) with AI-generated copy.
    Returns the generated email subject/body so the admin can review before sending.
    """
    user = await require_user(request)
    if not user:
        return JSONResponse({"ok": False, "error": "Not authenticated"})

    account_id = user.get("account_id", "")
    agent_name = user.get("name", "The Flowreach Team")
    agent_title = user.get("title", "B2B Sales Automation")

    # Find leads with score >= 7 AND status == "cold"
    all_leads = data_leads.get_all_leads()
    candidates = [
        l for l in all_leads
        if (l.get("ai_score") or l.get("score") or 0) >= 7 and l.get("status") in ("cold", "qualified")
    ]

    leads_with_email = [l for l in candidates if l.get("email")]
    leads_without_email = [l for l in candidates if not l.get("email")]

    from services.sales.message_gen import generate_message

    previews = []
    for lead in leads_with_email:
        try:
            message = generate_message(
                lead=lead,
                channel="email",
                message_type="cold",
                agent_name=agent_name,
                agent_title=agent_title,
                account_id=account_id,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            message = {"subject": "(generation failed)", "body": f"Error: {str(e)}"}

        previews.append({
            "lead_id": lead.get("id", ""),
            "company_name": lead.get("company_name", ""),
            "contact_name": lead.get("contact_name", ""),
            "email": lead.get("email", ""),
            "subject": message.get("subject", ""),
            "body": message.get("body", ""),
            "ai_score": lead.get("ai_score") or lead.get("score") or 0,
        })

    return JSONResponse({
        "total": len(candidates),
        "total_with_email": len(leads_with_email),
        "total_without_email": len(leads_without_email),
        "leads": previews,
    })


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

    return await _render(request, "sales/lead_detail.html", lead=lead, activities=acts)


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

    return await _render(request, "sales/pipeline.html", columns=columns, all_statuses=LEAD_STATUSES)


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
    user = await require_user(request)
    if user is None:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
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
    user = await require_user(request)
    if user is None:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
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
    return await _render(request, "sales/target_profile.html", profiles=profiles, businesses=businesses)


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