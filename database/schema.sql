-- Flowreach Database Schema for Supabase
-- Simplified: only auth + account management

CREATE TABLE accounts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  agency_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  language TEXT DEFAULT 'en',
  whatsapp_from TEXT,
  twilio_sid TEXT,
  twilio_token TEXT,
  monthly_fee NUMERIC DEFAULT 0,
  billing_notes TEXT,
  is_active BOOLEAN DEFAULT true,
  plan_notes TEXT,
  -- Sales automation onboarding
  sales_onboarding_status TEXT DEFAULT 'pending',
  sampling_start_date TIMESTAMP,
  sampling_lead_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  role TEXT DEFAULT 'client',
  account_id UUID REFERENCES accounts(id),
  is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed demo account
INSERT INTO accounts (id, agency_name, phone, email)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Agency', '0123456789', 'demo@flowreach.work');

-- Seed admin user
INSERT INTO users (id, email, role, account_id, is_admin)
VALUES ('00000000-0000-0000-0000-000000000002', 'admin@flowreach.work', 'admin', '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (id) DO NOTHING;

-- Seed demo user
INSERT INTO users (id, email, role, account_id, is_admin)
VALUES ('00000000-0000-0000-0000-000000000003', 'demo@flowreach.work', 'client', '00000000-0000-0000-0000-000000000001', false)
ON CONFLICT (id) DO NOTHING;

-- ── Chat Conversations ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id) NOT NULL,
  user_id UUID REFERENCES users(id) NOT NULL,
  title TEXT DEFAULT 'New Conversation',
  messages JSONB DEFAULT '[]'::jsonb,
  is_archived BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ── Follow-up Settings ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS followup_settings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id) NOT NULL,
  is_enabled BOOLEAN DEFAULT true,
  followup_delay_days INTEGER DEFAULT 2,
  max_followups INTEGER DEFAULT 3,
  followup_interval_days INTEGER DEFAULT 3,
  channels TEXT[] DEFAULT ARRAY['email'],
  auto_schedule BOOLEAN DEFAULT true,
  followup_template TEXT DEFAULT '',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(account_id)
);

-- ── Dashboard Banners ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dashboard_banners (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  message TEXT NOT NULL,
  banner_type TEXT DEFAULT 'info',
  is_active BOOLEAN DEFAULT true,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP
);
