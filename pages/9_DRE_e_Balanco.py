from datetime import date

import streamlit as st

import layout
from db import get_client
from formatacao import moeda
from relatorios import calcular_balanco, calcular_dre

st.set_page_config(page_title="DRE e Balanço", layout="wide")
layout.aplicar_logo()
st.title("DRE e Balanço Patrimonial")
st.caption(
    "Calculados a partir dos lançamentos já classificados — a IA não escreve estes números, "
    "ela só ajuda a sugerir a classificação de cada lançamento (com você sempre confirmando)."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

empresas = client.table("empresas").select("id, nome").order("nome").execute().data or []
if not empresas:
    st.error("Cadastre ao menos uma empresa em **Configurações** antes de continuar.")
    st.stop()
empresas_por_id = {e["id"]: e["nome"] for e in empresas}

col1, col2, col3 = st.columns(3)
empresa_id = col1.selectbox("Empresa", options=["Todas"] + list(empresas_por_id.keys()), format_func=lambda i: "Todas" if i == "Todas" else empresas_por_id[i])
data_inicio = col2.date_input("Período - de", value=date(date.today().year, 1, 1), format="DD/MM/YYYY")
data_fim = col3.date_input("Período - até", value=date.today(), format="DD/MM/YYYY")

st.divider()
st.header("DRE — Demonstrativo de Resultado")

dre = calcular_dre(
    client,
    data_inicio.isoformat(),
    data_fim.isoformat(),
    empresa_id=None if empresa_id == "Todas" else empresa_id,
)

col1, col2, col3 = st.columns(3)
col1.metric("Receitas", moeda(dre["total_receitas"]))
col2.metric("Despesas", moeda(dre["total_despesas"]))
col3.metric("Resultado", moeda(dre["resultado"]))

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Receitas")
    if dre["receitas"]:
        st.dataframe(
            [{"Categoria": k, "Valor": moeda(v)} for k, v in dre["receitas"].items()],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Nenhuma receita classificada no período.")
with col_b:
    st.subheader("Despesas")
    if dre["despesas"]:
        st.dataframe(
            [{"Categoria": k, "Valor": moeda(v)} for k, v in dre["despesas"].items()],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Nenhuma despesa classificada no período.")

st.divider()
st.header("Balanço Patrimonial (simplificado)")
st.caption(
    "⚠️ Aproximação, não é contabilidade de partidas dobradas real — 'Caixa' é a soma de todo "
    "o histórico de OFX já importado (assumindo que a importação começou do saldo zero da conta)."
)

balanco = calcular_balanco(client, empresa_id=None if empresa_id == "Todas" else empresa_id)

col1, col2, col3 = st.columns(3)
col1.metric("Total Ativo", moeda(balanco["total_ativo"]))
col2.metric("Total Passivo", moeda(balanco["total_passivo"]))
col3.metric("Patrimônio Líquido", moeda(balanco["patrimonio_liquido"]))

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Ativo")
    st.dataframe([{"Conta": k, "Valor": moeda(v)} for k, v in balanco["ativo"].items()], use_container_width=True, hide_index=True)
with col_b:
    st.subheader("Passivo")
    st.dataframe([{"Conta": k, "Valor": moeda(v)} for k, v in balanco["passivo"].items()], use_container_width=True, hide_index=True)
