import streamlit as st

from db import get_client

st.set_page_config(page_title="Empresas", layout="wide")
st.title("Empresas do grupo")
st.caption("Ex.: Phoenix, Vizentim. Cada conta bancária é vinculada a uma empresa.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

with st.form("nova_empresa", clear_on_submit=True):
    nome = st.text_input("Nome da empresa")
    submitted = st.form_submit_button("Cadastrar")
    if submitted:
        if not nome.strip():
            st.warning("Informe um nome.")
        else:
            try:
                client.table("empresas").insert({"nome": nome.strip()}).execute()
                st.success(f"Empresa '{nome}' cadastrada.")
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

st.divider()
st.subheader("Empresas cadastradas")
try:
    resp = client.table("empresas").select("*").order("nome").execute()
    empresas = resp.data or []
    if empresas:
        st.dataframe(empresas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma empresa cadastrada ainda.")
except Exception as e:
    st.error(f"Erro ao carregar empresas: {e}")
