import os
import sys
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(url, key)

res = supabase.table('ent_firms').select('*').execute()
print("Total firms found:", len(res.data))
for r in res.data:
    print("Firm name:", r.get('name'))
