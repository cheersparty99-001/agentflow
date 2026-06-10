"""Scrape real Google Maps leads, score them, and update app state.
Run with: python3 -c "exec(open('/root/agentflow/scripts/reset_and_scrape.py').read())"
"""
import os, sys, json, asyncio
from collections import Counter
sys.path.insert(0, '/root/agentflow')

# Force production mode for real Google Maps API calls

import config as cfg
from services.sales.scraper import scrape_google_maps
from services.sales.scraper import _extract_email_from_website as extract_email_from_website
from services.sales.qualifier import qualify_leads

DEMO_ACCOUNT = '00000000-0000-0000-0000-000000000001'

# Industry mapping: Google Maps types → qualifier industries
INDUSTRY_MAP = {
    'restaurant': 'Hospitality', 'food': 'Hospitality', 'cafe': 'Hospitality',
    'retail': 'Retail', 'store': 'Retail', 'shop': 'Retail', 'clothing': 'Retail', 'supermarket': 'Retail',
    'accounting': 'Professional Services', 'legal': 'Professional Services', 'law': 'Professional Services', 'training': 'Professional Services', 'consulting': 'Professional Services',
    'wholesale': 'Logistics', 'supplier': 'Manufacturing', 'distributor': 'Logistics',
    'manufacturing': 'Manufacturing', 'factory': 'Manufacturing',
    'logistics': 'Logistics', 'transport': 'Logistics', 'warehouse': 'Logistics',
    'technology': 'Technology', 'software': 'Technology', 'it': 'Technology',
    'education': 'Education', 'school': 'Education', 'training': 'Education',
    'automotive': 'Automotive', 'car': 'Automotive', 'workshop': 'Automotive',
    'construction': 'Construction', 'contractor': 'Construction',
    'real_estate': 'Real Estate', 'property': 'Real Estate',
    'energy': 'Energy', 'solar': 'Energy',
}

def map_industry(company_name, address, query):
    """Map company name/address/query to an industry for scoring."""
    text = (company_name + ' ' + address + ' ' + query).lower()
    for keyword, industry in INDUSTRY_MAP.items():
        if keyword in text:
            return industry
    return 'Other'

async def scrape_and_score():
    # ── Boleh AI target: Malaysian SMEs that need AI/automation ──
    # Removed insurance/optical (old insurance project leftovers)
    queries = [
        ("restaurant", "Kuala Lumpur", 10),
        ("retail shop", "Petaling Jaya", 10),
        ("cafe", "Kuala Lumpur", 10),
        ("accounting firm", "Kuala Lumpur", 10),
        ("training centre", "Petaling Jaya", 10),
    ]
    
    all_leads = []
    for query, location, limit in queries:
        print(f'\n[Scrape] Query: "{query} {location}" ({limit})')
        try:
            leads = await scrape_google_maps(query, location, max_results=limit, account_id=DEMO_ACCOUNT)
            # Map industries
            for l in leads:
                l['industry'] = map_industry(l.get('company_name',''), l.get('address',''), query)
                l['contact_name'] = ''
                l['source'] = 'google_maps'
                l['source_query'] = f'{query} {location}'
            all_leads.extend(leads)
            print(f'  → Got {len(leads)} leads')
        except Exception as e:
            print(f'  → ERROR: {e}')
    
    print(f'\n=== Total raw leads scraped: {len(all_leads)} ===')
    
    # Extract emails from websites
    print('\n[Email Extraction]')
    email_count = 0
    for i, l in enumerate(all_leads):
        website = l.get('website', '')
        if website and not l.get('email'):
            try:
                email = await extract_email_from_website(website)
                if email:
                    all_leads[i]['email'] = email
                    email_count += 1
                    print(f'  ✓ {l["company_name"]}: {email}')
            except:
                pass
    
    print(f'\nEmails found: {email_count}/{len(all_leads)}')
    
    # Score all leads — use Google Maps-friendly scoring
    print('\n[Scoring]')
    
    def simple_score(lead):
        """Score 1-10 based on available Google Maps data."""
        s = 3  # base: has Google Maps listing
        s += 1 if lead.get('phone') else 0
        s += 1 if lead.get('website') else 0
        s += 2 if lead.get('email') else 0
        rating = lead.get('rating', 0)
        if rating >= 4.5: s += 2
        elif rating >= 4.0: s += 1
        s += 1 if lead.get('address') else 0
        return min(s, 10)
    
    for l in all_leads:
        l['score'] = simple_score(l)
        l['status'] = 'cold'
    
    # Filter: score >= 7
    qualified = [l for l in all_leads if l['score'] >= 7]
    
    print(f'\n=== RESULTS ===')
    print(f'Total leads scraped: {len(all_leads)}')
    print(f'Qualified (score >= 55): {len(qualified)}')
    
    # By industry
    from collections import Counter
    industries = Counter(l.get('industry', 'Other') for l in qualified)
    print(f'\n--- By Industry ---')
    for ind, count in industries.most_common():
        print(f'  {ind}: {count}')
    
# With/without email
    with_email = [l for l in qualified if l.get('email')]
    without_email = [l for l in qualified if not l.get('email')]
    print(f'\n--- Contact Info ---')
    print(f'  With email: {len(with_email)}')
    print(f'  Phone only (需 WhatsApp): {len(without_email)}')

    # Full listing
    print(f'\n--- Qualified Leads List ---')
    print(f'{"#":>3} {"Company":<30} {"Industry":<18} {"Score":>5} {"Email":<35} {"WA":>3} {"Phone":<20}')
    print('-' * 120)
    for i, l in enumerate(qualified, 1):
        email = l.get('email', '')[:35] if l.get('email') else '(none)'
        phone = l.get('phone', '')[:20]
        needs_wa = 'X' if not l.get('email') else ''
        print(f'{i:>3} {l["company_name"][:29]:<30} {l.get("industry","Other")[:17]:<18} {l["score"]:>5} {email:<35} {needs_wa:>3} {phone:<20}')
    
    # Save to JSON for later use
    output = {
        'all_leads': all_leads,
        'qualified': qualified,
        'stats': {
            'total_scraped': len(all_leads),
            'qualified': len(qualified),
            'with_email': len(with_email),
            'phone_only': len(without_email),
            'industries': dict(industries.most_common()),
        }
    }
    with open('/root/agentflow/scripts/real_leads.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f'\nSaved to /root/agentflow/scripts/real_leads.json')
    
    return output

if __name__ == '__main__':
    result = asyncio.run(scrape_and_score())