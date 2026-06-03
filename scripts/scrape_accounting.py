"""Scrape accounting firm leads for Flowreach (KL + Selangor)."""
import os, sys, json, asyncio, uuid
from datetime import datetime
sys.path.insert(0, '/root/agentflow')
os.environ['DEMO_MODE'] = 'false'

import config as cfg
from services.sales.scraper import scrape_google_maps, _extract_email_from_website, _clean_company_name
from services.supabase_client import get_supabase

ACCOUNT_ID = '00000000-0000-0000-0000-000000000001'
FLOWREACH_ID = 'b3000000-0000-0000-0000-000000000003'
sb = get_supabase()

QUERIES = [
    ("accounting firm", "Kuala Lumpur", 8),
    ("audit firm", "Petaling Jaya", 8),
    ("bookkeeping services", "Selangor", 8),
    ("chartered accountant", "Kuala Lumpur", 8),
    ("tax agent", "Selangor", 8),
]

async def main():
    all_leads = []
    seen_phones = set()

    for query, location, limit in QUERIES:
        print(f'\n[Scrape] "{query} {location}"...')
        leads = await scrape_google_maps(query, location, max_results=limit, account_id=ACCOUNT_ID)
        for l in leads:
            phone = l.get('phone', '')
            if phone in seen_phones:
                continue
            seen_phones.add(phone)
            raw = l.get('company_name', '')
            cleaned = _clean_company_name(raw)
            l['company_name'] = cleaned
            l['source_query'] = f'{query} {location}'
            all_leads.append(l)
        print(f'  Got {len(leads)}, total unique: {len(all_leads)}')

    print(f'\n{"="*60}')
    print(f'Total unique leads scraped: {len(all_leads)}')
    print(f'{"="*60}')

    # Email re-extraction
    print('\n[Email Re-Extraction]')
    email_count = 0
    for i, l in enumerate(all_leads):
        website = l.get('website', '')
        if website and not l.get('email'):
            try:
                email = await _extract_email_from_website(website)
                if email:
                    all_leads[i]['email'] = email
                    email_count += 1
                    print(f'  [Email] {l["company_name"]}: {email}')
            except:
                pass
    print(f'  Emails found via re-extraction: {email_count}')

    # DB Insert
    print(f'\n[DB Insert] Writing {len(all_leads)} leads to Supabase...')
    inserted = 0
    for l in all_leads:
        record = {
            'id': str(uuid.uuid4()),
            'account_id': ACCOUNT_ID,
            'business_id': FLOWREACH_ID,
            'company_name': l['company_name'],
            'industry': 'Professional Services',
            'phone': l.get('phone', ''),
            'whatsapp': l.get('phone', '').replace(' ', '').replace('-', '').replace('+', ''),
            'email': l.get('email', ''),
            'website': l.get('website', ''),
            'address': l.get('address', ''),
            'source': 'google_maps',
            'source_url': l.get('source_url', ''),
            'status': 'new',
            'score': 0,
            'is_sample': False,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
        }
        try:
            sb.table('leads').insert(record).execute()
            inserted += 1
        except Exception as e:
            print(f'  [ERROR] {l["company_name"]}: {e}')
    print(f'  Inserted: {inserted}/{len(all_leads)}')

    # Results table
    print(f'\n{"="*110}')
    print('FLOWREACH - ACCOUNTING FIRM LEADS (KL + Selangor)')
    print(f'{"="*110}')
    header = f'{"#":>3} {"Company":<32} {"Industry":<24} {"Phone":<20} {"Email":>5} {"Channel":<12}'
    print(header)
    print('-' * 110)

    for i, l in enumerate(all_leads, 1):
        has_e = 'YES' if l.get('email') else 'NO'
        channel = 'Email' if l.get('email') else 'WhatsApp'
        print(f'{i:>3} {l["company_name"][:31]:<32} {"Professional Services":<24} {l.get("phone",""):<20} {has_e:>5} {channel:<12}')

    print('-' * 110)

    with_email = [l for l in all_leads if l.get('email')]
    phone_only = [l for l in all_leads if not l.get('email')]

    print()
    print('=' * 50)
    print('  VERIFICATION SUMMARY')
    print(f'  Total leads found:   {len(all_leads)}')
    print(f'  With email:          {len(with_email)}  <- Email channel ready')
    print(f'  Phone only (WA):     {len(phone_only)}  <- WhatsApp needed')
    print(f'  Email coverage:      {len(with_email)/len(all_leads)*100:.0f}%')
    print('=' * 50)

    # Save
    with open('/root/agentflow/scripts/accounting_leads.json', 'w') as f:
        json.dump(all_leads, f, indent=2, default=str)
    print(f'\nSaved to accounting_leads.json')

asyncio.run(main())
