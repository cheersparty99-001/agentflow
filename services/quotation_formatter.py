"""Quotation Formatter — generates formatted insurance quotations."""

import config as cfg
from datetime import datetime, date, timedelta
from services.supabase_client import get_supabase, safe_single, safe_multi, safe_insert

# Demo policies for quotation generation
DEMO_POLICIES_QUOTATION = [
    {
        "id": "q-demo-1", "customer_name": "Ahmad Razif", "phone": "60123456789",
        "ic_number": "900101-10-1234", "email": "ahmad@email.com",
        "insurance_type": "motor", "car_make": "Toyota", "car_model": "Vios",
        "car_year": 2022, "car_plate": "WXY 1234", "ncd": "25%",
        "coverage_type": "Comprehensive", "sum_insured": 85000,
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
    },
    {
        "id": "q-demo-2", "customer_name": "Lily Chang", "phone": "60164002233",
        "ic_number": "881212-14-5566", "email": "lily@email.com",
        "insurance_type": "motor", "car_make": "BMW", "car_model": "320i",
        "car_year": 2021, "car_plate": "SGR 5566", "ncd": "55%",
        "coverage_type": "Comprehensive", "sum_insured": 200000,
        "expiry_date": (date.today() + timedelta(days=60)).isoformat(),
    },
    {
        "id": "q-demo-3", "customer_name": "Siti Fatimah", "phone": "60178889990",
        "ic_number": "850615-08-7777", "email": "siti@email.com",
        "insurance_type": "medical", "dependents": 2,
        "coverage_type": "Hospital & Surgical", "sum_insured": 300000,
        "expiry_date": (date.today() + timedelta(days=60)).isoformat(),
    },
    {
        "id": "q-demo-4", "customer_name": "Dr. Ramesh Muthu", "phone": "60178004455",
        "ic_number": "700510-10-8899", "email": "ramesh@clinic.com",
        "insurance_type": "medical", "dependents": 4,
        "coverage_type": "Critical Illness", "sum_insured": 800000,
        "expiry_date": (date.today() + timedelta(days=120)).isoformat(),
    },
    {
        "id": "q-demo-5", "customer_name": "Lim Chee Keong", "phone": "60167778889",
        "ic_number": "720624-08-3456", "email": "limck@email.com",
        "insurance_type": "fire", "property_address": "12, Jalan Ampang, KL",
        "property_type": "Terrace House", "sum_insured": 350000,
        "expiry_date": (date.today() + timedelta(days=45)).isoformat(),
    },
    {
        "id": "q-demo-6", "customer_name": "Tan Sri William Ng", "phone": "60192001122",
        "ic_number": "650305-07-1122", "email": "william@nggroup.com",
        "insurance_type": "fire", "property_address": "1 Jalan Bungsar, Bangsar, KL",
        "property_type": "Bungalow", "sum_insured": 2000000,
        "expiry_date": (date.today() + timedelta(days=180)).isoformat(),
    },
    {
        "id": "q-demo-7", "customer_name": "Nurul Ain", "phone": "60134445556",
        "ic_number": "921201-08-5566", "email": "nurul@email.com",
        "insurance_type": "travel", "destination": "Tokyo, Japan",
        "travel_start": (date.today() + timedelta(days=14)).isoformat(),
        "travel_end": (date.today() + timedelta(days=21)).isoformat(),
        "sum_insured": 200000,
        "expiry_date": (date.today() + timedelta(days=21)).isoformat(),
    },
    {
        "id": "q-demo-8", "customer_name": "Alex Goh", "phone": "60128003344",
        "ic_number": "950816-07-9900", "email": "alexgoh@email.com",
        "insurance_type": "travel", "destination": "London, UK",
        "travel_start": (date.today() + timedelta(days=30)).isoformat(),
        "travel_end": (date.today() + timedelta(days=40)).isoformat(),
        "sum_insured": 500000,
        "expiry_date": (date.today() + timedelta(days=40)).isoformat(),
    },
]

