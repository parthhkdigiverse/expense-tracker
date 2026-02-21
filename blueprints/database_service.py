import os
from typing import List, Dict, Any, Optional
from supabase import create_client, ClientOptions

# ── Supabase Config ────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_supabase_client(token=None):
    """Create a Supabase client, optionally scoped to a user JWT."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    if token:
        return create_client(
            SUPABASE_URL, SUPABASE_KEY,
            options=ClientOptions(headers={"Authorization": f"Bearer {token}"})
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)

DEFAULT_CATEGORIES = [
    'Food', 'Transport', 'Utilities', 'Entertainment', 'Shopping',
    'Health', 'Travel', 'Education', 'Salary', 'Freelance', 'Investment', 'Other'
]

# ── Service Interface ──────────────────────────────────────────────────────────
class BaseService:
    """Abstract interface — all methods raise NotImplementedError by default."""
    def get_user_organizations(self, user_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def get_organization_name(self, org_id: str) -> Optional[str]: raise NotImplementedError
    def get_org_id_by_name(self, user_id: str, org_name: str) -> Optional[str]: raise NotImplementedError
    def get_revenue(self, org_id: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]: raise NotImplementedError
    def get_expenses(self, org_id: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]: raise NotImplementedError
    def add_revenue(self, org_id: str, data: Dict[str, Any]) -> bool: raise NotImplementedError
    def add_expense(self, org_id: str, data: Dict[str, Any]) -> bool: raise NotImplementedError
    def get_investments(self, org_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def add_investment(self, org_id: str, data: dict) -> bool: raise NotImplementedError
    def get_members(self, org_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def add_member(self, org_id: str, user_id: str, role: str = 'member') -> bool: raise NotImplementedError
    def find_profile_by_email(self, email: str) -> Optional[Dict[str, Any]]: raise NotImplementedError
    def get_personal_banks(self, user_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def get_enterprise_banks(self, user_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def get_banks_for_org(self, user_id: str, org_name: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def add_enterprise_bank(self, user_id: str, data: Dict[str, Any]) -> bool: raise NotImplementedError
    def update_enterprise_bank(self, user_id: str, bank_id: str, data: Dict[str, Any]) -> bool: raise NotImplementedError
    def delete_enterprise_bank(self, user_id: str, bank_id: str) -> bool: raise NotImplementedError
    def get_categories(self, user_id: str) -> List[str]: raise NotImplementedError
    def get_holding_payments(self, org_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def add_holding_payment(self, org_id: str, user_id: str, data: dict) -> bool: raise NotImplementedError
    def settle_holding_payment(self, txn_id: str, org_id: str, settle_type: str, part_amount: float = 0) -> dict: raise NotImplementedError
    def provision_business_org(self, user_id: str, business_name: str) -> Optional[str]: raise NotImplementedError
    def add_org_member(self, org_id: str, name: str, designation: str) -> bool: raise NotImplementedError
    def get_org_members(self, org_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def verify_or_create_business_access(self, user_id: str, business_name: str) -> bool: raise NotImplementedError
    def get_user_businesses(self, user_id: str) -> List[Dict[str, Any]]: raise NotImplementedError
    def get_personal_transactions(self, user_id: str, filters: dict) -> List[Dict[str, Any]]: raise NotImplementedError

# ── Supabase Implementation ────────────────────────────────────────────────────
class SupabaseService(BaseService):
    def __init__(self, client):
        self.db = client

    # ── Enterprise Access (Secure Double Login) ───────────────────────────────
    def verify_business_pin(self, user_id: str, business_name: str, pin: str) -> bool:
        """Securely verify the business PIN against the hashed value in Supabase using the RPC."""
        try:
            res = self.db.rpc('verify_business_pin', {
                'p_user_id': user_id,
                'p_business_name': business_name,
                'p_pin': pin
            }).execute()
            return res.data is True
        except Exception as e:
            print(f"[verify_business_pin] Error: {e}")
            return False

    def setup_business_pin(self, user_id: str, business_name: str, pin: str) -> bool:
        """Create or update a business access row with a securely hashed PIN using the RPC."""
        try:
            res = self.db.rpc('setup_business_pin', {
                'p_user_id': user_id,
                'p_business_name': business_name,
                'p_pin': pin
            }).execute()
            return res.data is True
        except Exception as e:
            print(f"[setup_business_pin] Error: {e}")
            return False

    def get_user_businesses(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all businesses the user has access to via ent_members table."""
        try:
            res = self.db.table('ent_members') \
                .select('role, ent_organizations!inner(name)') \
                .eq('user_id', user_id) \
                .execute()
            businesses = []
            if res.data:
                for r in res.data:
                    org = r.get('ent_organizations')
                    if org:
                        businesses.append({'business_name': org.get('name'), 'role': r.get('role')})
            businesses.sort(key=lambda x: x['business_name'])
            return businesses
        except Exception as e:
            print(f"[get_user_businesses] {e}")
            return []

    # ── Organizations ──
    def get_user_organizations(self, user_id: str) -> List[Dict[str, Any]]:
        """Return orgs the user belongs to."""
        try:
            res = self.db.table('ent_members') \
                .select('organization_id, ent_organizations!inner(name)') \
                .eq('user_id', user_id) \
                .execute()
            orgs = []
            if res.data:
                for r in res.data:
                    org = r.get('ent_organizations')
                    if org:
                        orgs.append({'id': r['organization_id'], 'name': org.get('name')})
            orgs.sort(key=lambda x: x['name'])
            return orgs
        except Exception as e:
            print(f"[get_user_organizations] {e}")
            return []

    def get_organization_name(self, org_id: str) -> Optional[str]:
        try:
            res = self.db.table('ent_organizations').select('name').eq('id', org_id).execute()
            return res.data[0]['name'] if res.data else None
        except Exception as e:
            print(f"[get_organization_name] {e}")
            return None

    def get_org_id_by_name(self, user_id: str, org_name: str) -> Optional[str]:
        # User ID is ignored here but kept for interface compatibility
        try:
            res = self.db.table('ent_organizations').select('id').eq('name', org_name).execute()
            return str(res.data[0]['id']) if res.data else None
        except Exception as e:
            print(f"[get_org_id_by_name] {e}")
            return None

    def provision_business_org(self, user_id: str, business_name: str) -> Optional[str]:
        """Idempotently ensure business exists and user is owner."""
        try:
            res = self.db.table('ent_organizations').select('id').eq('name', business_name).execute()
            if res.data:
                org_id = str(res.data[0]['id'])
            else:
                res_create = self.db.table('ent_organizations').insert({'name': business_name}).execute()
                if not res_create.data: return None
                org_id = str(res_create.data[0]['id'])

            mem_res = self.db.table('ent_members').select('id').eq('organization_id', org_id).eq('user_id', user_id).execute()
            if not mem_res.data:
                self.db.table('ent_members').insert({
                    'organization_id': org_id,
                    'user_id': user_id,
                    'role': 'owner'
                }).execute()
            return org_id
        except Exception as e:
            print(f"[provision_business_org] {e}")
            return None

    def get_revenue(self, org_id: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        query = self.db.table('ent_revenue') \
            .select('*, enterprise_bank_accounts(bank_name)') \
            .eq('organization_id', org_id)
        if start_date: query = query.gte('date', start_date)
        if end_date:   query = query.lte('date', end_date)
        res = query.order('date', desc=True).execute()
        return [
            {
                'taken_by_name': r.get('taken_by') or 'Unknown',
                'bank_name':     r.get('enterprise_bank_accounts', {}) and r['enterprise_bank_accounts'].get('bank_name') or None,
                **r
            }
            for r in res.data
        ]

    def add_revenue(self, org_id: str, data: Dict[str, Any]) -> bool:
        try:
            data['organization_id'] = org_id
            self.db.table('ent_revenue').insert(data).execute()
            return True
        except Exception as e:
            print(f"[add_revenue] {e}")
            return False

    # ── Expenses ──────────────────────────────────────────────────────────────
    def get_expenses(self, org_id: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        query = self.db.table('ent_expenses') \
            .select('*, enterprise_bank_accounts(bank_name)') \
            .eq('organization_id', org_id)
        if start_date: query = query.gte('date', start_date)
        if end_date:   query = query.lte('date', end_date)
        res = query.order('date', desc=True).execute()
        return [
            {
                'taken_by_name': r.get('taken_by') or 'Unknown',
                'bank_name':     r.get('enterprise_bank_accounts', {}) and r['enterprise_bank_accounts'].get('bank_name') or None,
                **r
            }
            for r in res.data
        ]

    def add_expense(self, org_id: str, data: Dict[str, Any]) -> bool:
        try:
            data['organization_id'] = org_id
            self.db.table('ent_expenses').insert(data).execute()
            return True
        except Exception as e:
            print(f"[add_expense] {e}")
            return False

    # ── Investments ───────────────────────────────────────────────────────────
    def get_investments(self, org_id: str) -> List[Dict[str, Any]]:
        try:
            res = self.db.table('ent_investments').select('*').eq('organization_id', org_id).order('date', desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[get_investments] {e}")
            return []

    def add_investment(self, org_id: str, data: dict) -> bool:
        try:
            taken_by  = (data.get('taken_by',  '') or '').strip() or None
            narrative = (data.get('narrative', '') or '').strip() or None
            self.db.table('ent_investments').insert({
                'organization_id': org_id,
                'amount':          float(data.get('amount', 0)),
                'date':            data.get('date'),
                'type':            data.get('type', 'investment'),
                'taken_by':        taken_by,
                'narrative':       narrative,
                'source':          taken_by,
                'description':     narrative,
            }).execute()
            return True
        except Exception as e:
            print(f"[add_investment] {e}")
            return False

    # ── Holding Payments ──────────────────────────────────────────────────────
    def get_holding_payments(self, org_id: str) -> List[Dict[str, Any]]:
        try:
            res = self.db.table('ent_holding_payments') \
                .select('*').eq('organization_id', org_id) \
                .order('created_at', desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"[get_holding_payments] {e}")
            return []

    def add_holding_payment(self, org_id: str, user_id: str, data: dict) -> bool:
        try:
            amt = float(data.get('amount', 0))
            self.db.table('ent_holding_payments').insert({
                'organization_id': org_id,
                'created_by':      user_id,
                'name':            data.get('name'),
                'type':            data.get('type', 'receivable'),
                'amount':          amt,
                'expected_date':   data.get('expected_date') or None,
                'mobile_no':       data.get('mobile_no'),
                'narrative':       data.get('narrative'),
                'status':          'pending',
                'paid_amount':     0,
                'remaining_amount':amt,
            }).execute()
            return True
        except Exception as e:
            print(f"[add_holding_payment] {e}")
            return False

    def settle_holding_payment(self, txn_id: str, org_id: str, settle_type: str, part_amount: float = 0) -> dict:
        try:
            res = self.db.table('ent_holding_payments') \
                .select('*').eq('id', txn_id).eq('organization_id', org_id) \
                .single().execute()
            if not res.data:
                return {'success': False, 'error': 'Transaction not found.'}
            txn         = res.data
            original    = float(txn.get('amount', 0))
            paid_so_far = float(txn.get('paid_amount', 0) or 0)

            if settle_type == 'full':
                new_paid, new_remaining, new_status = original, 0, 'settled'
            else:
                new_paid      = paid_so_far + part_amount
                new_remaining = max(original - new_paid, 0)
                new_status    = 'settled' if new_remaining == 0 else 'partial'

            self.db.table('ent_holding_payments').update({
                'paid_amount':      new_paid,
                'remaining_amount': new_remaining,
                'status':           new_status,
            }).eq('id', txn_id).execute()
            return {'success': True, 'status': new_status, 'paid': new_paid, 'remaining': new_remaining}
        except Exception as e:
            print(f"[settle_holding_payment] {e}")
            return {'success': False, 'error': str(e)}

    # ── Members / Staff ───────────────────────────────────────────────────────
    def get_members(self, org_id: str) -> List[Dict[str, Any]]:
        res = self.db.table('ent_members') \
            .select('role, profiles(id, full_name, email)') \
            .eq('organization_id', org_id).execute()
        return [
            {'role': m['role'], 'id': m['profiles']['id'],
             'full_name': m['profiles']['full_name'], 'email': m['profiles']['email']}
            for m in res.data
        ]

    def add_member(self, org_id: str, user_id: str, role: str = 'member') -> bool:
        try:
            self.db.table('ent_members').insert({
                'organization_id': org_id, 'user_id': user_id, 'role': role
            }).execute()
            return True
        except Exception as e:
            print(f"[add_member] {e}")
            return False

    def add_org_member(self, org_id: str, name: str, designation: str) -> bool:
        """Add a named staff member to ent_staff."""
        try:
            self.db.table('ent_staff').insert(
                {'organization_id': org_id, 'name': name, 'designation': designation}
            ).execute()
            return True
        except Exception as e:
            print(f"[add_org_member] {e}")
            return False

    def get_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        try:
            res = self.db.table('ent_staff').select('*').eq('organization_id', org_id).order('name').execute()
            return res.data or []
        except Exception:
            return []

    def find_profile_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        res = self.db.table('profiles').select('*').eq('email', email).execute()
        return res.data[0] if res.data else None

    # ── Banks — Personal ──────────────────────────────────────────────────────
    def get_personal_banks(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            return self.db.table('bank_accounts').select('*').eq('user_id', user_id).execute().data or []
        except Exception as e:
            print(f"[get_personal_banks] {e}")
            return []

    # ── Banks — Enterprise ────────────────────────────────────────────────────
    def get_enterprise_banks(self, user_id: str) -> List[Dict[str, Any]]:
        """Fetch all enterprise bank accounts from Supabase enterprise_bank_accounts."""
        try:
            return self.db.table('enterprise_bank_accounts').select('*') \
                .eq('user_id', user_id).order('created_at', desc=True).execute().data or []
        except Exception as e:
            print(f"[get_enterprise_banks] {e}")
            return []

    def get_banks_for_org(self, user_id: str, org_name: str) -> List[Dict[str, Any]]:
        """Return enterprise bank accounts scoped to a specific business name."""
        try:
            return self.db.table('enterprise_bank_accounts').select('*') \
                .eq('user_id', user_id).eq('business_name', org_name) \
                .order('created_at', desc=True).execute().data or []
        except Exception as e:
            print(f"[get_banks_for_org] {e}")
            return []

    def add_enterprise_bank(self, user_id: str, data: Dict[str, Any]) -> bool:
        try:
            self.db.table('enterprise_bank_accounts').insert({
                'user_id':         user_id,
                'business_name':   data.get('business_name'),
                'bank_name':       data.get('bank_name'),
                'account_number':  data.get('account_number'),
                'ifsc_code':       data.get('ifsc_code'),
                'opening_balance': data.get('opening_balance', 0.00),
                'account_type':    data.get('account_type', 'Current'),
            }).execute()
            return True
        except Exception as e:
            print(f"[add_enterprise_bank] {e}")
            return False

    def update_enterprise_bank(self, user_id: str, bank_id: str, data: Dict[str, Any]) -> bool:
        try:
            self.db.table('enterprise_bank_accounts').update({
                'business_name':   data.get('business_name'),
                'bank_name':       data.get('bank_name'),
                'account_number':  data.get('account_number'),
                'ifsc_code':       data.get('ifsc_code'),
                'opening_balance': data.get('opening_balance', 0.00),
                'account_type':    data.get('account_type', 'Current'),
            }).eq('id', bank_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            print(f"[update_enterprise_bank] {e}")
            return False

    def delete_enterprise_bank(self, user_id: str, bank_id: str) -> bool:
        try:
            self.db.table('enterprise_bank_accounts').delete() \
                .eq('id', bank_id).eq('user_id', user_id).execute()
            return True
        except Exception as e:
            print(f"[delete_enterprise_bank] {e}")
            return False

    # ── Categories ────────────────────────────────────────────────────────────
    def get_categories(self, user_id: str) -> List[str]:
        try:
            res = self.db.table('user_categories').select('name').eq('user_id', user_id).execute()
            return DEFAULT_CATEGORIES + [r['name'] for r in res.data]
        except Exception:
            return DEFAULT_CATEGORIES

    # ── Personal Transactions (Pocket Expense reports) ────────────────────────
    def get_personal_transactions(self, user_id: str, filters: dict) -> List[Dict[str, Any]]:
        """Fetch filtered personal transactions strictly from Supabase."""
        try:
            query = self.db.table('expenses').select(
                'id, date, category, description, amount, type, bank_account_id, bank_accounts(bank_name)'
            ).eq('user_id', user_id)

            if filters.get('start_date'):
                query = query.gte('date', filters['start_date'])
            if filters.get('end_date'):
                query = query.lte('date', filters['end_date'])
            if filters.get('category') and filters['category'] != 'all':
                query = query.eq('category', filters['category'])
            if filters.get('tx_type') and filters['tx_type'] != 'all':
                query = query.eq('type', filters['tx_type'])
            if filters.get('payment_method') == 'cash':
                query = query.is_('bank_account_id', 'null')
            elif filters.get('payment_method') == 'bank':
                query = query.not_.is_('bank_account_id', 'null')

            res = query.order('date', desc=True).execute()
            rows = []
            for r in (res.data or []):
                bank_name = None
                if r.get('bank_accounts') and isinstance(r['bank_accounts'], dict):
                    bank_name = r['bank_accounts'].get('bank_name')
                rows.append({
                    'id':             r.get('id'),
                    'date':           r.get('date', ''),
                    'category':       r.get('category', 'Uncategorized'),
                    'description':    r.get('description', ''),
                    'amount':         float(r.get('amount', 0)),
                    'type':           r.get('type', 'expense'),
                    'payment_method': bank_name or 'Cash',
                })
            return rows
        except Exception as e:
            print(f"[get_personal_transactions] {e}")
            return []
