import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from routers.auth import get_current_user
import config as cfg

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))

# ── Demo Data ──────────────────────────────────────────────────────────────────
LEAD_STATUSES = ["cold", "contacted", "replied", "interested", "closed_lost", "closed_won"]
BUSINESSES = ["Boleh AI", "Wise Solutions"]

SEED_LEADS = [
    {"id": "lead-001", "name": "Restoran Taman Sari", "industry": "food_beverage", "business": "Boleh AI", "score": 8, "status": "contacted", "contact": "Ahmad bin Ismail", "phone": "+60 12-345 6789", "email": "ahmad@tamansari.my", "location": "Kuala Lumpur", "notes": "Interested in AI menu system"},
    {"id": "lead-002", "name": "KB Insurance Agency", "industry": "insurance", "business": "Boleh AI", "score": 9, "status": "interested", "contact": "Khalid Bashir", "phone": "+60 13-456 7890", "email": "khalid@kbinsurance.my", "location": "Penang", "notes": "Wants AI for claims processing"},
    {"id": "lead-003", "name": "Marvelous Retail", "industry": "retail", "business": "Boleh AI", "score": 7, "status": "contacted", "contact": "Siti Nurhaliza", "phone": "+60 14-567 8901", "email": "siti@marvelous.my", "location": "Johor Bahru", "notes": "Chain of 5 stores"},
    {"id": "lead-004", "name": "Beauty Palace Ampang", "industry": "beauty", "business": "Boleh AI", "score": 8, "status": "replied", "contact": "Mei Ling Wong", "phone": "+60 16-789 0123", "email": "meiling@beautypalace.my", "location": "Ampang, KL", "notes": "Demo scheduled for next week"},
    {"id": "lead-005", "name": "Shah Alam Wholesale", "industry": "wholesale", "business": "Boleh AI", "score": 9, "status": "cold", "contact": "Ravi Chandran", "phone": "+60 17-890 1234", "email": "ravi@shahalamwholesale.my", "location": "Shah Alam", "notes": "Large distributor, high potential"},
    {"id": "lead-006", "name": "PrestoPay Malaysia", "industry": "fintech", "business": "Wise Solutions", "score": 9, "status": "interested", "contact": "Tan Li Wei", "phone": "+60 11-2345 6789", "email": "liweitan@prestopay.my", "location": "Kuala Lumpur", "notes": "Series A startup, needs AI chatbot"},
    {"id": "lead-007", "name": "MediTech Solutions", "industry": "healthcare", "business": "Wise Solutions", "score": 8, "status": "replied", "contact": "Dr. Sarah Lim", "phone": "+60 18-901 2345", "email": "sarah@meditech.my", "location": "Selangor", "notes": "Hospital chain, 3 locations"},
    {"id": "lead-008", "name": "EduSmart Learning", "industry": "education", "business": "Wise Solutions", "score": 7, "status": "contacted", "contact": "Prof. Amir Hassan", "phone": "+60 19-012 3456", "email": "amir@edusmart.my", "location": "Cyberjaya", "notes": "EdTech platform with 50K students"},
    {"id": "lead-009", "name": "ShopEase Malaysia", "industry": "ecommerce", "business": "Wise Solutions", "score": 8, "status": "replied", "contact": "Nadia Osman", "phone": "+60 10-1234 5678", "email": "nadia@shopease.my", "location": "Petaling Jaya", "notes": "Wants AI product recommendations"},
    {"id": "lead-010", "name": "LogiSwift MY", "industry": "logistics", "business": "Wise Solutions", "score": 9, "status": "interested", "contact": "Ganesh Krishnan", "phone": "+60 15-678 9012", "email": "ganesh@logiswift.my", "location": "Port Klang", "notes": "Fleet of 200+ vehicles"},
]

