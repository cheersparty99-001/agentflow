"""Improved email extractor for real_leads.json missing emails."""
import os, sys, json, asyncio, re
sys.path.insert(0, '/root/agentflow')

import httpx

SOCIAL_DOMAINS = {'instagram.com', 'facebook.com', 'fb.com', 'linkedin.com', 'tiktok.com', 'twitter.com', 'x.com', 'youtube.com'}

async def extract_email(url: str, timeout=8) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            resp = await client.get(url)
            emails = _find_emails(resp.text)
            if emails:
                return emails[0]
            for path in ['/contact', '/contact-us', '/about', '/about-us', '/contactus']:
                try:
                    r2 = await client.get(url.rstrip('/') + path, timeout=5)
                    if r2.status_code == 200:
                        emails = _find_emails(r2.text)
                        if emails:
                            return emails[0]
                except Exception:
                    pass
    except Exception:
        pass
    return ''

def _find_emails(html: str) -> list:
    found = set()
    for match in re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|my|com\.my|org|net|edu|info|biz)', html, re.IGNORECASE):
        email = match.strip().lower()
        if any(ext in email for ext in ['.png', '.jpg', '.gif', '.svg', '.css', '.js']):
            continue
        if email.startswith(('noreply@', 'no-reply@', 'donotreply@')):
            continue
        if 'example.com' in email or 'your-email' in email:
            continue
        if len(email) > 50:
            continue
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            continue
        found.add(email)
    return sorted(found)

async def main():
    with open('scripts/real_leads.json') as f:
        data = json.load(f)
    
    qualified = data['qualified']
    targets = [(i, l) for i, l in enumerate(qualified) if l.get('website') and not l.get('email')]
    
    real_websites = []
    for i, l in targets:
        domain = l['website'].lower()
        if any(s in domain for s in SOCIAL_DOMAINS):
            print(f'  SKIP (social): {l["company_name"]} - {l["website"]}')
            continue
        real_websites.append((i, l))
    
    print(f'\nReal websites to scan: {len(real_websites)}/{len(targets)}')
    print()
    
    found = 0
    for i, l in real_websites:
        url = l['website']
        email = await extract_email(url)
        if email:
            qualified[i]['email'] = email
            found += 1
            print(f'  OK  {l["company_name"]} -> {email}')
        else:
            print(f'  NO  {l["company_name"]} ({url})')
    
    with_email = [l for l in qualified if l.get('email')]
    print(f'\nFound {found} new emails')
    print(f'Total with email now: {len(with_email)}/{len(qualified)}')
    
    data['qualified'] = qualified
    data['stats']['with_email'] = len(with_email)
    with open('scripts/real_leads.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print('Saved updated data to scripts/real_leads.json')

if __name__ == '__main__':
    asyncio.run(main())
