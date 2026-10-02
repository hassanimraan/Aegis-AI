import streamlit as st

from database.supabase_client import get_supabase


def login_user(email, password):
    supabase = get_supabase()

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email.strip(),
            "password": password
        })

        if response.user:
            st.session_state["user"] = response.user
            return True, "Login successful."

        return False, "Login failed."

    except Exception as e:
        return False, str(e)


def signup_user(name, email, password):
    supabase = get_supabase()

    try:
        response = supabase.auth.sign_up({
            "email": email.strip(),
            "password": password,
            "options": {
                "data": {
                    "full_name": name.strip()
                }
            }
        })

        if response.user:
            st.session_state["user"] = response.user
            return True, "Account created successfully."

        return False, "Account creation failed."

    except Exception as e:
        return False, str(e)


def logout_user():
    supabase = get_supabase()

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.pop("user", None)
