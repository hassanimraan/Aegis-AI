import streamlit as st


def get_supabase_url():
    return st.secrets["SUPABASE_URL"]


def get_supabase_key():
    return st.secrets["SUPABASE_KEY"]


def get_gemini_api_key():
    return st.secrets["GEMINI_API_KEY"]


def get_groq_api_key():
    return st.secrets["GROQ_API_KEY"]


def get_openrouter_api_key():
    return st.secrets["OPENROUTER_API_KEY"]
