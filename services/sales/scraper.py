"""Scraper — simulated web scraper for collecting sales leads from various sources.

All scrapers run in demo mode with no real HTTP requests. Returns simulated
lead data matching the sales_leads schema.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

import config as cfg

# ── Demo lead pool ────────────────────────────────────────────────

DEMO_LEADS_BY_SOURCE = {
    "linkedin": [
        {
            "company_name": "TechVision Solutions",
            "website": "https://techvision.my",
            "phone": "60123456789",
            "email": "info@techvision.my",
            "address": "Level 12, Menara KL, Kuala Lumpur",
            "city": "Kuala Lumpur",
            "state": "WP Kuala Lumpur",
            "industry": "Technology",
            "employee_count": 50,
            "contact_name": "Rajesh Kumar",
            "contact_title": "CTO",
            "social_url": "https://linkedin.com/company/techvision",
            "notes": "Growing SaaS company. May need cyber insurance.",
        },
        {
            "company_name": "Elite Retail Group",
            "website": "https://eliteretail.my",
            "phone": "60167778889",
            "email": "hello@eliteretail.my",
            "address": "88 Jalan Meru, Johor Bahru",
            "city": "Johor Bahru",
            "state": "Johor",
            "industry": "Retail",
            "employee_count": 200,
            "contact_name": "Michelle Wong",
            "contact_title": "CEO",
            "social_url": "https://linkedin.com/company/eliteretail",
            "notes": "Major retail chain. Multiple locations.",
        },
    ],
    "google_maps": [
        {
            "company_name": "MediCare Clinic",
            "website": "https://medicare.com.my",
            "phone": "60198765432",
            "email": "admin@medicare.com.my",
            "address": "15 Jalan Burma, Penang",
            "city": "Penang",
            "state": "Penang",
            "industry": "Healthcare",
            "employee_count": 15,
            "contact_name": "Dr. Sarah Tan",
            "contact_title": "Director",
            "social_url": "",
            "notes": "Private clinic expanding to second location.",
        },
        {
            "company_name": "AutoPro Workshop",
            "website": "",
            "phone": "60105556677",
            "email": "autopro@example.com",
            "address": "42 Jalan SS2, Petaling Jaya",
            "city": "Petaling Jaya",
            "state": "Selangor",
            "industry": "Automotive",
            "employee_count": 8,
            "contact_name": "Lee Meng",
            "contact_title": "Owner",
            "social_url": "",
            "notes": "Auto repair shop. Fleet insurance potential.",
        },
    ],
    "facebook": [
        {
            "company_name": "Green Earth Logistics",
            "website": "https://greenearthlogistics.my",
            "phone": "60112223334",
            "email": "contact@greenearth.my",
            "address": "Lot 5, Industrial Park, Shah Alam",
            "city": "Shah Alam",
            "state": "Selangor",
            "industry": "Logistics",
            "employee_count": 120,
            "contact_name": "Ahmad Ismail",
            "contact_title": "Operations Manager",
            "social_url": "https://facebook.com/greenearthlogistics",
            "notes": "Fleet of 50+ trucks. Interested in comprehensive coverage.",
        },
    ],
    "manual": [
        {
            "company_name": "SmartStart Academy",
            "website": "https://smartstart.edu.my",
            "phone": "60134445556",
            "email": "info@smartstart.edu.my",
            "address": "3 Jalan Tun Razak, Ipoh",
            "city": "Ipoh",
            "state": "Perak",
            "industry": "Education",
            "employee_count": 30,
            "contact_name": "Prof. David Ng",
            "contact_title": "Principal",
            "social_url": "",
            "notes": "Private school. Interested in group insurance for staff.",
        },
    ],
}

ALL_SOURCES = list(DEMO_LEADS_BY_SOURCE.keys())


# ── Public API ────────────────────────────────────────────────────


def scrape_leads(
    source: str = "linkedin",
    query: str = "insurance leads",
    max_results: int = 10,
    account_id: str = "00000000-0000-0000-0000-000000000001",
) -> list[dict]:
    """Simulate scraping leads from a given source.

    In DEMO_MODE, returns pre-defined leads filtered by source.
    In production, this would use Playwright / Selenium / APIs.

    Args:
        source: Source platform ('linkedin', 'google_maps', 'facebook', 'manual', 'all').
        query: Search query string (used for simulation, logged but not filtered).
        max_results: Maximum number of leads to return.
        account_id: Account UUID to associate leads with.

    Returns:
        List of lead dicts ready for insertion into sales_leads table.
    """
    if source == "all":
        leads = []
        for src_leads in DEMO_LEADS_BY_SOURCE.values():
            leads.extend(src_leads)
    else:
        leads = DEMO_LEADS_BY_SOURCE.get(source, [])

    # Limit results
    leads = leads[:max_results]

    # Build full lead records with metadata
    result = []
    for lead in leads:
        record = {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "source": source if source != "all" else "linkedin",
            "company_name": lead["company_name"],
            "website": lead.get("website", ""),
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "address": lead.get("address", ""),
            "city": lead.get("city", ""),
            "state": lead.get("state", ""),
            "country": "Malaysia",
            "industry": lead.get("industry", ""),
            "employee_count": lead.get("employee_count", 0),
            "contact_name": lead.get("contact_name", ""),
            "contact_title": lead.get("contact_title", ""),
            "social_url": lead.get("social_url", ""),
            "notes": lead.get("notes", ""),
            "raw_data": json.dumps(lead),
            "status": "new",
            "score": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        result.append(record)

    # Log in demo mode
    if cfg.DEMO_MODE:
        print(
            f"[Sales/Scraper] DEMO -- Scraped {len(result)} leads "
            f"from '{source}' (query='{query}')"
        )

    return result


def get_available_sources() -> list[str]:
    """Return list of supported scrape sources."""
    return list(ALL_SOURCES)


def get_source_stats() -> dict:
    """Return count of demo leads available per source."""
    return {src: len(leads) for src, leads in DEMO_LEADS_BY_SOURCE.items()}