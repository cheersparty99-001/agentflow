"""Scraper — web scraper for collecting sales leads.

DEMO_MODE: returns simulated leads (preserve existing demo data).
Production: uses Google Maps Places API + website email extraction.
"""

import json, re, uuid, time, asyncio
from datetime import datetime
from typing import Optional
import httpx
import config as cfg

# ── Demo data (preserve existing) ──
DEMO_LEADS_BY_SOURCE = {
    'google_maps': [
        {'company_name': 'MediCare Clinic', 'website': 'https://medicare.com.my', 'phone': '60198765432', 'email': 'admin@medicare.com.my', 'address': '15 Jalan Burma, Penang', 'city': 'Penang', 'state': 'Penang', 'industry': 'Healthcare', 'employee_count': 15, 'contact_name': 'Dr. Sarah Tan', 'notes': 'Private clinic expanding.'},
        {'company_name': 'AutoPro Workshop', 'website': '', 'phone': '60105556677', 'email': '', 'address': '42 Jalan SS2, Petaling Jaya', 'city': 'Petaling Jaya', 'state': 'Selangor', 'industry': 'Automotive', 'employee_count': 8, 'contact_name': 'Lee Meng', 'notes': 'Auto repair shop.'},
        {'company_name': 'TechVision Solutions', 'website': 'https://techvision.my', 'phone': '60123456789', 'email': 'info@techvision.my', 'address': 'Level 12, Menara KL', 'city': 'Kuala Lumpur', 'state': 'WP Kuala Lumpur', 'industry': 'Technology', 'employee_count': 50, 'contact_name': 'Rajesh Kumar', 'notes': 'Growing SaaS company.'},
        {'company_name': 'Elite Retail Group', 'website': 'https://eliteretail.my', 'phone': '60167778889', 'email': 'hello@eliteretail.my', 'address': '88 Jalan Meru, Johor Bahru', 'city': 'Johor Bahru', 'state': 'Johor', 'industry': 'Retail', 'employee_count': 200, 'contact_name': 'Michelle Wong', 'notes': 'Major retail chain.'},
        {'company_name': 'Green Earth Logistics', 'website': 'https://greenearthlogistics.my', 'phone': '60112223334', 'email': 'contact@greenearth.my', 'address': 'Lot 5, Industrial Park, Shah Alam', 'city': 'Shah Alam', 'state': 'Selangor', 'industry': 'Logistics', 'employee_count': 120, 'contact_name': 'Ahmad Ismail', 'notes': 'Fleet of 50+ trucks.'},
        {'company_name': 'SmartStart Academy', 'website': 'https://smartstart.edu.my', 'phone': '60134445556', 'email': 'info@smartstart.edu.my', 'address': '3 Jalan Tun Razak, Ipoh', 'city': 'Ipoh', 'state': 'Perak', 'industry': 'Education', 'employee_count': 30, 'contact_name': 'Prof. David Ng', 'notes': 'Private school.'},
        {'company_name': 'Bakti Food Industries', 'website': 'https://baktifood.my', 'phone': '60175556688', 'email': '', 'address': 'Lot 3, Industrial Park, Shah Alam', 'city': 'Shah Alam', 'state': 'Selangor', 'industry': 'Food & Beverage', 'employee_count': 80, 'contact_name': 'Mr. Tan', 'notes': 'Food manufacturer.'},
        {'company_name': 'Klinik Pergigian Ampang', 'website': '', 'phone': '60189990001', 'email': '', 'address': '22 Jalan Ampang, Kuala Lumpur', 'city': 'Ampang', 'state': 'WP Kuala Lumpur', 'industry': 'Healthcare', 'employee_count': 5, 'contact_name': 'Dr. Lim', 'notes': 'Dental clinic.'},
        {'company_name': 'PJ Optical Centre', 'website': 'https://pjoptical.my', 'phone': '60176665544', 'email': 'info@pjoptical.my', 'address': '15 Jalan SS2/10, Petaling Jaya', 'city': 'Petaling Jaya', 'state': 'Selangor', 'industry': 'Optical', 'employee_count': 12, 'contact_name': 'John Ng', 'notes': 'Optical retailer.'},
        {'company_name': 'Maju Wholesale Trading', 'website': '', 'phone': '60123334455', 'email': '', 'address': '88 Jalan Meru, Klang', 'city': 'Klang', 'state': 'Selangor', 'industry': 'Wholesale', 'employee_count': 35, 'contact_name': 'Ganesh', 'notes': 'Wholesale distributor.'},
    ],
}

