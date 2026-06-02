# Flowreach

AI-powered B2B sales automation platform for Malaysian businesses. Find qualified leads, send personalised outreach via WhatsApp and email, and track your pipeline — all from one dashboard.

## Features

- **Lead Discovery** — Find qualified B2B prospects from Google Maps, enriched with AI scoring
- **Outreach Automation** — Send personalised WhatsApp and email messages on autopilot
- **Pipeline Tracking** — Manage leads through your sales pipeline with smart notifications
- **Dual Language** — English and Bahasa Malaysia message templates
- **Dashboard** — Real-time stats on outreach campaigns and lead engagement
- **Supabase Backend** — PostgreSQL database with auth, hosted on Supabase
- **Demo Mode** — Test everything without Twilio or email credentials

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Frontend | HTML + Tailwind CSS (CDN) + Vanilla JS |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth + signed cookies |
| Messaging | Twilio WhatsApp API |
| Deployment | Railway |

## Getting Started

### 1. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to the **SQL Editor** and paste the contents of `database/schema.sql`
3. Run the query to create tables and seed demo data
4. Go to **Project Settings > API** and copy:
   - `Project URL` -> `SUPABASE_URL`
   - `anon public` key -> `SUPABASE_KEY`
   - `service_role` key -> `SUPABASE_SERVICE_KEY`

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SECRET_KEY=generate-a-random-secret
DEMO_MODE=true
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=
```

### 3. Install Dependencies

```bash
cd agentflow
pip install -r requirements.txt
```

### 4. Run Locally

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 in your browser.

Login with **demo@flowreach.my** (any password).

### 5. Run Outreach Campaigns

From the sales dashboard, create a campaign and select your leads. In demo mode, it logs simulated outreach without sending real messages.

## Directory Structure

```
agentflow/
├── main.py                  # FastAPI entry point
├── config.py                # App settings
├── requirements.txt
├── railway.toml
├── .env.example
├── README.md
├── database/
│   └── schema.sql           # Supabase tables + seed data
├── routers/
│   ├── auth.py              # Login/logout + session management
│   ├── dashboard.py         # Dashboard page with outreach stats
│   ├── policies.py          # Policy CRUD (legacy)
│   ├── agents.py            # Agent run/status (legacy)
├── services/
│   ├── supabase_client.py   # Supabase client singleton
│   ├── renewal_reminder.py  # Core agent logic
│   ├── whatsapp.py          # Twilio WhatsApp sender
│   └── sheets.py            # Google Sheets sync (placeholder)
├── templates/
│   ├── base.html            # Layout with sidebar
│   ├── login.html           # Login page
│   ├── dashboard.html       # Dashboard with stats + activity
│   ├── policies.html        # Policy table + CRUD modals
│   └── settings.html        # Agency settings form
└── static/
    └── style.css
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase anon/public key | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Yes |
| `SECRET_KEY` | Session cookie signing secret | Yes |
| `DEMO_MODE` | Enable demo mode (no real SMS) | No (default: true) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | For WhatsApp |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | For WhatsApp |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender number | For WhatsApp |

## Deploy to Railway

1. Push code to GitHub
2. Create a new project on [Railway](https://railway.app)
3. Connect your GitHub repo
4. Add all environment variables from `.env.example`
5. Railway auto-detects the build from `railway.toml`
6. Deploy — the app starts at `https://your-app.railway.app`

## License

MIT