# Premium calculation rules (demo rates — not actual insurer rates)
PREMIUM_RATES = {
    "motor": {
        "base": 1200,
        "per_100k_value": 350,
        "ncd_discount": {"0%": 0, "25%": 0.25, "38%": 0.38, "55%": 0.55},
        "loading_young_driver": 0.15,  # under 25
        "comprehensive_multiplier": 1.0,
        "third_party_multiplier": 0.6,
    },
    "medical": {
        "base": 1800,
        "per_100k_coverage": 400,
        "per_dependent": 350,
    },
    "fire": {
        "base": 800,
        "per_100k_value": 200,
        "terrace_house_multiplier": 1.0,
        "condo_multiplier": 0.8,
        "bungalow_multiplier": 1.3,
    },
    "travel": {
        "base": 150,
        "per_day": 25,
        "per_100k_coverage": 50,
        "asia_multiplier": 1.0,
        "others_multiplier": 1.5,
    },
}


def run(account_id: str, policy_id: str = "", demo_mode: bool = True, log_store: list = None) -> dict:
    """Generate a quotation for a given policy or customer. Returns quotation data."""
    quotation = None

    if demo_mode:
        if policy_id:
            quotation = _find_demo_policy(policy_id)
        if not quotation:
            # Generate for first demo policy
            quotation = DEMO_POLICIES_QUOTATION[0]

    if not quotation:
        return {"error": "Policy not found", "success": False}

    # Calculate premium
    premium_data = _calculate_premium(quotation)
    premium_data["customer"] = {
        "name": quotation.get("customer_name", ""),
        "phone": quotation.get("phone", ""),
        "email": quotation.get("email", ""),
        "ic_number": quotation.get("ic_number", ""),
    }
    premium_data["insurance_type"] = quotation.get("insurance_type", "")
    premium_data["policy_id"] = quotation.get("id", "")
    premium_data["success"] = True

    # Log the quotation generation
    if log_store is not None and demo_mode:
        log_store.append({
            "module": "quotation_formatter",
            "action": "generate_quotation",
            "policy_id": quotation.get("id", ""),
            "customer": quotation.get("customer_name", ""),
            "status": "demo",
            "message": f"DEMO -- Generated quotation for {quotation.get('customer_name', '')} ({quotation.get('insurance_type', '')}) — RM {premium_data.get('total_premium', 0):,.2f}",
            "created_at": datetime.utcnow().isoformat(),
        })

    return premium_data


def run_all(account_id: str, demo_mode: bool = True, log_store: list = None) -> dict:
    """Generate quotations for all demo policies. Returns summary."""
    results = []
    total_premium = 0

    policies = DEMO_POLICIES_QUOTATION if demo_mode else []

    for policy in policies:
        premium_data = _calculate_premium(policy)
        premium_data["customer_name"] = policy.get("customer_name", "")
        premium_data["insurance_type"] = policy.get("insurance_type", "")
        premium_data["policy_id"] = policy.get("id", "")
        total_premium += premium_data.get("total_premium", 0)
        results.append(premium_data)

        if log_store is not None and demo_mode:
            log_store.append({
                "module": "quotation_formatter",
                "action": "generate_quotation",
                "policy_id": policy.get("id", ""),
                "customer": policy.get("customer_name", ""),
                "status": "demo",
                "message": f"DEMO -- Generated quotation for {policy.get('customer_name', '')} — RM {premium_data.get('total_premium', 0):,.2f}",
                "created_at": datetime.utcnow().isoformat(),
            })

    return {
        "success": True,
        "total": len(results),
        "total_premium": total_premium,
        "quotations": results,
    }


def _find_demo_policy(policy_id: str) -> dict:
    """Find a demo policy by ID."""
    for p in DEMO_POLICIES_QUOTATION:
        if p["id"] == policy_id:
            return p
    return None


