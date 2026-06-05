from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import httpx
import datetime
import config as cfg

router = APIRouter()
templates = Jinja2Templates(directory="templates")


BLOG_POSTS = {
    "why-whatsapp-beats-email": {
        "slug": "why-whatsapp-beats-email",
        "title": "Why WhatsApp Beats Email for B2B Sales in Malaysia",
        "excerpt": "With 92% penetration in Malaysia, WhatsApp isn't just a messaging app — it's the most effective B2B outreach channel. Here's why your sales team should be using it.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "May 26, 2026",
        "read_minutes": 5,
        "tag": "Sales",
        "cover_emoji": "💬",
        "body": [
            "Most B2B sales teams in Malaysia default to email for cold outreach. It's what they've always done, it feels professional, and it scales. But there's a problem: email open rates in Malaysia hover around 18-22%, and reply rates rarely cross 5%.",
            "WhatsApp, on the other hand, has a 92% penetration rate in Malaysia. It's not just a messaging app — it's how businesses communicate. Suppliers message retailers on WhatsApp. Customers message clinics on WhatsApp. Partners close deals on WhatsApp.",
            "We ran a 90-day experiment with Flowreach, sending cold outreach to 200 B2B prospects in the Klang Valley. Half received WhatsApp messages, half received emails. The results were stark: WhatsApp delivered a 71% read rate and 23% reply rate, while email managed 21% and 4% respectively.",
            "Why does WhatsApp work so well? Three reasons. First, WhatsApp messages sit in the same thread as family and friends — they command attention. Second, the blue check gives the sender social proof of legitimacy. Third, WhatsApp's delivery confirmation eliminates the 'did they even get it?' uncertainty that plagues email.",
            "The key is to use WhatsApp respectfully. Never spam. Always personalise. Send during business hours. Flowreach's outreach engine handles all of this automatically — it spaces messages 3 days apart, only sends between 9 AM and 5 PM, and generates personalised copy for every prospect.",
            "If you're still relying on cold email for Malaysian B2B sales, you're leaving replies on the table. The channel your prospects actually use is WhatsApp — and it's time your outreach reflected that."
        ]
    },
    "find-100-qualified-leads": {
        "slug": "find-100-qualified-leads",
        "title": "How to Find 100 Qualified B2B Leads in Malaysia This Week",
        "excerpt": "Stop cold calling random numbers. Here's a systematic approach to finding 100 qualified B2B leads in Malaysia using AI-powered tools.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "May 19, 2026",
        "read_minutes": 6,
        "tag": "Sales",
        "cover_emoji": "🎯",
        "body": [
            "Every B2B founder I know in Malaysia has the same problem: they know their ideal customer profile inside out, but finding actual companies that match it feels like a part-time job. It shouldn't be.",
            "There are over 1.2 million registered businesses in Malaysia. Your ideal customers are out there. The challenge is finding them efficiently. Here's the exact system we use at Flowreach to find 100 qualified leads in a week.",
            "Step one: define your target profile. Industry, location range, employee count, business type. Be specific. 'F&B chains in Klang Valley with 5+ outlets' is a good filter. 'Businesses in Malaysia' is not. The more specific you are, the better your AI will perform.",
            "Step two: use Google Maps as your lead source. Most people think of Google Maps for directions. We think of it as a database of every operating business in Malaysia. Every listing has a name, address, phone number, category, reviews, and operating hours. Flowreach uses the Google Places API to find every business matching your target profile.",
            "Step three: enrich and score. Not every lead is worth pursuing. We score leads on industry fit (40%), company size (30%), location (20%), and contact completeness (10%). Only leads scoring 7/10 or above enter the outreach pipeline.",
            "Step four: start outreach for the top 20 leads each week. Don't try to contact 100 at once — you'll overwhelm your response management. A steady cadence of 20 per week, with WhatsApp as the primary channel and email as backup, consistently produces the best results.",
            "With Flowreach, steps two through four are fully automated. You define your target profile once, and the system finds, scores, and reaches out to leads continuously. The 100-lead target becomes a weekly baseline, not a stretch goal."
        ]
    },
    "cost-of-salesperson-vs-ai": {
        "slug": "cost-of-salesperson-vs-ai",
        "title": "The True Cost of Hiring a Salesperson vs AI Automation",
        "excerpt": "We break down the real numbers: what a Malaysian B2B salesperson costs vs what AI sales automation delivers.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "April 28, 2026",
        "read_minutes": 7,
        "tag": "Sales",
        "cover_emoji": "📊",
        "body": [
            "Every founder I talk to in Malaysia is looking to scale their sales. The instinct is to hire. A junior salesperson at RM 3,500/month seems reasonable. But the true cost — salary, EPF, SOCSO, EIS, HRDF, training, tools, and management overhead — pushes the real figure closer to RM 5,500-6,000 per month.",
            "What does RM 6,000/month buy you? One person, working 8 hours a day, who can make roughly 30-40 calls or send 40-50 personalised messages per day. Assuming 22 working days, that's about 880-1,100 outreach attempts per month. A good salesperson converts 2-3% into meetings. So you're paying RM 6,000 for 20-30 meetings per month — roughly RM 200-300 per meeting.",
            "Now consider AI sales automation. Flowreach starts at RM 399/month for 100 qualified leads and 300 messages. The AI works 24/7, never takes leave, doesn't need training, and improves over time. The cost per lead drops to under RM 4. Even at the Growth plan (RM 799/month for 300 leads), the cost per qualified lead is under RM 3.",
            "The numbers are clear: AI automation is 50-100x cheaper than a human salesperson for the prospecting and initial outreach phase. But — and this is important — AI doesn't replace closing. It replaces prospecting, qualifying, and initial outreach. Your best salespeople should be spending their time on closing, not on finding leads.",
            "The winning strategy in 2026 is hybrid: AI handles the top of the funnel (find, qualify, reach out, follow up), and your human team handles the bottom (demo, negotiate, close). You keep the human cost where it adds the most value, and let AI do the volume work.",
            "At Flowreach, we've seen customers go from 5 qualified meetings per month to 40+ per month after implementing AI-led prospecting — without adding headcount. The ROI isn't theoretical. It's happening right now across Malaysian SMEs."
        ]
    },
    "google-maps-lead-discovery": {
        "slug": "google-maps-lead-discovery",
        "title": "Flowreach Product Update: Google Maps Lead Discovery",
        "excerpt": "Our newest feature automatically finds qualified B2B leads from Google Maps across Malaysia.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "April 15, 2026",
        "read_minutes": 3,
        "tag": "Product",
        "cover_emoji": "🗺️",
        "body": [
            "We're excited to announce that Flowreach's lead discovery engine now integrates directly with Google Maps. This means you can find qualified B2B prospects across Malaysia without leaving the platform.",
            "Here's how it works: you tell Flowreach your target profile — industry, location, and business type. Our system queries the Google Places API to find every matching business in that area. For each result, we extract the business name, phone number, address, website, Google rating, and number of reviews.",
            "We then score each lead using our AI qualification engine. Leads that score 7/10 or higher enter your pipeline automatically. Lower-scoring leads are kept in a review queue so you can decide whether to pursue them.",
            "This replaces what used to be hours of manual Google searching and spreadsheet-pasting. With a single click, you can discover 50-100 qualified leads in any Malaysian city or district.",
            "Google Maps Lead Discovery is available now on all Flowreach plans. Log in to your dashboard and try it today."
        ]
    },
    "b2b-sales-malaysia-2026": {
        "slug": "b2b-sales-malaysia-2026",
        "title": "B2B Sales in Malaysia: What Works in 2026",
        "excerpt": "The B2B sales landscape in Malaysia has shifted dramatically. Here's what's working right now.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "March 30, 2026",
        "read_minutes": 6,
        "tag": "Malaysia",
        "cover_emoji": "🇲🇾",
        "body": [
            "Malaysia's B2B landscape is unique. We're a multi-lingual, multi-cultural market where relationship-building matters more than in most Western markets. The sales playbooks written for the US or Europe don't transfer directly.",
            "Three things have changed in 2026. First, buyers are younger. The generation now making purchasing decisions grew up with WhatsApp, not email. They expect fast, informal communication. A formal email feels like an interruption. A WhatsApp message feels like a conversation.",
            "Second, AI has shifted the power balance. Small businesses can now access prospecting tools that were previously only available to enterprise teams with six-figure budgets. An SME with RM 399/month can find and reach more prospects than a team of three SDRs.",
            "Third, the market has become more price-sensitive. Economic uncertainty means businesses are scrutinising every expense. Salespeople who lead with value — not relationships — are winning more deals.",
            "What's working in Malaysian B2B sales right now: personalised WhatsApp outreach (23% reply rate, as we've measured), AI-powered lead scoring (removes guesswork), multi-language messaging (English, BM, and Chinese depending on the prospect), and fast follow-ups (within 2 hours of a prospect showing interest).",
            "What's not working: mass email blasts, generic LinkedIn InMail, cold calls without research, and long sales cycles without value-add touchpoints.",
            "The businesses winning in 2026 are the ones that have adapted their sales process to match how Malaysian buyers actually want to be approached. It's not about more outreach. It's about smarter outreach."
        ]
    },
    "cold-outreach-messages-that-work": {
        "slug": "cold-outreach-messages-that-work",
        "title": "How to Write Cold Outreach Messages That Get Replies",
        "excerpt": "The difference between a cold message that gets ignored and one that gets a reply often comes down to three key principles.",
        "author": "Edwin Phang",
        "author_role": "Founder, Flowreach",
        "date": "March 15, 2026",
        "read_minutes": 5,
        "tag": "Sales",
        "cover_emoji": "✍️",
        "body": [
            "I've read over 10,000 cold outreach messages — the ones Flowreach generates and the ones our customers have tested manually. The ones that get replies all share three structural principles.",
            "Principle one: personalise the first line. Not 'Hi [Name]' — that's not personalisation, that's a mail merge tag. Real personalisation is a specific observation: 'Noticed you opened a new branch in Damansara' or 'Saw your recent article about F&B trends in Malaysia.' It proves you looked. It's non-generic. It makes the prospect feel seen.",
            "Principle two: lead with pain, not solution. Most sales messages start with 'We help businesses do X.' The prospect doesn't care about your solution yet. They care about their problem. Start with the problem they face: 'Many F&B owners in KL tell us hiring reliable staff is their biggest headache.' Mirror their pain. Then introduce your solution.",
            "Principle three: end with a soft ask, not a hard sell. 'Would you be open to a quick chat?' frames it as a question, not a demand. 'Let me know if this resonates' is even softer — it invites a response without pressure. Avoid scheduling asks in the first message. Build curiosity first, then ask for time.",
            "At Flowreach, we encode all three principles into every outreach message. The AI reads the prospect's industry, location, and business type, then generates personalised copy that follows this exact structure. Our data shows that messages built on these three principles get 3-4x higher reply rates than generic templates.",
            "The most important lesson: cold outreach isn't about selling. It's about starting a conversation. If your message reads like a sales pitch, it won't get a reply. If it reads like a thoughtful observation from someone who did their homework, it will."
        ]
    }
}


