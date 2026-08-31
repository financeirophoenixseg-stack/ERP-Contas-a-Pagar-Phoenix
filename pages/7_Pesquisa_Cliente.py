import streamlit as st

import layout
from db import get_client
from formatacao import data_br, moeda

st.set_page_config(page_title="Pesquisa por Cliente", layout="wide")
layout.aplicar_logo()
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


def _iniciais(nome: str) -> str:
    palavras = [p for p in nome.strip().split() if p]
    if not palavras:
        return "?"
    if len(palavras) == 1:
        return palavras[0][:2].upper()
    return (palavras[0][0] + palavras[-1][0]).upper()


nome_empresa_principal = (cliente.get("empresas") or {}).get("nome")

st.markdown(
    layout._compacto(
        f"""
        <div class="card" style="padding:20px 24px;display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:16px;">
            <div style="width:52px;height:52px;border-radius:14px;background:rgba(30,95,191,0.10);display:flex;align-items:center;justify-content:center;color:#1E5FBF;font-family:'Manrope',sans-serif;font-weight:700;font-size:18px;">{_iniciais(cliente['nome'])}</div>
            <div>
              <div style="font-family:'Manrope',sans-serif;font-weight:700;font-size:18px;color:#10233F;">{cliente['nome']}</div>
              <div style="font-size:12.5px;color:#8592A8;margin-top:2px;">{cliente.get('documento') or 'Sem documento cadastrado'}</div>
            </div>
          </div>
          {f'<span class="pill pill-blue">Empresa principal: {nome_empresa_principal}</span>' if nome_empresa_principal else ''}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

movimentacoes = (
    client.table("movimentacoes_comissao")
    .select("tipo, apolice, parcela, percentual_comissao, valor_parcela, valor_comissao, lotes_comissao(data_pagamento, seguradoras(nome))")
    .eq("cliente_id", cliente_id)
    .execute()
    .data
    or []
)
lancamentos = (
    client.table("lancamentos_previstos")
    .select("tipo, descricao, valor, data_vencimento, status, parcela_atual, parcela_total")
    .eq("cliente_id", cliente_id)
    .order("data_vencimento")
    .execute()
    .data
    or []
)
total_comissoes = sum(m["valor_comissao"] for m in movimentacoes)

layout.cartoes_kpi(
    [
        {
            "icone": "check",
            "cor": "#0ca30c",
            "label": "Total líquido de comissões (histórico)",
            "valor": moeda(total_comissoes),
            "valor_cor": "#0ca30c",
        },
        {"icone": "receber", "label": "Movimentações de comissão", "valor": str(len(movimentacoes))},
        {"icone": "pagar", "label": "Lançamentos previstos", "valor": str(len(lancamentos))},
    ]
)

st.divider()
st.subheader(f"Movimentações de comissão ({len(movimentacoes)})")
if movimentacoes:
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
