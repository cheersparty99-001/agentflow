import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_insert, safe_update, safe_delete
from routers.auth import get_current_user
from datetime import datetime, date, timedelta

router = APIRouter()

env = Environment(loader=FileSystemLoader("templates"))


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


DEMO_POLICIES = [
    # ── Motor ──
    {"id": "d-p1", "customer_name": "Ahmad Razif", "phone": "60123456789", "ic_number": "900101-10-1234", "email": "ahmad@email.com",
     "car_plate": "WXY 1234", "car_make": "Toyota", "car_model": "Vios", "car_year": 2022, "ncd": "25%", "coverage_type": "Comprehensive",
     "expiry_date": (date.today() + timedelta(days=30)).isoformat(), "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-001", "insurer": "Etiqa", "sum_insured": 85000, "premium": 1850},
    {"id": "d-p2", "customer_name": "Tan Wei Ming", "phone": "60198765432", "ic_number": "850615-08-5678", "email": "tanwm@email.com",
     "car_plate": "JHB 5678", "car_make": "Honda", "car_model": "Civic", "car_year": 2023, "ncd": "38%", "coverage_type": "Comprehensive",
     "expiry_date": (date.today() + timedelta(days=14)).isoformat(), "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-002", "insurer": "Allianz", "sum_insured": 120000, "premium": 2200},
    {"id": "d-p9", "customer_name": "Mohd Hafiz", "phone": "60139001122", "ic_number": "930822-07-3344", "email": "hafiz@email.com",
     "car_plate": "KEL 1122", "car_make": "Perodua", "car_model": "Myvi", "car_year": 2024, "ncd": "0%", "coverage_type": "Third Party Fire & Theft",
     "expiry_date": (date.today() + timedelta(days=5)).isoformat(), "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-009", "insurer": "Proton Insurance", "sum_insured": 45000, "premium": 950},
    {"id": "d-p10", "customer_name": "Lily Chang", "phone": "60164002233", "ic_number": "881212-14-5566", "email": "lily@email.com",
     "car_plate": "SGR 5566", "car_make": "BMW", "car_model": "320i", "car_year": 2021, "ncd": "55%", "coverage_type": "Comprehensive",
     "expiry_date": (date.today() + timedelta(days=60)).isoformat(), "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-010", "insurer": "AXA Affin", "sum_insured": 200000, "premium": 4500},

    # ── Medical ──
    {"id": "d-p3", "customer_name": "Priya Nair", "phone": "60112223334", "ic_number": "780301-14-9012", "email": "priya@email.com",
     "coverage_type": "Hospital & Surgical", "dependents": 3,
     "expiry_date": (date.today() + timedelta(days=7)).isoformat(), "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-001", "insurer": "Great Eastern", "sum_insured": 500000, "premium": 3600},
    {"id": "d-p6", "customer_name": "Siti Fatimah", "phone": "60178889990", "ic_number": "850615-08-7777", "email": "siti@email.com",
     "coverage_type": "Cardiac Care", "dependents": 2,
     "expiry_date": (date.today() + timedelta(days=60)).isoformat(), "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-002", "insurer": "Prudential", "sum_insured": 300000, "premium": 2800},
    {"id": "d-p11", "customer_name": "Dr. Ramesh Muthu", "phone": "60178004455", "ic_number": "700510-10-8899", "email": "ramesh@clinic.com",
     "coverage_type": "Critical Illness", "dependents": 4,
     "expiry_date": (date.today() + timedelta(days=120)).isoformat(), "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-003", "insurer": "AIA", "sum_insured": 800000, "premium": 6200},

    # ── Fire ──
    {"id": "d-p4", "customer_name": "Lim Chee Keong", "phone": "60167778889", "ic_number": "720624-08-3456", "email": "limck@email.com",
     "property_address": "12 Jalan Ampang, KL", "property_type": "Terrace House",
     "expiry_date": (date.today() + timedelta(days=45)).isoformat(), "status": "Active", "insurance_type": "fire", "policy_number": "FIR-2026-001", "insurer": "Zurich", "sum_insured": 350000, "premium": 1200},
    {"id": "d-p7", "customer_name": "Raj Kumar", "phone": "60199998887", "ic_number": "810915-10-6677", "email": "raj@email.com",
     "property_address": "5 Persiaran Perdana, PJ", "property_type": "Condominium",
     "expiry_date": (date.today() + timedelta(days=90)).isoformat(), "status": "Active", "insurance_type": "fire", "policy_number": "FIR-2026-002", "insurer": "Tokio Marine", "sum_insured": 600000, "premium": 2100},
    {"id": "d-p12", "customer_name": "Tan Sri William Ng", "phone": "60192001122", "ic_number": "650305-07-1122", "email": "william@nggroup.com",
     "property_address": "1 Jalan Bungsar, Bangsar, KL", "property_type": "Bungalow",
     "expiry_date": (date.today() + timedelta(days=180)).isoformat(), "status": "Active", "insurance_type": "fire", "policy_number": "FIR-2026-003", "insurer": "Allianz", "sum_insured": 2000000, "premium": 6800},

    # ── Travel ──
    {"id": "d-p5", "customer_name": "Nurul Ain", "phone": "60134445556", "ic_number": "921201-08-5566", "email": "nurul@email.com",
     "destination": "Tokyo, Japan", "travel_start": (date.today() + timedelta(days=14)).isoformat(), "travel_end": (date.today() + timedelta(days=21)).isoformat(),
     "expiry_date": (date.today() + timedelta(days=21)).isoformat(), "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-001", "insurer": "AIA", "sum_insured": 200000, "premium": 350},
    {"id": "d-p8", "customer_name": "Emily Wong", "phone": "60155556667", "ic_number": "900410-14-7788", "email": "emily@email.com",
     "destination": "Bali, Indonesia", "travel_start": (date.today() + timedelta(days=7)).isoformat(), "travel_end": (date.today() + timedelta(days=14)).isoformat(),
     "expiry_date": (date.today() + timedelta(days=14)).isoformat(), "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-002", "insurer": "Allianz", "sum_insured": 150000, "premium": 280},
    {"id": "d-p13", "customer_name": "Alex Goh", "phone": "60128003344", "ic_number": "950816-07-9900", "email": "alexgoh@email.com",
     "destination": "London, UK", "travel_start": (date.today() + timedelta(days=30)).isoformat(), "travel_end": (date.today() + timedelta(days=40)).isoformat(),
     "expiry_date": (date.today() + timedelta(days=40)).isoformat(), "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-003", "insurer": "Great Eastern", "sum_insured": 500000, "premium": 680},

    # ── Expired/Cancelled ──
    {"id": "d-p14", "customer_name": "Ong Bee Leng", "phone": "60137001122", "ic_number": "680829-10-3344", "email": "ongbl@email.com",
     "car_plate": "PRK 7890", "car_make": "Proton", "car_model": "Saga", "car_year": 2019, "ncd": "25%", "coverage_type": "Comprehensive",
     "expiry_date": (date.today() - timedelta(days=45)).isoformat(), "status": "Expired", "insurance_type": "motor", "policy_number": "MTR-2025-888", "insurer": "Etiqa", "sum_insured": 35000, "premium": 1100},
    {"id": "d-p15", "customer_name": "Kenny Loo", "phone": "60145003355", "ic_number": "830412-14-5567", "email": "kenny@email.com",
     "car_plate": "JLN 3344", "car_make": "Mazda", "car_model": "CX-5", "car_year": 2022, "ncd": "38%", "coverage_type": "Comprehensive",
     "expiry_date": (date.today() - timedelta(days=10)).isoformat(), "status": "Cancelled", "insurance_type": "motor", "policy_number": "MTR-2025-999", "insurer": "Tokio Marine", "sum_insured": 150000, "premium": 3200},
]


