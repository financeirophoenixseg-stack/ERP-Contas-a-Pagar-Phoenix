import streamlit as st

from db import get_client

st.set_page_config(page_title="ERP Phoenix/Vizentim", layout="wide")

st.title("ERP Phoenix / Vizentim — Conciliação Bancária + Comissões")
st.caption("Semana 1: empresas e contas bancárias. Use o menu à esquerda para navegar.")

try:
    client = get_client()
    n_empresas = len(client.table("empresas").select("id").execute().data or [])
    n_contas = len(client.table("contas_bancarias").select("id").execute().data or [])
    col1, col2 = st.columns(2)
    col1.metric("Empresas cadastradas", n_empresas)
    col2.metric("Contas bancárias cadastradas", n_contas)
except RuntimeError as e:
    st.warning(str(e))
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase: {e}")

st.divider()
st.markdown(
    "- **Empresas**: cadastro das empresas do grupo (Phoenix, Vizentim, ...)\n"
    "- **Contas Bancárias**: banco + agência + conta, vinculadas a uma empresa — "
    "usadas para identificar automaticamente a empresa ao importar um OFX\n\n"
    "Ver [PLANO.md](.) para escopo completo, modelo de dados e cronograma."
)
