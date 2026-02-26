import os
import sys
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(url, key)

try:
    res = supabase.table('ent_investments').select('*').order('id', desc=True).limit(3).execute()
    print("=== INVESTMENTS ===")
    for r in res.data:
        print(f"ID: {r.get('id')}, Date: {r.get('date')}, Narrative: {r.get('narrative')}, Firm: '{r.get('firm')}'")

    res2 = supabase.table('ent_holding_payments').select('*').order('id', desc=True).limit(3).execute()
    print("=== HOLDINGS ===")
    for r in res2.data:
        print(f"ID: {r.get('id')}, Name: {r.get('name')}, Amount: {r.get('amount')}, Firm: '{r.get('firm')}'")
        
    res3 = supabase.table('ent_expenses').select('*').order('id', desc=True).limit(2).execute()
    print("=== EXPENSES ===")
    for r in res3.data:
        print(f"ID: {r.get('id')}, Narrative: {r.get('narrative')}, Amount: {r.get('amount')}, Firm: '{r.get('firm')}'")
        
except Exception as e:
    print("Error:", e)