EMAIL_BLACKLIST = {'noreply@', 'no-reply@', 'donotreply@', 'do-not-reply@', 'noreply', 'no-reply'}

# ── Async helpers ──

def _is_demo() -> bool:
    return getattr(cfg, 'DEMO_MODE', True)

def _build_record(lead, source, account_id):
    return {
        'id': str(uuid.uuid4()),
        'account_id': account_id,
        'source': source,
        'company_name': lead['company_name'],
        'website': lead.get('website', ''),
        'phone': lead.get('phone', ''),
        'whatsapp': lead.get('whatsapp', lead.get('phone', '')),
        'email': lead.get('email', ''),
        'address': lead.get('address', ''),
        'city': lead.get('city', ''),
        'state': lead.get('state', ''),
        'industry': lead.get('industry', ''),
        'employee_count': lead.get('employee_count', 0),
        'contact_name': lead.get('contact_name', ''),
        'rating': lead.get('rating', 0),
        'review_count': lead.get('review_count', lead.get('total_reviews', 0)),
        'notes': lead.get('notes', ''),
        'status': 'new',
        'score': 0,
        'is_sample': lead.get('is_sample', False),
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }

# ── Google Maps API (Production) ──

async def scrape_google_maps(query: str, location: str, max_results: int = 50, account_id: str = '00000000-0000-0000-0000-000000000001') -> list[dict]:
    """Scrape leads from Google Maps Places API.
    DEMO_MODE: returns simulated data (10 Malaysian businesses from demo pool)."""
    
    if _is_demo():
        results = DEMO_LEADS_BY_SOURCE.get('google_maps', [])[:min(max_results, 10)]
        return [_build_record(r, 'google_maps', account_id) for r in results]

    # Production: Google Places API
    api_key = getattr(cfg, 'GOOGLE_MAPS_API_KEY', '')
    if not api_key:
        print('[Sales/Scraper] ERROR: GOOGLE_MAPS_API_KEY not configured')
        return []

    query_str = f'{query} {location}'
    results = []

    async with httpx.AsyncClient(timeout=15) as client:
        # Text Search
        params = {'query': query_str, 'key': api_key, 'language': 'en', 'region': 'my'}
        resp = await client.get('https://maps.googleapis.com/maps/api/place/textsearch/json', params=params)
        data = resp.json()

        next_token = data.get('next_page_token')
        all_places = list(data.get('results', []))

        # Paginate
        max_attempts = 5
        attempts = 0
        while next_token and len(all_places) < max_results and attempts < max_attempts:
            await asyncio.sleep(2)  # Google requires delay
            params = {'pagetoken': next_token, 'key': api_key}
            resp = await client.get('https://maps.googleapis.com/maps/api/place/textsearch/json', params=params)
            data = resp.json()
            all_places.extend(data.get('results', []))
            next_token = data.get('next_page_token')
            attempts += 1

        # Filter + get details
        for place in all_places[:max_results]:
            status = place.get('business_status', '')
            if status != 'OPERATIONAL':
                continue

            # Rate limit: 500ms between detail calls
            await asyncio.sleep(0.5)

            place_id = place.get('place_id', '')
            detail_params = {
                'place_id': place_id,
                'key': api_key,
                'fields': 'name,formatted_phone_number,international_phone_number,website,formatted_address,business_status,rating,user_ratings_total,opening_hours',
                'language': 'en',
            }
            detail_resp = await client.get('https://maps.googleapis.com/maps/api/place/details/json', params=detail_params)
            detail = detail_resp.json().get('result', {})

            phone = detail.get('international_phone_number', '') or detail.get('formatted_phone_number', '')
            if not phone:
                continue

            rating = detail.get('rating', 0)
            if rating < 3.0:
                continue

            website = detail.get('website', '')
            email = await _extract_email_from_website(website) if website else ''

            lead = {
                'company_name': detail.get('name', place.get('name', '')),
                'phone': phone,
                'whatsapp': phone.replace(' ', '').replace('-', '').replace('+', ''),
                'email': email,
                'website': website,
                'address': detail.get('formatted_address', place.get('formatted_address', '')),
                'rating': rating,
                'review_count': detail.get('user_ratings_total', 0),
                'source': 'google_maps',
                'source_url': f'https://maps.google.com/?q={detail.get("name", "")}' if detail.get('name') else '',
            }
            results.append(_build_record(lead, 'google_maps', account_id))

    print(f'[Sales/Scraper] Scraped {len(results)} leads from Google Maps (query="{query_str}")')
    return results

