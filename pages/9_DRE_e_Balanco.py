from datetime import date

import streamlit as st

from db import get_client
from relatorios import LinhaDRE, montar_balanco, montar_dre

st.set_page_config(page_title="DRE e Balanço", layout="wide")
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
data_inicio = col2.date_input("Período - de", value=date(date.today().year, 1, 1))
data_fim = col3.date_input("Período - até", value=date.today())

st.divider()
st.header("DRE — Demonstrativo de Resultado")

linhas_dre: list[LinhaDRE] = []

# Comissões (lotes_comissao.data_pagamento dentro do período). As
# movimentacoes_comissao trazem o valor BRUTO por linha (antes de
# impostos) — os impostos retidos são do lote como um todo, então entram
# aqui como despesa tributária separada, senão a receita fica inflada.
query = (
    client.table("lotes_comissao")
    .select("id, empresa_id, data_pagamento, valor_irrf, valor_iss, valor_inss, valor_pis_cofins_csll")
    .gte("data_pagamento", data_inicio.isoformat())
    .lte("data_pagamento", data_fim.isoformat())
)
if empresa_id != "Todas":
    query = query.eq("empresa_id", empresa_id)
lotes_periodo = query.execute().data or []
lote_ids = [l["id"] for l in lotes_periodo]

if lote_ids:
    movimentacoes = (
        client.table("movimentacoes_comissao").select("valor_comissao").in_("lote_id", lote_ids).execute().data or []
    )
    total_comissoes = sum(m["valor_comissao"] for m in movimentacoes)
    if total_comissoes:
        if total_comissoes > 0:
            linhas_dre.append(LinhaDRE("receita", "Receita de Comissões (bruto)", total_comissoes))
        else:
            linhas_dre.append(LinhaDRE("despesa", "Cancelamentos/Estornos de Comissão (líquido negativo)", -total_comissoes))

    total_impostos = sum(
        (l["valor_irrf"] or 0) + (l["valor_iss"] or 0) + (l["valor_inss"] or 0) + (l["valor_pis_cofins_csll"] or 0)
        for l in lotes_periodo
    )
    if total_impostos:
        linhas_dre.append(LinhaDRE("despesa", "Impostos sobre Comissões (IRRF/ISS/INSS/PIS-COFINS-CSLL)", total_impostos))

# Lançamentos previstos pagos no período
query = (
    client.table("lancamentos_previstos")
    .select("tipo, valor, descricao, plano_contas(nome)")
    .eq("status", "pago")
    .gte("data_pagamento", data_inicio.isoformat())
    .lte("data_pagamento", data_fim.isoformat())
)
if empresa_id != "Todas":
    query = query.eq("empresa_id", empresa_id)
for lanc in query.execute().data or []:
    categoria = (lanc.get("plano_contas") or {}).get("nome") or ("Outras Receitas" if lanc["tipo"] == "receber" else "Outras Despesas")
    linhas_dre.append(LinhaDRE("receita" if lanc["tipo"] == "receber" else "despesa", categoria, lanc["valor"]))

# Transações OFX classificadas manualmente com conta do plano de contas
query = (
    client.table("ofx_transacoes")
    .select("valor, plano_contas(nome, tipo), contas_bancarias(empresa_id)")
    .not_.is_("plano_conta_id", "null")
    .gte("data", data_inicio.isoformat())
    .lte("data", data_fim.isoformat())
)
for txn in query.execute().data or []:
    if empresa_id != "Todas" and txn["contas_bancarias"]["empresa_id"] != empresa_id:
        continue
    conta = txn.get("plano_contas") or {}
    if conta.get("tipo") in ("receita", "despesa"):
        linhas_dre.append(LinhaDRE(conta["tipo"], conta["nome"], abs(txn["valor"])))

dre = montar_dre(linhas_dre)

col1, col2, col3 = st.columns(3)
col1.metric("Receitas", f"R$ {dre['total_receitas']:,.2f}")
col2.metric("Despesas", f"R$ {dre['total_despesas']:,.2f}")
col3.metric("Resultado", f"R$ {dre['resultado']:,.2f}")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Receitas")
    if dre["receitas"]:
        st.dataframe(
            [{"Categoria": k, "Valor": v} for k, v in dre["receitas"].items()],
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Nenhuma receita classificada no período.")
with col_b:
    st.subheader("Despesas")
    if dre["despesas"]:
        st.dataframe(
            [{"Categoria": k, "Valor": v} for k, v in dre["despesas"].items()],
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

query_caixa = client.table("ofx_transacoes").select("valor, contas_bancarias(empresa_id)")
todas_transacoes = query_caixa.execute().data or []
caixa = sum(
    t["valor"] for t in todas_transacoes
    if empresa_id == "Todas" or t["contas_bancarias"]["empresa_id"] == empresa_id
)

query_receber = client.table("lancamentos_previstos").select("valor, empresa_id").eq("status", "previsto").eq("tipo", "receber")
query_pagar = client.table("lancamentos_previstos").select("valor, empresa_id").eq("status", "previsto").eq("tipo", "pagar")
if empresa_id != "Todas":
    query_receber = query_receber.eq("empresa_id", empresa_id)
    query_pagar = query_pagar.eq("empresa_id", empresa_id)
contas_a_receber = sum(r["valor"] for r in query_receber.execute().data or [])
contas_a_pagar = sum(r["valor"] for r in query_pagar.execute().data or [])

balanco = montar_balanco(caixa, contas_a_receber, contas_a_pagar)

col1, col2, col3 = st.columns(3)
col1.metric("Total Ativo", f"R$ {balanco['total_ativo']:,.2f}")
col2.metric("Total Passivo", f"R$ {balanco['total_passivo']:,.2f}")
col3.metric("Patrimônio Líquido", f"R$ {balanco['patrimonio_liquido']:,.2f}")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Ativo")
    st.dataframe([{"Conta": k, "Valor": v} for k, v in balanco["ativo"].items()], use_container_width=True, hide_index=True)
with col_b:
    st.subheader("Passivo")
    st.dataframe([{"Conta": k, "Valor": v} for k, v in balanco["passivo"].items()], use_container_width=True, hide_index=True)
