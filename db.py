import os

import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


@st.cache_resource
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL/SUPABASE_KEY não configurados. Copie .env.example para .env "
            "e preencha com as credenciais do seu projeto Supabase."
        )
    return create_client(url, key)