async def _extract_email_from_website(url: str) -> str:
    """Extract email from website HTML using regex."""
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            resp = await client.get(url)
            html = resp.text
            emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html))
            for e in emails:
                lower = e.lower()
                if any(lower.startswith(b) for b in EMAIL_BLACKLIST):
                    continue
                if lower.endswith(('.png', '.jpg', '.gif', '.svg')):
                    continue
                return e
    except Exception:
        pass
    return ''

# ── News RSS Scraper (no API key needed) ──

async def scrape_news_leads(keywords: list, max_results: int = 20, account_id: str = '00000000-0000-0000-0000-000000000001') -> list[dict]:
    """Scrape news for company leads using Google News RSS.
    DEMO_MODE: returns simulated data."""
    
    if _is_demo():
        leads = [
            {'company_name': 'PrestoPay Malaysia', 'industry': 'Fintech', 'notes': 'Raised RM5M in Series A'},
            {'company_name': 'MediTech Solutions', 'industry': 'Healthcare', 'notes': 'Expanding across SE Asia'},
            {'company_name': 'EduSmart Learning', 'industry': 'Education', 'notes': 'Secured RM2M for edtech platform'},
            {'company_name': 'ShopEase Malaysia', 'industry': 'Ecommerce', 'notes': 'Launched new marketplace'},
            {'company_name': 'LogiSwift MY', 'industry': 'Logistics', 'notes': 'Expanded fleet to 200 vehicles'},
        ]
        return [_build_record({'company_name': l['company_name'], 'industry': l['industry'], 'notes': l['notes'], 'source_url': 'https://news.google.com/rss/search?q=Malaysia+startup+funding&hl=en-MY&gl=MY&ceid=MY:en'}, 'news', account_id) for l in leads[:max_results]]

    # Production: Google News RSS
    query_str = ' '.join(keywords)
    url = f'https://news.google.com/rss/search?q={query_str}&hl=en-MY&gl=MY&ceid=MY:en'
    
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('.//atom:entry', ns) or root.findall('.//item') or []
            for entry in entries[:max_results]:
                title = (entry.findtext('title') or entry.findtext('atom:title', '', ns)).strip()
                link_elem = entry.find('atom:link', ns) if ns.get('atom') else entry.find('link')
                link = (entry.findtext('link') or (link_elem.get('href') if link_elem is not None else ''))
                pub_date = entry.findtext('pubDate') or entry.findtext('atom:published', '', ns)
                
                # Extract company name from title (simple heuristic: first proper noun phrase)
                company_name = title.split('-')[0].split('|')[0].split(':')[0].strip()
                
                results.append(_build_record({
                    'company_name': company_name,
                    'industry': '',
                    'notes': title,
                    'source_url': link,
                }, 'news', account_id))
    except Exception as e:
        print(f'[Sales/Scraper] News RSS error: {e}')
    
    print(f'[Sales/Scraper] Scraped {len(results)} news leads')
    return results

# ── CSV Upload ──

async def process_csv_upload(file_content: str, account_id: str = '00000000-0000-0000-0000-000000000001') -> list[dict]:
    """Process CSV upload for manual lead import."""
    import csv, io
    reader = csv.DictReader(io.StringIO(file_content))
    
    leads = []
    for row in reader:
        name = row.get('company_name', '').strip()
        phone = row.get('phone', '').strip()
        email = row.get('email', '').strip()
        if not name or (not phone and not email):
            continue
        leads.append(_build_record({
            'company_name': name,
            'contact_name': row.get('contact_name', '').strip(),
            'industry': row.get('industry', '').strip(),
            'phone': phone,
            'whatsapp': row.get('whatsapp', phone),
            'email': email,
            'address': row.get('address', '').strip(),
            'website': row.get('website', '').strip(),
            'notes': row.get('notes', '').strip(),
        }, 'manual_upload', account_id))
    
    return leads

# ── Existing API compatibility ──

async def scrape_leads(source: str = 'google_maps', query: str = '', max_results: int = 10, account_id: str = '00000000-0000-0000-0000-000000000001') -> list[dict]:
    """Legacy compat: scrape from any source."""
    if source == 'google_maps':
        return await scrape_google_maps(query, '', max_results, account_id)
    elif source == 'news':
        return await scrape_news_leads(query.split(), max_results, account_id)
    elif source in DEMO_LEADS_BY_SOURCE and _is_demo():
        return [_build_record(r, source, account_id) for r in DEMO_LEADS_BY_SOURCE[source][:max_results]]
    return []