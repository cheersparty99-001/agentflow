"""Scraper — web scraper for collecting sales leads.

Uses Google Maps Places API for lead discovery,
news RSS for company intelligence, and CSV upload.
"""

import json, re, uuid, time, asyncio
from datetime import datetime
from typing import Optional
import httpx
import config as cfg

EMAIL_BLACKLIST = {'noreply@', 'no-reply@', 'donotreply@', 'do-not-reply@', 'noreply', 'no-reply'}

# ── Company name cleaning ──

def _clean_company_name(name: str) -> str:
    """Strip taglines/descriptions after dash, comma, or pipe from company names.
    E.g. 'Medindemnity - Medical Malpractice Solutions' -> 'Medindemnity'
         'ABC Sdn Bhd, KL' -> 'ABC Sdn Bhd'
    """
    if not name:
        return name
    # Split on common separators used for taglines
    for sep in [' -- ', ' - ', ' | ', ' / ', ' . ']:
        parts = name.split(sep)
        if len(parts) > 1:
            name = parts[0].strip()
    # Also handle comma-separated extras (but keep 'Sdn Bhd', 'Bhd', 'LLC')
    # Only strip if the comma part is short (location/number, not a suffix)
    if ',' in name:
        parts = [p.strip() for p in name.split(',')]
        if len(parts[0]) > 2:
            suffix = parts[-1].strip()
            if not any(suffix.lower().startswith(s) for s in ['sdn', 'bhd', 'llc', 'inc', 'ltd', 'pte', 'pty']):
                if len(suffix) < 3 or suffix.isdigit():
                    name = parts[0].strip()
    return name.strip()


# ── Async helpers ──

def _build_record(lead, source, account_id):
    # Clean company name
    raw_name = lead.get('company_name', '')
    cleaned = _clean_company_name(raw_name)
    if cleaned != raw_name:
        print(f'  [Clean] \"{raw_name}\" → \"{cleaned}\"')

    # Determine contact method
    email = lead.get('email', '')
    needs_wa = not email
    notes = lead.get('notes', '')
    if needs_wa:
        notes = '[需 WhatsApp] ' + notes if notes else '[需 WhatsApp]'

    return {
        'id': str(uuid.uuid4()),
        'account_id': account_id,
        'source': source,
        'company_name': cleaned,
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
        'notes': notes,
        'status': 'new',
        'score': 0,
        'is_sample': lead.get('is_sample', False),
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }

# ── Google Maps API ──

async def scrape_google_maps(query: str, location: str, max_results: int = 50, account_id: str = '00000000-0000-0000-0000-000000000001') -> list[dict]:
    """Scrape leads from Google Maps Places API.

    Uses Google Places Text Search + Place Details API.
    Fetches phone, website, address, rating for each place.
    Filters out non-OPERATIONAL and < 3.0 rating.
    """
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
    """Scrape news for company leads using Google News RSS."""
    
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
    return []