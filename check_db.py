import os
import sys
from dotenv import load_dotenv

# Fix path to import app correctly if needed, but we can just use supabase directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

try:
    res = supabase.table('ent_investments').select('*').limit(1).execute()
    print("ent_investments data:", res.data)
    
    res2 = supabase.table('ent_holding_payments').select('*').limit(1).execute()
    print("ent_holding_payments data:", res2.data)
except Exception as e:
    print("Error:", e)
