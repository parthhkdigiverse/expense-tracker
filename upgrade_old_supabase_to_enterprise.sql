-- ==============================================================================
-- 🚀 UPGRADE SCRIPT: OLD SUPABASE DB -> EXPS TRACKER ENTERPRISE (V2)
-- Safely applies all new table structures, columns, and permissions to an 
-- existing personal tracker database without deleting existing data.
-- ==============================================================================
-- INSTRUCTIONS: Open the Supabase SQL Editor, paste this entire file, and click RUN.
-- ==============================================================================

-- 1. Enable secure hashing for enterprise PINs
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Protect against 42501 Permission Denied errors out of the box
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;

-- ==============================================================================
-- PART 1: SAFELY UPGRADE EXISTING PERSONAL TABLES
-- ==============================================================================
DO $$
BEGIN
    -- ---------------------------------------------------------
    -- EXPENSES: Add new columns if missing
    -- ---------------------------------------------------------
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='expenses' AND column_name='type') THEN
        ALTER TABLE public.expenses ADD COLUMN type text DEFAULT 'expense' CHECK (type IN ('income', 'expense'));
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='expenses' AND column_name='method') THEN
        ALTER TABLE public.expenses ADD COLUMN method text;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='expenses' AND column_name='bank_account_id') THEN
        ALTER TABLE public.expenses ADD COLUMN bank_account_id uuid;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='expenses' AND column_name='receipt_url') THEN
        ALTER TABLE public.expenses ADD COLUMN receipt_url text;
    END IF;

    -- Add foreign key constraint safely
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name='expenses_bank_account_id_fkey'
    ) AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='bank_accounts') THEN
        ALTER TABLE public.expenses ADD CONSTRAINT expenses_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id) ON DELETE SET NULL;
    END IF;

    -- ---------------------------------------------------------
    -- DEBTS: Rename total_amount to amount if it exists
    -- ---------------------------------------------------------
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='debts' AND column_name='total_amount') THEN
        ALTER TABLE public.debts RENAME COLUMN total_amount TO amount;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='debts' AND column_name='transaction_date') THEN
        ALTER TABLE public.debts ADD COLUMN transaction_date date;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='debts' AND column_name='bank_account_id') THEN
        ALTER TABLE public.debts ADD COLUMN bank_account_id uuid;
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='bank_accounts') THEN
             ALTER TABLE public.debts ADD CONSTRAINT debts_bank_account_id_fkey FOREIGN KEY (bank_account_id) REFERENCES public.bank_accounts(id) ON DELETE SET NULL;
        END IF;
    END IF;

    -- ---------------------------------------------------------
    -- INCOMES: Migrate old 'incomes' table to 'expenses' with type='income'
    -- ---------------------------------------------------------
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='incomes') THEN
        -- Insert rows from incomes table into the newly structured expenses table
        INSERT INTO public.expenses (user_id, amount, type, category, date, description, created_at)
        SELECT user_id, amount, 'income', source, date, description, created_at
        FROM public.incomes;
        
        -- Rename incomes table to preserve data safely just in case it's needed for rollback
        ALTER TABLE public.incomes RENAME TO incomes_archived;
    END IF;
END
$$;


-- ==============================================================================
-- PART 2: CREATE NEW MISSING CORE TABLES
-- ==============================================================================

-- Storage Buckets for Avatars and Receipts (Safe to run multiple times)
INSERT INTO storage.buckets (id, name, public) VALUES ('avatars', 'avatars', true) ON CONFLICT (id) DO NOTHING;
INSERT INTO storage.buckets (id, name, public) VALUES ('receipts', 'receipts', true) ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "Avatar images are publicly accessible" ON storage.objects;
DROP POLICY IF EXISTS "Anyone can upload an avatar" ON storage.objects;
CREATE POLICY "Avatar images are publicly accessible" ON storage.objects FOR SELECT USING (bucket_id = 'avatars');
CREATE POLICY "Anyone can upload an avatar" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'avatars');


