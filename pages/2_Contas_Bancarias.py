import streamlit as st

from db import get_client

st.set_page_config(page_title="Contas Bancárias", layout="wide")
st.title("Contas bancárias")
st.caption(
    "Banco + agência + conta identificam automaticamente a empresa ao importar um OFX."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

try:
    empresas = client.table("empresas").select("id, nome").order("nome").execute().data or []
except Exception as e:
    st.error(f"Erro ao carregar empresas: {e}")
    st.stop()

if not empresas:
    st.warning("Cadastre ao menos uma empresa antes de adicionar contas bancárias.")
    st.stop()

nomes_por_id = {e["id"]: e["nome"] for e in empresas}

with st.form("nova_conta", clear_on_submit=True):
    empresa_id = st.selectbox(
        "Empresa", options=list(nomes_por_id.keys()), format_func=lambda i: nomes_por_id[i]
    )
    col1, col2, col3 = st.columns(3)
    banco = col1.text_input("Banco (código)", placeholder="756")
    agencia = col2.text_input("Agência", placeholder="4406-7")
    conta = col3.text_input("Conta", placeholder="4928-0")
    submitted = st.form_submit_button("Cadastrar")
    if submitted:
        if not (banco.strip() and agencia.strip() and conta.strip()):
            st.warning("Preencha banco, agência e conta.")
        else:
            try:
                client.table("contas_bancarias").insert(
                    {
                        "empresa_id": empresa_id,
                        "banco": banco.strip(),
                        "agencia": agencia.strip(),
                        "conta": conta.strip(),
                    }
                ).execute()
                st.success(f"Conta {conta} cadastrada para {nomes_por_id[empresa_id]}.")
            except Exception as e:
                st.error(f"Erro ao cadastrar (verifique se essa conta já existe): {e}")

st.divider()
st.subheader("Contas cadastradas")
try:
    resp = (
        client.table("contas_bancarias")
        .select("banco, agencia, conta, empresas(nome)")
        .order("banco")
        .execute()
    )
    contas = resp.data or []
    if contas:
        linhas = [
            {
                "Empresa": c["empresas"]["nome"] if c.get("empresas") else "?",
                "Banco": c["banco"],
                "Agência": c["agencia"],
                "Conta": c["conta"],
            }
            for c in contas
        ]
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma conta cadastrada ainda.")
except Exception as e:
    st.error(f"Erro ao carregar contas: {e}")