SEED_ACTIVITIES = [
    # lead-001: Restoran Taman Sari
    {"lead_id": "lead-001", "type": "call", "summary": "Initial outreach call", "detail": "Called Ahmad to introduce Boleh AI menu system. He was curious but busy. Will call back.", "created_at": (datetime.utcnow() - timedelta(days=14, hours=3)).isoformat()},
    {"lead_id": "lead-001", "type": "email", "summary": "Sent introductory email", "detail": "Sent brochure and pricing via email. Included case studies for F&B industry.", "created_at": (datetime.utcnow() - timedelta(days=13)).isoformat()},
    {"lead_id": "lead-001", "type": "message", "summary": "WhatsApp follow-up", "detail": "Ahmad: 'Can you show me how it works for a menu with 100+ items?' Agent: 'Sure! Let me schedule a demo.'", "created_at": (datetime.utcnow() - timedelta(days=10, hours=12)).isoformat()},
    {"lead_id": "lead-001", "type": "note", "summary": "Demo scheduled", "detail": "Scheduled Zoom demo for next Thursday at 2pm. Ahmad will bring his head chef.", "created_at": (datetime.utcnow() - timedelta(days=8)).isoformat()},

    # lead-002: KB Insurance Agency
    {"lead_id": "lead-002", "type": "call", "summary": "Discovery call", "detail": "Khalid explained their claims process involves 12 steps. Looking for AI automation to reduce to 3-4 steps.", "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat()},
    {"lead_id": "lead-002", "type": "email", "summary": "Sent proposal", "detail": "Sent custom proposal for AI claims automation. Estimated ROI within 6 months.", "created_at": (datetime.utcnow() - timedelta(days=8)).isoformat()},
    {"lead_id": "lead-002", "type": "message", "summary": "Khalid replied excitedly", "detail": "Khalid: 'This looks fantastic! Can we fast-track the implementation? I want to show this to my board.'", "created_at": (datetime.utcnow() - timedelta(days=5, hours=14)).isoformat()},
    {"lead_id": "lead-002", "type": "note", "summary": "Board presentation prep", "detail": "Preparing board deck. Khalid wants a pilot with 50 claims first. Expected close: high.", "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat()},

    # lead-003: Marvelous Retail
    {"lead_id": "lead-003", "type": "call", "summary": "Cold call", "detail": "Spoke with Siti. She runs 5 retail stores and is interested in inventory management AI.", "created_at": (datetime.utcnow() - timedelta(days=7, hours=2)).isoformat()},
    {"lead_id": "lead-003", "type": "email", "summary": "Sent retail case study", "detail": "Sent case study of AI implementation in similar retail chain with 8 stores.", "created_at": (datetime.utcnow() - timedelta(days=6)).isoformat()},
    {"lead_id": "lead-003", "type": "message", "summary": "Siti asked about pricing", "detail": "Siti: 'What are the monthly costs for 5 stores?' Agent sent pricing breakdown.", "created_at": (datetime.utcnow() - timedelta(days=4, hours=10)).isoformat()},

    # lead-004: Beauty Palace Ampang
    {"lead_id": "lead-004", "type": "call", "summary": "Warm introduction", "detail": "Mei Ling was referred by a mutual contact. Very receptive to AI appointment scheduling.", "created_at": (datetime.utcnow() - timedelta(days=6, hours=5)).isoformat()},
    {"lead_id": "lead-004", "type": "email", "summary": "Demo confirmation", "detail": "Confirmed demo for Friday 3pm. Will showcase appointment scheduling and customer CRM.", "created_at": (datetime.utcnow() - timedelta(days=4)).isoformat()},
    {"lead_id": "lead-004", "type": "message", "summary": "Mei Ling confirmed demo", "detail": "Mei Ling: 'Looking forward to it! My team of 12 will join the call.'", "created_at": (datetime.utcnow() - timedelta(days=2, hours=16)).isoformat()},

    # lead-005: Shah Alam Wholesale
    {"lead_id": "lead-005", "type": "call", "summary": "Initial call (no answer)", "detail": "Called Ravi but went to voicemail. Left a brief message.", "created_at": (datetime.utcnow() - timedelta(days=5)).isoformat()},
    {"lead_id": "lead-005", "type": "email", "summary": "Sent intro email", "detail": "Cold email sent with intro about AI for wholesale distribution.", "created_at": (datetime.utcnow() - timedelta(days=4)).isoformat()},
    {"lead_id": "lead-005", "type": "message", "summary": "LinkedIn connection request", "detail": "Sent LinkedIn request with note about AI solutions for wholesale.", "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat()},

    # lead-006: PrestoPay Malaysia
    {"lead_id": "lead-006", "type": "call", "summary": "Intro call with founder", "detail": "Tan Li Wei is the CTO. They're building a fintech platform and need AI customer support chatbot.", "created_at": (datetime.utcnow() - timedelta(days=12, hours=4)).isoformat()},
    {"lead_id": "lead-006", "type": "email", "summary": "Sent technical proposal", "detail": "Detailed technical proposal covering API integration, NLP model, and compliance for fintech.", "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat()},
    {"lead_id": "lead-006", "type": "message", "summary": "Li Wei wants POC", "detail": "Li Wei: 'Can you do a small proof-of-concept first? We need to validate with our investors.'", "created_at": (datetime.utcnow() - timedelta(days=7, hours=8)).isoformat()},
    {"lead_id": "lead-006", "type": "note", "summary": "POC scope defined", "detail": "POC will cover chatbot for 3 common customer queries. Timeline: 2 weeks. Budget: RM 15K.", "created_at": (datetime.utcnow() - timedelta(days=5)).isoformat()},

    # lead-007: MediTech Solutions
    {"lead_id": "lead-007", "type": "call", "summary": "Discovery call", "detail": "Dr. Sarah Lim is the IT director. They want AI for patient scheduling and follow-up automation.", "created_at": (datetime.utcnow() - timedelta(days=9, hours=3)).isoformat()},
    {"lead_id": "lead-007", "type": "email", "summary": "Sent healthcare compliance docs", "detail": "Sent HIPAA compliance documentation and data security whitepaper.", "created_at": (datetime.utcnow() - timedelta(days=7)).isoformat()},
    {"lead_id": "lead-007", "type": "message", "summary": "Sarah requested more info", "detail": "Sarah: 'Can you share how the AI handles patient data encryption?' Sent detailed response.", "created_at": (datetime.utcnow() - timedelta(days=4, hours=11)).isoformat()},

    # lead-008: EduSmart Learning
    {"lead_id": "lead-008", "type": "call", "summary": "Intro call", "detail": "Prof. Amir is the academic director. He wants AI for personalized learning paths for 50K students.", "created_at": (datetime.utcnow() - timedelta(days=11, hours=5)).isoformat()},
    {"lead_id": "lead-008", "type": "email", "summary": "Sent education sector proposal", "detail": "Sent proposal covering adaptive learning, AI tutoring, and analytics dashboard.", "created_at": (datetime.utcnow() - timedelta(days=9)).isoformat()},
    {"lead_id": "lead-008", "type": "message", "summary": "Amir has budget questions", "detail": "Amir: 'We're on a tight budget as an edtech. Any educational discounts?' Agent: 'Let me check our education pricing.'", "created_at": (datetime.utcnow() - timedelta(days=6, hours=14)).isoformat()},

    # lead-009: ShopEase Malaysia
    {"lead_id": "lead-009", "type": "call", "summary": "Product demo call", "detail": "Nadia is the head of product. Demoed AI recommendation engine. She was very impressed.", "created_at": (datetime.utcnow() - timedelta(days=8, hours=2)).isoformat()},
    {"lead_id": "lead-009", "type": "email", "summary": "Sent technical specs", "detail": "Sent API documentation and integration guide for their existing platform.", "created_at": (datetime.utcnow() - timedelta(days=6)).isoformat()},
    {"lead_id": "lead-009", "type": "message", "summary": "Nadia wants trial access", "detail": "Nadia: 'Can we get a 14-day sandbox trial? My dev team wants to test the API.' Agent set up sandbox access.", "created_at": (datetime.utcnow() - timedelta(days=3, hours=9)).isoformat()},
    {"lead_id": "lead-009", "type": "note", "summary": "Trial activated", "detail": "Sandbox trial activated for ShopEase. Dev team started integration testing. Positive early feedback.", "created_at": (datetime.utcnow() - timedelta(days=1)).isoformat()},

    # lead-010: LogiSwift MY
    {"lead_id": "lead-010", "type": "call", "summary": "Executive meeting", "detail": "Met with Ganesh (COO) and his team. They need AI route optimization and fleet management.", "created_at": (datetime.utcnow() - timedelta(days=13, hours=6)).isoformat()},
    {"lead_id": "lead-010", "type": "email", "summary": "Sent logistics solution deck", "detail": "Deck covering AI route optimization, predictive maintenance, and fuel savings analytics.", "created_at": (datetime.utcnow() - timedelta(days=11)).isoformat()},
    {"lead_id": "lead-010", "type": "message", "summary": "Ganesh wants ROI calc", "detail": "Ganesh: 'Can you provide ROI projections based on our fleet size?' Sent detailed calculation.", "created_at": (datetime.utcnow() - timedelta(days=8, hours=15)).isoformat()},
    {"lead_id": "lead-010", "type": "note", "summary": "Contract negotiation stage", "detail": "Ganesh is presenting to board next week. Estimated deal value: RM 120K/year. High confidence.", "created_at": (datetime.utcnow() - timedelta(days=4)).isoformat()},

    # Additional cross-cutting activities
    {"lead_id": "lead-001", "type": "message", "summary": "Ahmad sent menu PDF", "detail": "Ahmad shared their full menu PDF (124 items). Agent confirmed AI can handle it.", "created_at": (datetime.utcnow() - timedelta(days=6, hours=8)).isoformat()},
    {"lead_id": "lead-003", "type": "note", "summary": "Follow-up call scheduled", "detail": "Siti requested to postpone discussion to next month. Set reminder for 3 weeks.", "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat()},
    {"lead_id": "lead-005", "type": "note", "summary": "Research completed", "detail": "Researched Shah Alam Wholesale — RM 50M annual revenue, 300+ employees. High priority target.", "created_at": (datetime.utcnow() - timedelta(days=2, hours=5)).isoformat()},
    {"lead_id": "lead-007", "type": "message", "summary": "Follow-up scheduled", "detail": "Sarah: 'Let's meet next week with our compliance officer.' Scheduled for Wednesday.", "created_at": (datetime.utcnow() - timedelta(days=1, hours=10)).isoformat()},
    {"lead_id": "lead-008", "type": "note", "summary": "Education discount approved", "detail": "Approved 30% education discount. Revised proposal sent to Prof. Amir.", "created_at": (datetime.utcnow() - timedelta(days=0, hours=6)).isoformat()},
]

# ── Utility ────────────────────────────────────────────────────────────────────

async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


def _get_leads_state(app_state):
    if not hasattr(app_state, "sales_leads") or app_state.sales_leads is None:
        return {"leads": [], "activities": []}
    return app_state.sales_leads


def _save_leads_state(app_state, state):
    app_state.sales_leads = state


# ── Startup Seeder ─────────────────────────────────────────────────────────────

def seed_demo_data(app_state):
    """Call this on application startup to populate demo leads."""
    leads = []
    for ld in SEED_LEADS:
        lead = dict(ld)
        lead["created_at"] = (datetime.utcnow() - timedelta(days=15, hours=int(ld["id"][-1]))).isoformat()
        lead["updated_at"] = datetime.utcnow().isoformat()
        leads.append(lead)

    activities = []
    for act in SEED_ACTIVITIES:
        activities.append(dict(act))

    _save_leads_state(app_state, {"leads": leads, "activities": activities})
    print(f"[Sales] Seeded {len(leads)} demo leads with {len(activities)} activities")


def init_sales_demo_data(app_state):
    """Initialize all sales demo data (call from startup)."""
    # Existing seed
    seed_demo_data(app_state)

    # Target profiles
    if not hasattr(app_state, 'sales_target_profiles') or not app_state.sales_target_profiles:
        app_state.sales_target_profiles = [
            {
                'id': 'tp-001',
                'account_id': '00000000-0000-0000-0000-000000000001',
                'business_id': 'b1000000-0000-0000-0000-000000000001',
                'business_name': 'Boleh AI',
                'name': 'Default - Boleh AI',
                'industries': ['Food & Beverage','Retail','Healthcare','Insurance','Optical','Wholesale'],
                'locations': ['Kuala Lumpur','Selangor','Penang','Johor'],
                'company_size': 'any',
                'keywords_include': ['sdn bhd','enterprise'],
                'keywords_exclude': [],
                'min_ai_score': 7,
                'is_active': True,
            },
            {
                'id': 'tp-002',
                'account_id': '00000000-0000-0000-0000-000000000001',
                'business_id': 'b1000000-0000-0000-0000-000000000002',
                'business_name': 'Wise Solutions',
                'name': 'Default - Wise Solutions',
                'industries': ['Technology','Fintech','Healthcare','Education','Ecommerce'],
                'locations': ['Kuala Lumpur','Selangor'],
                'company_size': 'any',
                'keywords_include': ['startup','funding','expansion'],
                'keywords_exclude': [],
                'min_ai_score': 7,
                'is_active': True,
            },
        ]

    # Onboarding state
    if not hasattr(app_state, 'sales_onboarding'):
        app_state.sales_onboarding = {
            'status': 'pending',
            'sampling_start_date': None,
            'sampling_lead_count': 0,
        }

    # Businesses (for target profile form)
    if not hasattr(app_state, 'sales_businesses'):
        app_state.sales_businesses = [
            {'id': 'b1000000-0000-0000-0000-000000000001', 'name': 'Boleh AI', 'type': 'boleh_ai'},
            {'id': 'b1000000-0000-0000-0000-000000000002', 'name': 'Wise Solutions', 'type': 'wise_solutions'},
        ]

    # Usage & limits
    if not hasattr(app_state, 'sales_usage'):
        app_state.sales_usage = {
            'total_leads_scraped': 0,
            'total_outreach_sent': 0,
            'total_samples': 0,
            'sampling_limit': 30,
            'monthly_outreach_limit': 500,
            'daily_scrape_limit': 200,
        }


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


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/sales/dashboard", response_class=HTMLResponse)
async def sales_dashboard(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    state = _get_leads_state(request.app.state)
    leads = state["leads"]
    activities = state["activities"]

    # Stats per business
    biz_stats = {}
    for b in BUSINESSES:
        biz_leads = [l for l in leads if l["business"] == b]
        biz_stats[b] = {
            "total": len(biz_leads),
            "by_status": {s: len([l for l in biz_leads if l["status"] == s]) for s in LEAD_STATUSES},
            "avg_score": round(sum(l["score"] for l in biz_leads) / len(biz_leads), 1) if biz_leads else 0,
            "industries": list(set(l["industry"] for l in biz_leads)),
        }

    # Recent activity feed (last 15)
    sorted_acts = sorted(activities, key=lambda a: a["created_at"], reverse=True)[:15]

    # Escalation alerts: leads with score >= 8 and status in ("cold", "contacted")
    escalations = [l for l in leads if l["score"] >= 8 and l["status"] in ("cold", "contacted")]

    return _render(request, "sales/dashboard.html",
                   biz_stats=biz_stats,
                   total_leads=len(leads),
                   recent_activities=sorted_acts,
                   escalations=escalations,
                   leads_status_counts={s: len([l for l in leads if l["status"] == s]) for s in LEAD_STATUSES},
                   )


@router.get("/sales/leads", response_class=HTMLResponse)
async def sales_leads(
    request: Request,
    status: str = "",
    business: str = "",
    industry: str = "",
    search: str = "",
    page: int = 1,
):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    state = _get_leads_state(request.app.state)
    leads = state["leads"]

    # Filter
    if status:
        leads = [l for l in leads if l["status"] == status]
    if business:
        leads = [l for l in leads if l["business"] == business]
    if industry:
        leads = [l for l in leads if l["industry"] == industry]
    if search:
        q = search.lower()
        leads = [l for l in leads if q in l["name"].lower() or q in l["contact"].lower() or q in l.get("notes", "").lower()]

    total = len(leads)
    per_page = 10
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    page_leads = leads[start:end]

    all_industries = sorted(set(l["industry"] for l in state["leads"]))

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


@router.get("/sales/leads/{lead_id}", response_class=HTMLResponse)
async def sales_lead_detail(request: Request, lead_id: str):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    state = _get_leads_state(request.app.state)
    lead = next((l for l in state["leads"] if l["id"] == lead_id), None)
    if not lead:
        return RedirectResponse(url="/sales/leads")

    acts = sorted(
        [a for a in state["activities"] if a["lead_id"] == lead_id],
        key=lambda a: a["created_at"],
        reverse=True,
    )

    return _render(request, "sales/lead_detail.html", lead=lead, activities=acts)


@router.post("/sales/leads/{lead_id}/status")
async def sales_lead_update_status(request: Request, lead_id: str, status: str = Form(...)):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    state = _get_leads_state(request.app.state)
    for l in state["leads"]:
        if l["id"] == lead_id:
            l["status"] = status
            l["updated_at"] = datetime.utcnow().isoformat()
            state["activities"].append({
                "lead_id": lead_id,
                "type": "note",
                "summary": f"Status changed to {status}",
                "detail": f"Lead status updated from previous to '{status}' by agent.",
                "created_at": datetime.utcnow().isoformat(),
            })
            _save_leads_state(request.app.state, state)
            return JSONResponse({"ok": True, "status": status})

    return JSONResponse({"error": "Lead not found"}, status_code=404)


@router.post("/sales/leads/{lead_id}/note")
async def sales_lead_add_note(request: Request, lead_id: str, summary: str = Form(...), detail: str = Form("")):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    state = _get_leads_state(request.app.state)
    lead = next((l for l in state["leads"] if l["id"] == lead_id), None)
    if not lead:
        return JSONResponse({"error": "Lead not found"}, status_code=404)

    act = {
        "lead_id": lead_id,
        "type": "note",
        "summary": summary,
        "detail": detail,
        "created_at": datetime.utcnow().isoformat(),
    }
    state["activities"].append(act)
    lead["updated_at"] = datetime.utcnow().isoformat()
    _save_leads_state(request.app.state, state)
    return JSONResponse({"ok": True, "activity": act})


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
    state = _get_leads_state(request.app.state)
    imported = 0
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        lid = f"lead-import-{uuid.uuid4().hex[:8]}"
        state["leads"].append({
            "id": lid,
            "name": parts[0],
            "industry": parts[1] if len(parts) > 1 else "other",
            "business": parts[2] if len(parts) > 2 else "Boleh AI",
            "score": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 5,
            "status": "cold",
            "contact": parts[4] if len(parts) > 4 else "",
            "phone": parts[5] if len(parts) > 5 else "",
            "email": parts[6] if len(parts) > 6 else "",
            "location": parts[7] if len(parts) > 7 else "",
            "notes": parts[8] if len(parts) > 8 else "",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
        imported += 1

    _save_leads_state(request.app.state, state)
    return JSONResponse({"ok": True, "imported": imported})


@router.get("/sales/pipeline", response_class=HTMLResponse)
async def sales_pipeline(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    state = _get_leads_state(request.app.state)
    leads = state["leads"]

    columns = {}
    for s in LEAD_STATUSES:
        columns[s] = [l for l in leads if l["status"] == s]

    return _render(request, "sales/pipeline.html", columns=columns, all_statuses=LEAD_STATUSES)


@router.post("/sales/outreach/trigger")
async def sales_outreach_trigger(request: Request, campaign: str = Form(""), channel: str = Form("whatsapp")):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    state = _get_leads_state(request.app.state)
    # Simulate outreach: pick leads with status "cold" or "contacted"
    targets = [l for l in state["leads"] if l["status"] in ("cold", "contacted")]
    sent_count = 0
    for target in targets[:5]:  # limit to 5 per trigger
        state["activities"].append({
            "lead_id": target["id"],
            "type": "message",
            "summary": f"Outreach via {channel}" + (f" — {campaign}" if campaign else ""),
            "detail": f"Sent automated {channel} message to {target['contact']} at {target['name']}.",
            "created_at": datetime.utcnow().isoformat(),
        })
        sent_count += 1

    _save_leads_state(request.app.state, state)
    return JSONResponse({"ok": True, "sent": sent_count, "channel": channel, "campaign": campaign})


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

    state = _get_leads_state(request.app.state)

    # Accept lead_id directly, or match by phone/name
    lead = None
    if "lead_id" in body:
        lead = next((l for l in state["leads"] if l["id"] == body["lead_id"]), None)
    if not lead:
        matched = [l for l in state["leads"] if phone in l.get("phone", "")]
        if not matched:
            matched = [l for l in state["leads"] if name.lower() in l["name"].lower()]
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
        state["activities"].append({
            "lead_id": lead["id"],
            "type": "message",
            "summary": f"Inbound WhatsApp from {name} — Sentiment: {sentiment}",
            "detail": f"Message: {message[:500]}\n\nAI Analysis:\nSentiment: {sentiment}\nAction: {action}\nAuto-reply: {intent_result.get('auto_reply', '(none)')[:200]}",
            "created_at": datetime.utcnow().isoformat(),
        })

        # Update lead status based on sentiment
        if sentiment in ("negative", "unsubscribe"):
            lead["status"] = "closed_lost"
        elif sentiment == "positive":
            lead["status"] = "interested"
        lead["updated_at"] = datetime.utcnow().isoformat()

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

    _save_leads_state(request.app.state, state)
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

    state = _get_leads_state(request.app.state)
    matched = [l for l in state["leads"] if sender.lower() in l.get("email", "").lower()]

    for lead in matched:
        state["activities"].append({
            "lead_id": lead["id"],
            "type": "email",
            "summary": f"Inbound email: {subject}",
            "detail": f"From: {sender}\nSubject: {subject}\n\n{snippet[:500]}",
            "created_at": datetime.utcnow().isoformat(),
        })
        lead["updated_at"] = datetime.utcnow().isoformat()

    _save_leads_state(request.app.state, state)
    return JSONResponse({"ok": True, "matched": len(matched)})


# ── Target Profiles ────────────────────────────────────────────────────────────


@router.get("/sales/target-profiles", response_class=HTMLResponse)
async def sales_target_profiles_list(request: Request):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    profiles = getattr(request.app.state, "sales_target_profiles", [])
    businesses = getattr(request.app.state, "sales_businesses", [])
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

    if not hasattr(request.app.state, "sales_target_profiles"):
        request.app.state.sales_target_profiles = []

    businesses = getattr(request.app.state, "sales_businesses", [])
    biz = next((b for b in businesses if b["id"] == business_id), None)

    profile = {
        "id": f"tp-{uuid.uuid4().hex[:8]}",
        "account_id": user.get("account_id", "00000000-0000-0000-0000-000000000001"),
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
    request.app.state.sales_target_profiles.append(profile)
    return RedirectResponse(url="/sales/target-profiles", status_code=303)


@router.get("/sales/target-profiles/{profile_id}")
async def sales_target_profiles_get(request: Request, profile_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    profiles = getattr(request.app.state, "sales_target_profiles", [])
    profile = next((p for p in profiles if p["id"] == profile_id), None)
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

    profiles = getattr(request.app.state, "sales_target_profiles", [])
    businesses = getattr(request.app.state, "sales_businesses", [])
    biz = next((b for b in businesses if b["id"] == business_id), None)

    for p in profiles:
        if p["id"] == profile_id:
            p["name"] = name
            p["business_id"] = business_id
            p["business_name"] = biz["name"] if biz else business_id
            p["industries"] = industries if isinstance(industries, list) else [industries]
            p["locations"] = locations if isinstance(locations, list) else [locations]
            p["company_size"] = company_size
            p["keywords_include"] = [kw.strip() for kw in keywords_include.split(",") if kw.strip()]
            p["keywords_exclude"] = [kw.strip() for kw in keywords_exclude.split(",") if kw.strip()]
            p["min_ai_score"] = min_ai_score
            return RedirectResponse(url="/sales/target-profiles", status_code=303)

    return JSONResponse({"error": "Not found"}, status_code=404)


@router.delete("/sales/target-profiles/{profile_id}")
async def sales_target_profiles_delete(request: Request, profile_id: str):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    profiles = getattr(request.app.state, "sales_target_profiles", [])
    request.app.state.sales_target_profiles = [p for p in profiles if p["id"] != profile_id]
    return JSONResponse({"ok": True})


# ── Onboarding / Sampling ─────────────────────────────────────────────────────


@router.post("/sales/onboarding/start-sampling")
async def sales_onboarding_start_sampling(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    onboarding = getattr(request.app.state, "sales_onboarding", {})
    if not onboarding:
        request.app.state.sales_onboarding = {
            "status": "pending",
            "sampling_start_date": None,
            "sampling_lead_count": 0,
        }
        onboarding = request.app.state.sales_onboarding

    if onboarding.get("status") == "sampling":
        return JSONResponse({"error": "Already sampling"}, status_code=400)

    # Create 30 sample leads
    state = _get_leads_state(request.app.state)
    sample_count = 0
    for i in range(30):
        lid = f"sample-{uuid.uuid4().hex[:8]}"
        state["leads"].append({
            "id": lid,
            "name": f"Sample Lead #{i+1}",
            "industry": ["Food & Beverage", "Retail", "Technology", "Healthcare", "Manufacturing"][i % 5],
            "business": "Boleh AI",
            "score": 5 + (i % 4),
            "status": "cold",
            "contact": f"contact{i}@sample.com",
            "phone": f"+60 1{i:02d}-{i:07d}",
            "email": f"sample{i}@leads.my",
            "location": ["Kuala Lumpur", "Selangor", "Penang", "Johor"][i % 4],
            "notes": "Sample lead for onboarding evaluation",
            "is_sample": True,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
        sample_count += 1

    _save_leads_state(request.app.state, state)

    onboarding["status"] = "sampling"
    onboarding["sampling_start_date"] = datetime.utcnow().isoformat()
    onboarding["sampling_lead_count"] = sample_count

    usage = getattr(request.app.state, "sales_usage", {})
    usage["total_samples"] = (usage.get("total_samples", 0) or 0) + sample_count
    usage["total_leads_scraped"] = (usage.get("total_leads_scraped", 0) or 0) + sample_count

    return JSONResponse({"ok": True, "samples_created": sample_count, "status": "sampling"})


@router.get("/sales/onboarding/samples")
async def sales_onboarding_list_samples(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    state = _get_leads_state(request.app.state)
    samples = [l for l in state["leads"] if l.get("is_sample")]
    return JSONResponse({"samples": samples, "count": len(samples)})


@router.post("/sales/onboarding/confirm")
async def sales_onboarding_confirm(request: Request, quality_rating: int = Form(7), notes: str = Form("")):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    onboarding = getattr(request.app.state, "sales_onboarding", {})
    if not onboarding or onboarding.get("status") != "sampling":
        return JSONResponse({"error": "Not in sampling phase"}, status_code=400)

    onboarding["status"] = "confirmed"
    onboarding["quality_rating"] = quality_rating
    onboarding["confirmation_notes"] = notes
    onboarding["confirmed_at"] = datetime.utcnow().isoformat()

    return JSONResponse({"ok": True, "status": "confirmed", "quality_rating": quality_rating})


@router.post("/sales/onboarding/activate")
async def sales_onboarding_activate(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if not user.get("is_admin", False):
        return JSONResponse({"error": "Admin only"}, status_code=403)

    onboarding = getattr(request.app.state, "sales_onboarding", {})
    if not onboarding or onboarding.get("status") != "confirmed":
        return JSONResponse({"error": "Must confirm sampling first"}, status_code=400)

    onboarding["status"] = "active"
    onboarding["activated_at"] = datetime.utcnow().isoformat()

    return JSONResponse({"ok": True, "status": "active", "message": "Real outreach enabled"})


# ── Usage & Limits ─────────────────────────────────────────────────────────────


@router.get("/sales/usage")
async def sales_usage_get(request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    usage = getattr(request.app.state, "sales_usage", {})
    if not usage:
        usage = {
            "total_leads_scraped": 0,
            "total_outreach_sent": 0,
            "total_samples": 0,
            "sampling_limit": 30,
            "monthly_outreach_limit": 500,
            "daily_scrape_limit": 200,
        }
        request.app.state.sales_usage = usage

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

    usage = getattr(request.app.state, "sales_usage", {})
    if not usage:
        usage = {}
        request.app.state.sales_usage = usage

    usage["sampling_limit"] = sampling_limit
    usage["monthly_outreach_limit"] = monthly_outreach_limit
    usage["daily_scrape_limit"] = daily_scrape_limit

    return JSONResponse({"ok": True, "limits": usage})


# ── Updated Scraper (google_maps support) ──────────────────────────────────────


@router.post("/sales/scraper/run")
async def sales_scraper_run(
    request: Request,
    url: str = Form(""),
    source: str = Form("linkedin"),
    query: str = Form(""),
    location: str = Form(""),
    max_results: int = Form(10),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    scraped = []
    usage = getattr(request.app.state, "sales_usage", {})

    if source == "google_maps":
        # Simulate Google Maps scraping
        industries_pool = ["Food & Beverage", "Retail", "Healthcare", "Technology", "Manufacturing", "Logistics", "Education"]
        for i in range(min(max_results, 20)):
            scraped.append({
                "name": f"{query or 'Business'} #{i+1}",
                "industry": industries_pool[i % len(industries_pool)],
                "contact": "N/A",
                "phone": f"+60 1{i:02d}-{i:05d}",
                "email": f"info@business{i}.my",
                "location": location or "Kuala Lumpur",
                "notes": f"Scraped from Google Maps — query: {query or 'N/A'}, location: {location or 'N/A'}",
            })
    elif source == "linkedin":
        scraped.append({"name": "TechCorp Malaysia", "industry": "technology", "contact": "N/A", "phone": "", "email": "", "location": "Kuala Lumpur", "notes": f"Scraped from LinkedIn URL: {url}"})
        scraped.append({"name": "GreenEnergy Solutions", "industry": "energy", "contact": "N/A", "phone": "", "email": "", "location": "Selangor", "notes": f"Scraped from LinkedIn URL: {url}"})
    else:
        # Default simulation
        scraped.append({"name": f"Lead from {source}", "industry": "other", "contact": "N/A", "phone": "", "email": "", "location": "", "notes": f"Scraped from {source}"})

    state = _get_leads_state(request.app.state)
    imported = 0
    for s in scraped:
        lid = f"lead-import-{uuid.uuid4().hex[:8]}"
        state["leads"].append({
            "id": lid,
            "name": s["name"],
            "industry": s["industry"],
            "business": "Boleh AI",
            "score": 5,
            "status": "cold",
            "contact": s["contact"],
            "phone": s["phone"],
            "email": s["email"],
            "location": s["location"],
            "notes": s["notes"],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
        imported += 1

    _save_leads_state(request.app.state, state)
    if usage:
        usage["total_leads_scraped"] = (usage.get("total_leads_scraped", 0) or 0) + imported

    return JSONResponse({"ok": True, "source": source, "query": query, "location": location, "scraped": imported})


# ── Real API Scraping (non-demo) ───────────────────────────────────────────────


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

    # Demo mode: return simulated leads
    if cfg.DEMO_MODE:
        from services.sales.scraper import scrape_google_maps as demo_scrape
        leads = await demo_scrape(query, location, max_results)
        return JSONResponse({"ok": True, "source": "google_maps", "places_found": len(leads), "imported": len(leads), "demo": True})

    # Real Google Maps Places API call
    import httpx

    places = []
    try:
        params = {
            "query": f"{query} {location}" if location else query,
            "key": api_key or getattr(cfg, "GOOGLE_MAPS_API_KEY", "") or "",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params=params,
            )
            data = resp.json()
            for result in data.get("results", [])[:max_results]:
                places.append({
                    "name": result.get("name", "Unknown"),
                    "address": result.get("formatted_address", ""),
                    "rating": result.get("rating"),
                    "place_id": result.get("place_id", ""),
                    "types": result.get("types", []),
                    "location": result.get("geometry", {}).get("location", {}),
                })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    # Import as leads
    state = _get_leads_state(request.app.state)
    imported = 0
    for p in places:
        lid = f"lead-gmaps-{uuid.uuid4().hex[:8]}"
        state["leads"].append({
            "id": lid,
            "name": p["name"],
            "industry": (p.get("types") or ["other"])[0] if p.get("types") else "other",
            "business": "Boleh AI",
            "score": min(10, int((p.get("rating") or 0) * 2)),
            "status": "cold",
            "contact": "",
            "phone": "",
            "email": "",
            "location": p.get("address", ""),
            "notes": f"Google Maps — place_id: {p['place_id']}, rating: {p.get('rating', 'N/A')}",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
        imported += 1

    _save_leads_state(request.app.state, state)
    usage = getattr(request.app.state, "sales_usage", {})
    if usage:
        usage["total_leads_scraped"] = (usage.get("total_leads_scraped", 0) or 0) + imported

    return JSONResponse({"ok": True, "source": "google_maps", "places_found": len(places), "imported": imported})


@router.post("/sales/scraper/news")
async def sales_scraper_news(request: Request, query: str = Form(...), max_results: int = Form(10)):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Demo mode: return simulated news leads
    if cfg.DEMO_MODE:
        from services.sales.scraper import scrape_news_leads as demo_scrape
        leads = await demo_scrape(query.split(), max_results)
        return JSONResponse({"ok": True, "source": "news", "articles_found": len(leads), "imported": len(leads), "demo": True})

    # Google News RSS feed
    import httpx
    import xml.etree.ElementTree as ET
    from urllib.parse import quote

    articles = []
    try:
        search_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-MY&gl=MY&ceid=MY:en"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(search_url)
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for item in list(root.iter("item"))[:max_results]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else ""
                articles.append({
                    "title": title,
                    "url": link,
                    "published": pub_date,
                    "source": source_name,
                })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    # Import as leads (from news mentions)
    state = _get_leads_state(request.app.state)
    imported = 0
    for art in articles[:max_results]:
        lid = f"lead-news-{uuid.uuid4().hex[:8]}"
        state["leads"].append({
            "id": lid,
            "name": f"News: {art['title'][:60]}",
            "industry": "other",
            "business": "Boleh AI",
            "score": 6,
            "status": "cold",
            "contact": "",
            "phone": "",
            "email": "",
            "location": "",
            "notes": f"Google News — {art['source']}: {art['title']} ({art['url']})",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        })
        imported += 1

    _save_leads_state(request.app.state, state)
    usage = getattr(request.app.state, "sales_usage", {})
    if usage:
        usage["total_leads_scraped"] = (usage.get("total_leads_scraped", 0) or 0) + imported

    return JSONResponse({"ok": True, "source": "news", "articles_found": len(articles), "imported": imported})