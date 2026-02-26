-- 1. Create the ent_firms table
CREATE TABLE IF NOT EXISTS public.ent_firms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES public.ent_organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    opening_balance NUMERIC(15, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Enable Row Level Security (RLS)
ALTER TABLE public.ent_firms ENABLE ROW LEVEL SECURITY;

-- 3. Add RLS Policies mirroring ent_staff
-- Allow users to view firms if they have access to the organization
CREATE POLICY "Users can view firms for their organization"
ON public.ent_firms
FOR SELECT
USING (
    EXISTS (
        SELECT 1
        FROM public.ent_members
        WHERE ent_members.organization_id = ent_firms.organization_id
        AND ent_members.user_id = auth.uid()
    )
);

-- Allow users to insert firms if they have access to the organization
CREATE POLICY "Users can insert firms for their organization"
ON public.ent_firms
FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM public.ent_members
        WHERE ent_members.organization_id = ent_firms.organization_id
        AND ent_members.user_id = auth.uid()
    )
);

-- Allow users to update firms if they have access to the organization
CREATE POLICY "Users can update firms for their organization"
ON public.ent_firms
FOR UPDATE
USING (
    EXISTS (
        SELECT 1
        FROM public.ent_members
        WHERE ent_members.organization_id = ent_firms.organization_id
        AND ent_members.user_id = auth.uid()
    )
);

-- Allow users to delete firms if they have access to the organization
CREATE POLICY "Users can delete firms for their organization"
ON public.ent_firms
FOR DELETE
USING (
    EXISTS (
        SELECT 1
        FROM public.ent_members
        WHERE ent_members.organization_id = ent_firms.organization_id
        AND ent_members.user_id = auth.uid()
    )
);
