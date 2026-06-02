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
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Agency', '0123456789', 'demo@agentflow.my');

-- Seed admin user
INSERT INTO users (id, email, role, account_id, is_admin)
VALUES ('00000000-0000-0000-0000-000000000002', 'admin@agentflow.my', 'admin', '00000000-0000-0000-0000-000000000001', true)
ON CONFLICT (id) DO NOTHING;

-- Seed demo user
INSERT INTO users (id, email, role, account_id, is_admin)
VALUES ('00000000-0000-0000-0000-000000000003', 'demo@agentflow.my', 'client', '00000000-0000-0000-0000-000000000001', false)
ON CONFLICT (id) DO NOTHING;
