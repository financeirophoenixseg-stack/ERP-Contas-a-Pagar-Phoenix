from datetime import date

import streamlit as st

from db import get_client
from formatacao import moeda

st.set_page_config(page_title="ERP Phoenix/Vizentim", layout="wide")

st.title("ERP Phoenix / Vizentim — Dashboard")
st.caption("Visão geral. Use o menu à esquerda para navegar entre os módulos.")

try:
    client = get_client()
except RuntimeError as e:
    st.warning(str(e))
    st.stop()
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase: {e}")
    st.stop()

hoje = date.today().isoformat()

previstos = (
    client.table("lancamentos_previstos")
    .select("tipo, valor, data_vencimento, status")
    .eq("status", "previsto")
    .execute()
    .data
    or []
)
a_pagar = [p for p in previstos if p["tipo"] == "pagar"]
a_receber = [p for p in previstos if p["tipo"] == "receber"]
a_pagar_vencido = [p for p in a_pagar if p["data_vencimento"] < hoje]
a_receber_vencido = [p for p in a_receber if p["data_vencimento"] < hoje]

col1, col2, col3, col4 = st.columns(4)
col1.metric("A pagar (previsto)", moeda(sum(p["valor"] for p in a_pagar)), f"{len(a_pagar)} lançamento(s)")
col2.metric(
    "A pagar vencido",
    moeda(sum(p["valor"] for p in a_pagar_vencido)),
    f"{len(a_pagar_vencido)} lançamento(s)",
    delta_color="inverse",
)
col3.metric("A receber (previsto)", moeda(sum(p["valor"] for p in a_receber)), f"{len(a_receber)} lançamento(s)")
col4.metric(
    "A receber vencido",
    moeda(sum(p["valor"] for p in a_receber_vencido)),
    f"{len(a_receber_vencido)} lançamento(s)",
    delta_color="inverse",
)

st.divider()

lotes = client.table("lotes_comissao").select("status, valor_liquido").execute().data or []
por_status = {"pendente": [], "conciliado": [], "divergente": []}
for l in lotes:
    por_status.setdefault(l["status"], []).append(l)

col1, col2, col3 = st.columns(3)
col1.metric("Comissões conciliadas", len(por_status["conciliado"]), moeda(sum(l["valor_liquido"] for l in por_status["conciliado"])))
col2.metric("Comissões pendentes", len(por_status["pendente"]), moeda(sum(l["valor_liquido"] for l in por_status["pendente"])))
col3.metric("Comissões divergentes ⚠️", len(por_status["divergente"]), moeda(sum(l["valor_liquido"] for l in por_status["divergente"])))

alertas = client.table("auditoria_alertas").select("id, tipo, descricao, created_at").eq("resolvido", False).order("created_at", desc=True).execute().data or []
if alertas:
    st.divider()
    st.subheader(f"⚠️ {len(alertas)} alerta(s) de auditoria não resolvido(s)")
    st.dataframe(
        [{"Data": a["created_at"][:10], "Tipo": a["tipo"], "Descrição": a["descricao"]} for a in alertas],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Veja e resolva em **Alertas**.")

st.divider()
n_empresas = len(client.table("empresas").select("id").execute().data or [])
n_contas = len(client.table("contas_bancarias").select("id").execute().data or [])
n_clientes = len(client.table("clientes").select("id").execute().data or [])
col1, col2, col3 = st.columns(3)
col1.metric("Empresas", n_empresas)
col2.metric("Contas bancárias", n_contas)
col3.metric("Clientes cadastrados", n_clientes)

st.caption("Ver [PLANO.md](.) para escopo completo, modelo de dados e cronograma.")
