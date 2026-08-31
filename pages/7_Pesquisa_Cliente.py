import streamlit as st

from db import get_client
from formatacao import data_br, moeda

st.set_page_config(page_title="Pesquisa por Cliente", layout="wide")
st.title("Pesquisa por cliente")
st.caption("Histórico completo: movimentações de comissão e lançamentos previstos.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

clientes = client.table("clientes").select("id, nome, documento, empresas(nome)").order("nome").execute().data or []
if not clientes:
    st.info("Nenhum cliente cadastrado ainda.")
    st.stop()

nomes_por_id = {c["id"]: c["nome"] for c in clientes}
busca = st.text_input("Digite parte do nome para filtrar")
opcoes = [i for i in nomes_por_id if not busca or busca.strip().lower() in nomes_por_id[i].lower()]

if not opcoes:
    st.warning("Nenhum cliente encontrado com esse nome.")
    st.stop()

cliente_id = st.selectbox("Cliente", options=opcoes, format_func=lambda i: nomes_por_id[i])
cliente = next(c for c in clientes if c["id"] == cliente_id)

st.divider()
col1, col2 = st.columns(2)
col1.metric("Nome", cliente["nome"])
col2.metric("Empresa principal", (cliente.get("empresas") or {}).get("nome", "-"))

movimentacoes = (
    client.table("movimentacoes_comissao")
    .select("tipo, apolice, parcela, percentual_comissao, valor_parcela, valor_comissao, lotes_comissao(data_pagamento, seguradoras(nome))")
    .eq("cliente_id", cliente_id)
    .execute()
    .data
    or []
)

st.divider()
st.subheader(f"Movimentações de comissão ({len(movimentacoes)})")
if movimentacoes:
    total = sum(m["valor_comissao"] for m in movimentacoes)
    st.metric("Total líquido de comissões (histórico)", moeda(total))
    st.dataframe(
        [
            {
                "Data": data_br((m.get("lotes_comissao") or {}).get("data_pagamento")),
                "Seguradora": ((m.get("lotes_comissao") or {}).get("seguradoras") or {}).get("nome"),
                "Apólice": m["apolice"],
                "Parcela": m["parcela"],
                "Tipo": m["tipo"],
                "% Comissão": m["percentual_comissao"],
                "Valor Comissão": moeda(m["valor_comissao"]),
            }
            for m in movimentacoes
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Nenhuma movimentação de comissão para este cliente.")

lancamentos = (
    client.table("lancamentos_previstos")
    .select("tipo, descricao, valor, data_vencimento, status, parcela_atual, parcela_total")
    .eq("cliente_id", cliente_id)
    .order("data_vencimento")
    .execute()
    .data
    or []
)

st.divider()
st.subheader(f"Lançamentos previstos ({len(lancamentos)})")
if lancamentos:
    st.dataframe(
        [
            {
                "Vencimento": data_br(l["data_vencimento"]),
                "Tipo": l["tipo"],
                "Descrição": l["descricao"],
                "Parcela": f"{l['parcela_atual']}/{l['parcela_total']}" if l["parcela_atual"] else "-",
                "Valor": moeda(l["valor"]),
                "Situação": l["status"],
            }
            for l in lancamentos
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Nenhum lançamento previsto para este cliente.")
