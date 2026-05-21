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
    {"id": "d-p1", "customer_name": "Ahmad Razif", "phone": "60123456789", "car_plate": "WXY 1234", "expiry_date": (date.today() + timedelta(days=30)).isoformat(), "ncd": "25%", "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-001", "insurer": "Etiqa", "car_make": "Toyota", "car_model": "Vios", "car_year": 2022, "coverage_type": "Comprehensive", "sum_insured": 85000, "premium": 1850},
    {"id": "d-p2", "customer_name": "Tan Wei Ming", "phone": "60198765432", "car_plate": "JHB 5678", "expiry_date": (date.today() + timedelta(days=14)).isoformat(), "ncd": "38%", "status": "Active", "insurance_type": "motor", "policy_number": "MTR-2026-002", "insurer": "Allianz", "car_make": "Honda", "car_model": "Civic", "car_year": 2023, "coverage_type": "Comprehensive", "sum_insured": 120000, "premium": 2200},
    {"id": "d-p3", "customer_name": "Priya Nair", "phone": "60112223334", "car_plate": "PEN 9012", "expiry_date": (date.today() + timedelta(days=7)).isoformat(), "ncd": "55%", "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-001", "insurer": "Great Eastern", "coverage_type": "Hospital & Surgical", "dependents": 3, "sum_insured": 500000, "premium": 3600},
    {"id": "d-p4", "customer_name": "Lim Chee Keong", "phone": "60167778889", "car_plate": "KLM 3456", "expiry_date": (date.today() + timedelta(days=45)).isoformat(), "ncd": "0%", "status": "Active", "insurance_type": "fire", "policy_number": "FIR-2026-001", "insurer": "Zurich", "property_address": "12 Jalan Ampang, KL", "property_type": "Terrace House", "sum_insured": 350000, "premium": 1200},
    {"id": "d-p5", "customer_name": "Nurul Ain", "phone": "60134445556", "car_plate": "SGR 7890", "expiry_date": (date.today() + timedelta(days=7)).isoformat(), "ncd": "25%", "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-001", "insurer": "AIA", "destination": "Japan", "travel_start": (date.today() + timedelta(days=14)).isoformat(), "travel_end": (date.today() + timedelta(days=21)).isoformat(), "sum_insured": 200000, "premium": 350},
    {"id": "d-p6", "customer_name": "Siti Fatimah", "phone": "60178889990", "car_plate": "PRK 2468", "expiry_date": (date.today() + timedelta(days=60)).isoformat(), "ncd": "25%", "status": "Active", "insurance_type": "medical", "policy_number": "MED-2026-002", "insurer": "Prudential", "coverage_type": "Cardiac Care", "dependents": 2, "sum_insured": 300000, "premium": 2800},
    {"id": "d-p7", "customer_name": "Raj Kumar", "phone": "60199998887", "car_plate": "JB 1357", "expiry_date": (date.today() + timedelta(days=90)).isoformat(), "ncd": "0%", "status": "Active", "insurance_type": "fire", "policy_number": "FIR-2026-002", "insurer": "Tokio Marine", "property_address": "5 Persiaran Perdana, PJ", "property_type": "Condominium", "sum_insured": 600000, "premium": 2100},
    {"id": "d-p8", "customer_name": "Emily Wong", "phone": "60155556667", "car_plate": "KCH 9753", "expiry_date": (date.today() + timedelta(days=21)).isoformat(), "ncd": "38%", "status": "Active", "insurance_type": "travel", "policy_number": "TRV-2026-002", "insurer": "Allianz", "destination": "Bali, Indonesia", "travel_start": (date.today() + timedelta(days=7)).isoformat(), "travel_end": (date.today() + timedelta(days=14)).isoformat(), "sum_insured": 150000, "premium": 280},
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