from supabase import create_client
from config.settings import get_supabase_url, get_supabase_key


def get_supabase():
    return create_client(
        get_supabase_url(),
        get_supabase_key()
    )