-- recurring_expenses (Personal)
CREATE TABLE IF NOT EXISTS public.recurring_expenses (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount          numeric(15,2) NOT NULL DEFAULT 0,
    type            text DEFAULT 'expense' CHECK (type IN ('income', 'expense')),
    category        text NOT NULL,
    frequency       text NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
    next_due_date   date NOT NULL,
    description     text,
    method          text,
    status          text DEFAULT 'active' CHECK (status IN ('active', 'paused', 'cancelled')),
    bank_account_id uuid REFERENCES public.bank_accounts(id) ON DELETE SET NULL,
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.recurring_expenses ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.recurring_expenses TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "recurring_all" ON public.recurring_expenses;
CREATE POLICY "recurring_all" ON public.recurring_expenses FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Ensure profiles is fully configured (if missing policy or trigger)
CREATE TABLE IF NOT EXISTS public.profiles (
    id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email        text UNIQUE NOT NULL,
    username     text UNIQUE,
    full_name    text,
    avatar_url   text,
    budget       numeric(15,2) DEFAULT 0.00,
    currency     text DEFAULT '₹',
    created_at   timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.profiles TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "profiles_select" ON public.profiles;
DROP POLICY IF EXISTS "profiles_insert" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update" ON public.profiles;
DROP POLICY IF EXISTS "profiles_delete" ON public.profiles;

CREATE POLICY "profiles_select" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "profiles_insert" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_delete" ON public.profiles FOR DELETE USING (auth.uid() = id);


-- ==============================================================================
-- PART 3: ENTERPRISE (BUSINESS) TABLES AND POLICIES
-- ==============================================================================

-- 1. ent_organizations (The central hub for a business)
CREATE TABLE IF NOT EXISTS public.ent_organizations (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_organizations ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_organizations TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_orgs_select" ON public.ent_organizations;
DROP POLICY IF EXISTS "ent_orgs_insert" ON public.ent_organizations;
CREATE POLICY "ent_orgs_select" ON public.ent_organizations FOR SELECT USING (true);
CREATE POLICY "ent_orgs_insert" ON public.ent_organizations FOR INSERT WITH CHECK (true);


-- 2. ent_members (The strict gateway + Double Login PIN System)
CREATE TABLE IF NOT EXISTS public.ent_members (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role            text DEFAULT 'member',
    pin_hash        text,
    created_at      timestamptz DEFAULT now() NOT NULL,
    UNIQUE (organization_id, user_id)
);
ALTER TABLE public.ent_members ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_members TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_members_select" ON public.ent_members;
DROP POLICY IF EXISTS "ent_members_insert" ON public.ent_members;
DROP POLICY IF EXISTS "ent_members_update" ON public.ent_members;
DROP POLICY IF EXISTS "ent_members_delete" ON public.ent_members;

CREATE POLICY "ent_members_select" ON public.ent_members FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "ent_members_insert" ON public.ent_members FOR INSERT WITH CHECK (true);
CREATE POLICY "ent_members_update" ON public.ent_members FOR UPDATE USING (user_id = auth.uid() OR role = 'owner');
CREATE POLICY "ent_members_delete" ON public.ent_members FOR DELETE USING (user_id = auth.uid() OR role = 'owner');


-- 2a. Double Login RPC: Set Business PIN
CREATE OR REPLACE FUNCTION public.setup_business_pin(p_user_id uuid, p_business_name text, p_pin text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_org_id uuid;
BEGIN
    SELECT id INTO v_org_id FROM public.ent_organizations WHERE name = p_business_name LIMIT 1;
    IF v_org_id IS NULL THEN
        INSERT INTO public.ent_organizations (name) VALUES (p_business_name) RETURNING id INTO v_org_id;
    END IF;

    IF EXISTS (SELECT 1 FROM public.ent_members WHERE user_id = p_user_id AND organization_id = v_org_id) THEN
        UPDATE public.ent_members SET pin_hash = crypt(p_pin, gen_salt('bf')) WHERE user_id = p_user_id AND organization_id = v_org_id;
        RETURN true;
    ELSE
        INSERT INTO public.ent_members (organization_id, user_id, role, pin_hash) VALUES (v_org_id, p_user_id, 'owner', crypt(p_pin, gen_salt('bf')));
        RETURN true;
    END IF;
EXCEPTION WHEN OTHERS THEN RETURN false;
END;
$$;
GRANT EXECUTE ON FUNCTION public.setup_business_pin TO anon, authenticated, service_role;


-- 2b. Double Login RPC: Verify Business PIN
CREATE OR REPLACE FUNCTION public.verify_business_pin(p_user_id uuid, p_business_name text, p_pin text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE v_stored_hash text;
BEGIN
    SELECT m.pin_hash INTO v_stored_hash 
    FROM public.ent_members m
    JOIN public.ent_organizations o ON m.organization_id = o.id
    WHERE m.user_id = p_user_id AND o.name = p_business_name;
    
    IF v_stored_hash IS NULL THEN RETURN false; END IF;
    RETURN v_stored_hash = crypt(p_pin, v_stored_hash);
END;
$$;
GRANT EXECUTE ON FUNCTION public.verify_business_pin TO anon, authenticated, service_role;


-- 3. enterprise_bank_accounts
CREATE TABLE IF NOT EXISTS public.enterprise_bank_accounts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    business_name   text NOT NULL,
    bank_name       text NOT NULL,
    account_number  text,
    ifsc_code       text,
    opening_balance numeric(15,2) DEFAULT 0.00,
    account_type    text DEFAULT 'Current' CHECK (account_type IN ('Current', 'CC/OD')),
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.enterprise_bank_accounts ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.enterprise_bank_accounts TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_banks_all" ON public.enterprise_bank_accounts;
CREATE POLICY "ent_banks_all" ON public.enterprise_bank_accounts FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);


-- 4. ent_revenue
CREATE TABLE IF NOT EXISTS public.ent_revenue (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    amount          numeric(15,2) NOT NULL DEFAULT 0,
    date            date NOT NULL DEFAULT CURRENT_DATE,
    status          text DEFAULT 'completed',
    taken_by        text,  
    method          text,
    bank_account_id uuid REFERENCES public.enterprise_bank_accounts(id) ON DELETE SET NULL,
    narrative       text,
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_revenue ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_revenue TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_revenue: org access" ON public.ent_revenue;
CREATE POLICY "ent_revenue: org access" ON public.ent_revenue FOR ALL
    USING  (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_revenue.organization_id AND m.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_revenue.organization_id AND m.user_id = auth.uid()));


-- 5. ent_expenses
CREATE TABLE IF NOT EXISTS public.ent_expenses (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    amount          numeric(15,2) NOT NULL DEFAULT 0,
    date            date NOT NULL DEFAULT CURRENT_DATE,
    category        text NOT NULL,
    taken_by        text,
    method          text,
    bank_account_id uuid REFERENCES public.enterprise_bank_accounts(id) ON DELETE SET NULL,
    narrative       text,
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_expenses ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_expenses TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_expenses: org access" ON public.ent_expenses;
CREATE POLICY "ent_expenses: org access" ON public.ent_expenses FOR ALL
    USING  (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_expenses.organization_id AND m.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_expenses.organization_id AND m.user_id = auth.uid()));


-- 6. ent_investments
CREATE TABLE IF NOT EXISTS public.ent_investments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    amount          numeric(15,2) NOT NULL DEFAULT 0,
    date            date NOT NULL DEFAULT CURRENT_DATE,
    type            text DEFAULT 'investment',
    taken_by        text,
    narrative       text,
    source          text,    
    description     text,    
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_investments ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_investments TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_investments: org access" ON public.ent_investments;
CREATE POLICY "ent_investments: org access" ON public.ent_investments FOR ALL
    USING  (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_investments.organization_id AND m.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_investments.organization_id AND m.user_id = auth.uid()));


-- 7. ent_holding_payments
CREATE TABLE IF NOT EXISTS public.ent_holding_payments (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    created_by       uuid NOT NULL REFERENCES auth.users(id),
    name             text NOT NULL,
    type             text DEFAULT 'receivable' CHECK (type IN ('receivable', 'payable')),
    amount           numeric(15,2) NOT NULL DEFAULT 0,
    paid_amount      numeric(15,2) DEFAULT 0,
    remaining_amount numeric(15,2),
    expected_date    date,
    mobile_no        text,
    narrative        text,
    status           text DEFAULT 'pending' CHECK (status IN ('pending', 'partial', 'settled')),
    created_at       timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_holding_payments ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_holding_payments TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_holding: org access" ON public.ent_holding_payments;
CREATE POLICY "ent_holding: org access" ON public.ent_holding_payments FOR ALL
    USING  (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_holding_payments.organization_id AND m.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_holding_payments.organization_id AND m.user_id = auth.uid()));


-- 8. ent_staff
CREATE TABLE IF NOT EXISTS public.ent_staff (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    name            text NOT NULL,
    designation     text,
    created_at      timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.ent_staff ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE public.ent_staff TO anon, authenticated, service_role;

DROP POLICY IF EXISTS "ent_staff: org access" ON public.ent_staff;
CREATE POLICY "ent_staff: org access" ON public.ent_staff FOR ALL
    USING  (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_staff.organization_id AND m.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM public.ent_members m WHERE m.organization_id = ent_staff.organization_id AND m.user_id = auth.uid()));


-- ==============================================================================
-- PART 4: TRIGGERS (Auto-Create Profiles)
-- ==============================================================================
-- Ensures that whenever a user signs up with Supabase Auth, their `profiles` row is created.

CREATE OR REPLACE FUNCTION public.handle_new_user() 
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, email, username, full_name, avatar_url)
  VALUES (
    new.id, 
    new.email, 
    new.raw_user_meta_data->>'username', 
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url'
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();


-- FORCE RELOAD POSTGREST CACHE
NOTIFY pgrst, 'reload schema';

-- DONE! Your existing Supabase Database is now fully upgraded with Enterprise Features. 🚀
