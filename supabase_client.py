import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

def get_supabase() -> Client:
    """إرجاع عميل Supabase جاهز للاستخدام"""
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)

# إنشاء عميل عام لاستخدامه في جميع الملفات
supabase = get_supabase()