def _calculate_premium(policy: dict) -> dict:
    """Calculate premium breakdown based on insurance type and customer data."""
    ins_type = policy.get("insurance_type", "motor")
    rates = PREMIUM_RATES.get(ins_type, PREMIUM_RATES["motor"])
    breakdown = {}
    total = 0
    discounts = []
    loadings = []

    if ins_type == "motor":
        sum_insured = policy.get("sum_insured", 85000)
        car_value_component = (sum_insured / 100000) * rates["per_100k_value"]
        coverage_mult = rates.get(policy.get("coverage_type", "Comprehensive").lower().replace(" ", "_") + "_multiplier", 1.0)

        base_premium = rates["base"]
        value_premium = car_value_component
        total = (base_premium + value_premium) * coverage_mult

        breakdown = {
            "base_premium": round(base_premium, 2),
            "value_premium": round(value_premium, 2),
            "coverage_multiplier": coverage_mult,
            "subtotal": round(total, 2),
        }

        # NCD discount
        ncd = policy.get("ncd", "0%")
        ncd_rate = rates["ncd_discount"].get(ncd, 0)
        if ncd_rate > 0:
            ncd_discount = round(total * ncd_rate, 2)
            total -= ncd_discount
            discounts.append(f"NCD {ncd}: -RM {ncd_discount:,.2f}")

        breakdown["ncd"] = ncd
        breakdown["ncd_discount"] = round(total * ncd_rate, 2) if ncd_rate > 0 else 0

    elif ins_type == "medical":
        sum_insured = policy.get("sum_insured", 500000)
        dependents = policy.get("dependents", 0)
        coverage_premium = (sum_insured / 100000) * rates["per_100k_coverage"]
        dependent_premium = dependents * rates["per_dependent"]

        total = rates["base"] + coverage_premium + dependent_premium
        breakdown = {
            "base_premium": rates["base"],
            "coverage_premium": round(coverage_premium, 2),
            "dependent_premium": round(dependent_premium, 2),
            "dependents": dependents,
        }

    elif ins_type == "fire":
        sum_insured = policy.get("sum_insured", 350000)
        prop_type = policy.get("property_type", "Terrace House").lower()
        multiplier_key = prop_type.replace(" ", "_") + "_multiplier"
        prop_mult = rates.get(multiplier_key, 1.0)

        value_premium = (sum_insured / 100000) * rates["per_100k_value"]
        total = (rates["base"] + value_premium) * prop_mult

        breakdown = {
            "base_premium": rates["base"],
            "value_premium": round(value_premium, 2),
            "property_multiplier": prop_mult,
        }

    elif ins_type == "travel":
        destination = policy.get("destination", "Asia").lower()
        is_asia = any(k in destination for k in ["asia", "malaysia", "singapore", "thailand", "indonesia", "japan", "korea", "china", "taiwan", "hong kong", "vietnam", "philippines"])
        region_mult = rates["asia_multiplier"] if is_asia else rates["others_multiplier"]

        travel_start = policy.get("travel_start", date.today().isoformat())
        travel_end = policy.get("travel_end", (date.today() + timedelta(days=7)).isoformat())
        try:
            days = (datetime.strptime(travel_end[:10], "%Y-%m-%d") - datetime.strptime(travel_start[:10], "%Y-%m-%d")).days
            days = max(days, 1)
        except Exception:
            days = 7

        sum_insured = policy.get("sum_insured", 200000)
        day_premium = days * rates["per_day"]
        coverage_premium = (sum_insured / 100000) * rates["per_100k_coverage"]

        total = (rates["base"] + day_premium + coverage_premium) * region_mult
        breakdown = {
            "base_premium": rates["base"],
            "day_premium": round(day_premium, 2),
            "coverage_premium": round(coverage_premium, 2),
            "region_multiplier": region_mult,
            "travel_days": days,
        }

    # Add the breakdown to the result
    result = {
        "insurance_type": ins_type,
        "breakdown": breakdown,
        "discounts": discounts,
        "loadings": loadings,
        "total_premium": round(total, 2),
    }

    # Add customer and policy info
    for key in ["customer_name", "phone", "email", "ic_number", "car_make", "car_model",
                "car_plate", "car_year", "ncd", "coverage_type", "property_address",
                "property_type", "destination", "travel_start", "travel_end", "dependents",
                "sum_insured", "expiry_date"]:
        if key in policy:
            result[key] = policy[key]

    return result