-- AgentFlow Database Schema for Supabase

CREATE TABLE accounts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  agency_name TEXT NOT NULL,
  phone TEXT,
  email TEXT,
  business_hours TEXT DEFAULT 'Mon-Fri 9AM-6PM, Sat 9AM-1PM',
  language TEXT DEFAULT 'en',
  whatsapp_from TEXT,
  twilio_sid TEXT,
  twilio_token TEXT,
  modules JSONB DEFAULT '{"renewal_reminder": true, "enquiry_handler": false, "quotation_formatter": false, "claims_tracker": false}',
  reminder_days JSONB DEFAULT '[30, 14, 7]',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  role TEXT DEFAULT 'client',
  account_id UUID REFERENCES accounts(id),
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE policies (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  customer_name TEXT NOT NULL,
  phone TEXT NOT NULL,
  car_plate TEXT NOT NULL,
  expiry_date DATE NOT NULL,
  ncd TEXT,
  status TEXT DEFAULT 'Active',
  reminder_30_sent DATE,
  reminder_14_sent DATE,
  reminder_7_sent DATE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE agent_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  module TEXT NOT NULL,
  action TEXT NOT NULL,
  policy_id UUID REFERENCES policies(id),
  status TEXT,
  message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed demo account
INSERT INTO accounts (id, agency_name, phone, email)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Insurance Agency', '0123456789', 'demo@agentflow.my');

-- Seed demo policies
INSERT INTO policies (account_id, customer_name, phone, car_plate, expiry_date, ncd, status)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'Ahmad Razif', '60123456789', 'WXY 1234', CURRENT_DATE + 30, '25%', 'Active'),
  ('00000000-0000-0000-0000-000000000001', 'Tan Wei Ming', '60198765432', 'JHB 5678', CURRENT_DATE + 14, '38%', 'Active'),
  ('00000000-0000-0000-0000-000000000001', 'Priya Nair', '60112223334', 'PEN 9012', CURRENT_DATE + 7, '55%', 'Active'),
  ('00000000-0000-0000-0000-000000000001', 'Lim Chee Keong', '60167778889', 'KLM 3456', CURRENT_DATE + 45, '0%', 'Active'),
  ('00000000-0000-0000-0000-000000000001', 'Nurul Ain', '60134445556', 'SGR 7890', CURRENT_DATE + 7, '25%', 'Active');

-- 险种类型
CREATE TABLE IF NOT EXISTS insurance_types (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true
);
INSERT INTO insurance_types (code, name) VALUES
  ('motor', 'Motor Insurance'), ('medical', 'Medical Insurance'),
  ('fire', 'Fire Insurance'), ('travel', 'Travel Insurance')
ON CONFLICT DO NOTHING;

ALTER TABLE policies ADD COLUMN IF NOT EXISTS insurance_type TEXT DEFAULT 'motor';
ALTER TABLE policies ADD COLUMN IF NOT EXISTS policy_number TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS insurer TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS sum_insured NUMERIC;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS premium NUMERIC;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS ic_number TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS car_make TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS car_model TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS car_year INTEGER;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS coverage_type TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS dependents INTEGER DEFAULT 0;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS property_address TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS property_type TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS destination TEXT;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS travel_start DATE;
ALTER TABLE policies ADD COLUMN IF NOT EXISTS travel_end DATE;

CREATE TABLE IF NOT EXISTS modules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  module_code TEXT NOT NULL,
  is_enabled BOOLEAN DEFAULT false,
  config JSONB DEFAULT '{}',
  updated_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS monthly_fee NUMERIC DEFAULT 0;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS billing_notes TEXT;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS plan_notes TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false;

INSERT INTO modules (account_id, module_code, is_enabled) VALUES
  ('00000000-0000-0000-0000-000000000001', 'renewal_reminder', true),
  ('00000000-0000-0000-0000-000000000001', 'enquiry_handler', false),
  ('00000000-0000-0000-0000-000000000001', 'quotation_formatter', false),
  ('00000000-0000-0000-0000-000000000001', 'claims_tracker', false),
  ('00000000-0000-0000-0000-000000000001', 'birthday_greeting', false),
  ('00000000-0000-0000-0000-000000000001', 'annual_report', false)
ON CONFLICT DO NOTHING;

-- Customer Telegram bot link table
CREATE TABLE IF NOT EXISTS customer_bot_links (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  phone TEXT NOT NULL,
  chat_id BIGINT NOT NULL,
  customer_name TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE policies ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;