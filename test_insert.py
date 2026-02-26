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
    # Get organization_id from the first row to reuse
    existing = supabase.table('ent_investments').select('organization_id').limit(1).execute()
    org_id = existing.data[0]['organization_id'] if existing.data else None
    
    if not org_id:
        print("No org ID found, cannot test insert.")
        sys.exit()

    # Test insert
    data = {
        'organization_id': org_id,
        'amount': 100,
        'date': '2026-02-25',
        'type': 'investment',
        'narrative': 'Test Direct Insert via Service Role',
        'firm': 'TEST FIRM XYZ'
    }
    
    print("Testing insert:", data)
    res = supabase.table('ent_investments').insert(data).execute()
    
    if res.data:
        inserted_id = res.data[0]['id']
        # Fetch it back to see if firm was saved
        fetch_res = supabase.table('ent_investments').select('id, narrative, firm').eq('id', inserted_id).execute()
        print("Fetched back:", fetch_res.data)
except Exception as e:
    print("Error:", e)