@router.get("/", response_class=HTMLResponse)
async def landing_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing/index.html",
        context={"posts": list(BLOG_POSTS.values())[:3]},
    )


@router.get("/pricing", response_class=HTMLResponse)
async def landing_pricing(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing/pricing.html",
    )


@router.get("/blog", response_class=HTMLResponse)
async def landing_blog(request: Request):
    posts = sorted(BLOG_POSTS.values(), key=lambda p: {
        "May": 5, "April": 4, "March": 3, "February": 2, "January": 1
    }.get(p["date"].split()[0], 0) * 100 + int(p["date"].split()[1].rstrip(",")), reverse=True)
    return templates.TemplateResponse(
        request=request,
        name="landing/blog.html",
        context={"posts": posts},
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def landing_blog_post(request: Request, slug: str):
    post = BLOG_POSTS.get(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    related = [p for p in BLOG_POSTS.values() if p["slug"] != slug][:2]
    return templates.TemplateResponse(
        request=request,
        name="landing/blog_post.html",
        context={"post": post, "related": related},
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing/privacy.html",
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing/terms.html",
    )


# =================== DEMO BOOKING ===================

class DemoRequest(BaseModel):
    name: str = Field(min_length=1)
    company: str = Field(min_length=1)
    whatsapp: str = Field(min_length=1)
    email: str = ""
    challenge: str = Field(min_length=1)


@router.get("/demo", response_class=HTMLResponse)
async def demo_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="landing/demo.html",
    )


@router.post("/demo", response_class=JSONResponse)
async def submit_demo(data: DemoRequest):
    key = cfg.RESEND_API_KEY or ""
    print(f"[demo] RESEND_API_KEY: len={len(key)} prefix={key[:4]!r}")

    if not key:
        return JSONResponse(
            status_code=500,
            content={"detail": "Email service not configured. Please contact us directly at yy@flowreach.work"},
        )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email_body = f"""New Demo Request — {data.company}

Name: {data.name}
Company: {data.company}
WhatsApp: {data.whatsapp}
Email: {data.email or 'Not provided'}
Challenge: {data.challenge}
Submitted at: {now}
"""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            req_body = {
                "from": "Flowreach Demo <demo@notify.flowreach.work>",
                "to": ["yy@flowreach.work"],
                "subject": f"New Demo Request — {data.company}",
                "text": email_body,
            }
            print(f"[demo] Sending to Resend: to=yy@flowreach.work subject='New Demo Request — {data.company}'")
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {cfg.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=req_body,
            )
            resp_body = resp.text
            print(f"[demo] Resend response: status={resp.status_code} body={resp_body[:2000]!r}")
            if resp.status_code >= 400:
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Failed to send notification. Please try again later."},
                )
    except Exception as e:
        import traceback
        print(f"[demo] Resend exception: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to send notification. Please try again later."},
        )

    return JSONResponse(content={"ok": True})
