-- ==========================================
-- SUPABASE ADMIN QUERIES & SCHEMA SETUP
-- ==========================================

-- 1. Add admin and suspension flags to the existing profiles table
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN DEFAULT FALSE;

-- 2. Create the admin_audit_logs table to track admin actions
CREATE TABLE IF NOT EXISTS public.admin_audit_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    admin_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_record_id TEXT NOT NULL,
    old_data JSONB,
    new_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Enable RLS on admin_audit_logs for security
ALTER TABLE public.admin_audit_logs ENABLE ROW LEVEL SECURITY;

-- 4. Create RLS Policies for admin_audit_logs
-- Only admins can view the logs
CREATE POLICY "Admins can view audit logs" ON public.admin_audit_logs
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid() AND profiles.is_admin = TRUE
    )
  );

-- Service role bypasses RLS, but if accessed via standard client, only admins can insert
CREATE POLICY "Admins can insert audit logs" ON public.admin_audit_logs
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid() AND profiles.is_admin = TRUE
    )
  );

-- ==========================================
-- USEFUL ADMIN QUERIES FOR MANUAL EXECUTION
-- ==========================================

-- A. Make a specific user an admin (Replace with the user's actual email or ID)
-- UPDATE public.profiles SET is_admin = TRUE WHERE email = 'your_admin_email@example.com';
-- UPDATE public.profiles SET is_admin = TRUE WHERE id = 'user-uuid-here';

-- B. View all current admins
-- SELECT id, full_name, email FROM public.profiles WHERE is_admin = TRUE;

-- C. Suspend a user manually
-- UPDATE public.profiles SET is_suspended = TRUE WHERE id = 'user-uuid-here';

-- D. View all suspended users
-- SELECT id, full_name, email FROM public.profiles WHERE is_suspended = TRUE;

-- E. View recent admin audit logs
-- SELECT * FROM public.admin_audit_logs ORDER BY created_at DESC LIMIT 50;