@router.get("/policies", response_class=HTMLResponse)
async def policies_page(request: Request, type: str = "", expiry: str = ""):
    user = await require_user(request)
    if not user:
        return RedirectResponse(url="/login")

    account_id = user.get("account_id")
    sb = get_supabase()

    policies = safe_multi(
        lambda: sb.table("policies").select("*").eq("account_id", account_id).order("expiry_date", desc=False),
        default=DEMO_POLICIES,
    )

    account = safe_single(lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(), default={"agency_name": "Demo Insurance Agency"})
    agency_name = account.get("agency_name", "Agency") if account else "Agency"

    today = date.today()
    
    # Apply filters
    filtered = []
    for p in policies:
        try:
            exp = datetime.strptime(p["expiry_date"], "%Y-%m-%d").date() if isinstance(p["expiry_date"], str) else p["expiry_date"]
            days_left = (exp - today).days
        except Exception:
            days_left = 999
        p["days_left"] = days_left
        p["insurance_type"] = p.get("insurance_type", "motor")

        # Filter by type
        if type and p.get("insurance_type", "") != type:
            continue
        # Filter by expiry
        if expiry:
            exp_int = int(expiry)
            if days_left > exp_int or days_left < 0:
                continue
        filtered.append(p)

    template = env.get_template("policies.html")
    html = template.render(
        policies=filtered,
        agency_name=agency_name,
        demo_mode=True,
        current_path=request.url.path,
        active_type=type,
        active_expiry=expiry,
        is_admin=user.get("is_admin", False),
        user_email=user.get("email", ""),
    )
    return HTMLResponse(html)


@router.post("/policies/add")
async def add_policy(
    request: Request,
    customer_name: str = Form(...),
    phone: str = Form(...),
    expiry_date: str = Form(...),
    insurance_type: str = Form("motor"),
    car_plate: str = Form(""),
    ncd: str = Form(""),
    policy_number: str = Form(""),
    insurer: str = Form(""),
    sum_insured: str = Form("0"),
    premium: str = Form("0"),
    status: str = Form("Active"),
    car_make: str = Form(""),
    car_model: str = Form(""),
    car_year: str = Form(""),
    coverage_type: str = Form(""),
    dependents: str = Form("0"),
    property_address: str = Form(""),
    property_type: str = Form(""),
    destination: str = Form(""),
    travel_start: str = Form(""),
    travel_end: str = Form(""),
    ic_number: str = Form(""),
    email: str = Form(""),
    notes: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    account_id = user.get("account_id")

    safe_insert("policies", {
        "account_id": account_id,
        "customer_name": customer_name,
        "phone": phone,
        "car_plate": car_plate,
        "expiry_date": expiry_date,
        "ncd": ncd,
        "status": status,
        "insurance_type": insurance_type,
        "policy_number": policy_number,
        "insurer": insurer,
        "sum_insured": float(sum_insured) if sum_insured else 0,
        "premium": float(premium) if premium else 0,
        "car_make": car_make,
        "car_model": car_model,
        "car_year": int(car_year) if car_year else None,
        "coverage_type": coverage_type,
        "dependents": int(dependents) if dependents else 0,
        "property_address": property_address,
        "property_type": property_type,
        "destination": destination,
        "travel_start": travel_start,
        "travel_end": travel_end,
        "ic_number": ic_number,
        "email": email,
        "notes": notes,
    })
    return JSONResponse({"success": True})


@router.post("/policies/edit/{policy_id}")
async def edit_policy(
    policy_id: str,
    request: Request,
    customer_name: str = Form(...),
    phone: str = Form(...),
    expiry_date: str = Form(...),
    insurance_type: str = Form("motor"),
    car_plate: str = Form(""),
    ncd: str = Form(""),
    policy_number: str = Form(""),
    insurer: str = Form(""),
    sum_insured: str = Form("0"),
    premium: str = Form("0"),
    status: str = Form("Active"),
    car_make: str = Form(""),
    car_model: str = Form(""),
    car_year: str = Form(""),
    coverage_type: str = Form(""),
    dependents: str = Form("0"),
    property_address: str = Form(""),
    property_type: str = Form(""),
    destination: str = Form(""),
    travel_start: str = Form(""),
    travel_end: str = Form(""),
    ic_number: str = Form(""),
    email: str = Form(""),
    notes: str = Form(""),
):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    safe_update("policies", {
        "customer_name": customer_name,
        "phone": phone,
        "car_plate": car_plate,
        "expiry_date": expiry_date,
        "ncd": ncd,
        "status": status,
        "insurance_type": insurance_type,
        "policy_number": policy_number,
        "insurer": insurer,
        "sum_insured": float(sum_insured) if sum_insured else 0,
        "premium": float(premium) if premium else 0,
        "car_make": car_make,
        "car_model": car_model,
        "car_year": int(car_year) if car_year else None,
        "coverage_type": coverage_type,
        "dependents": int(dependents) if dependents else 0,
        "property_address": property_address,
        "property_type": property_type,
        "destination": destination,
        "travel_start": travel_start,
        "travel_end": travel_end,
        "updated_at": datetime.utcnow().isoformat(),
        "ic_number": ic_number,
        "email": email,
        "notes": notes,
    }, "id", policy_id)

    return JSONResponse({"success": True})


@router.post("/policies/delete/{policy_id}")
async def delete_policy(policy_id: str, request: Request):
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    safe_delete("policies", "id", policy_id)
    return JSONResponse({"success": True})