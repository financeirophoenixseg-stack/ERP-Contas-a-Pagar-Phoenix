from datetime import date, timedelta

import streamlit as st

import exportacao
import layout
from db import get_client
from formatacao import data_br, moeda
from graficos import grafico_fluxo_caixa
from relatorios import (
    calcular_aging,
    calcular_comissoes_por_cliente,
    calcular_comissoes_por_seguradora,
    calcular_evolucao_mensal,
    calcular_fluxo_projetado,
    calcular_impostos_retidos,
)

st.set_page_config(page_title="Relatórios", layout="wide")
layout.aplicar_logo()
st.title("Relatórios")
st.caption(
    "Relatórios gerenciais — todos calculados a partir dos dados já lançados no sistema "
    "(nada estimado ou escrito pela IA)."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

empresas = client.table("empresas").select("id, nome").order("nome").execute().data or []
empresas_por_id = {e["id"]: e["nome"] for e in empresas}
opcoes_empresa = ["Todas"] + list(empresas_por_id.keys())
empresa_escolhida = st.selectbox(
    "Empresa", options=opcoes_empresa, format_func=lambda i: "Todas" if i == "Todas" else empresas_por_id[i]
)
empresa_id = None if empresa_escolhida == "Todas" else empresa_escolhida

aba_fluxo, aba_aging, aba_comissoes, aba_impostos = st.tabs(
    ["Fluxo de Caixa Projetado", "Aging (Atrasados)", "Comissões", "Impostos e Evolução"]
)

MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

with aba_fluxo:
    st.subheader("Fluxo de Caixa Projetado")
    st.caption(
        "O que já está lançado como previsto pra entrar/sair, somado ao caixa atual — "
        "diferente do fluxo de caixa realizado (esse é o dinheiro que já passou pelo banco)."
    )

    fluxo = calcular_fluxo_projetado(client, empresa_id=empresa_id)

    layout.cartoes_kpi(
        [
            {"icone": "banco", "label": "Caixa atual", "valor": moeda(fluxo["caixa_atual"])},
            {
                "icone": "receber",
                "cor": "#0ca30c",
                "label": "Saldo projetado em 90 dias",
                "valor": moeda(fluxo["buckets"][-1]["saldo_projetado_acumulado"]) if fluxo["buckets"] else moeda(0),
                "valor_cor": "#0ca30c" if (fluxo["buckets"] and fluxo["buckets"][-1]["saldo_projetado_acumulado"] >= 0) else "#B23A3A",
            },
        ],
        colunas=2,
    )

    linhas_fluxo = [
        {
            "Período": b["periodo"],
            "Entradas": moeda(b["entradas"]),
            "Saídas": moeda(b["saidas"]),
            "Saldo líquido": moeda(b["saldo_liquido"]),
            "Saldo projetado acumulado": moeda(b["saldo_projetado_acumulado"]),
        }
        for b in fluxo["buckets"]
    ]
    st.dataframe(linhas_fluxo, use_container_width=True, hide_index=True)

    col_exp1, col_exp2, _ = st.columns([1, 1, 3])
    col_exp1.download_button(
        "⬇️ Excel",
        data=exportacao.gerar_excel(linhas_fluxo, "Fluxo Projetado"),
        file_name=f"fluxo_projetado_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=not linhas_fluxo,
        key="fluxo_export_excel",
    )
    col_exp2.download_button(
        "⬇️ PDF",
        data=exportacao.gerar_pdf(linhas_fluxo, "Fluxo de Caixa Projetado"),
        file_name=f"fluxo_projetado_{date.today().isoformat()}.pdf",
        mime="application/pdf",
        disabled=not linhas_fluxo,
        key="fluxo_export_pdf",
    )

with aba_aging:
    st.subheader("Aging — contas vencidas por faixa de atraso")
    st.caption("Só lançamentos ainda previstos (não pagos) com vencimento já passado.")

    tipo_aging = layout.pills(["A Pagar", "A Receber"], "aging_tipo_estado", "aging_tipo")
    tipo_aging_valor = "pagar" if tipo_aging == "A Pagar" else "receber"

    aging = calcular_aging(client, tipo=tipo_aging_valor, empresa_id=empresa_id)

    cor_valor_aging = "#B23A3A" if aging["total"] > 0 else "#10233F"
    layout.cartoes_kpi(
        [
            {
                "icone": "alerta",
                "cor": "#B23A3A",
                "label": f"Total atrasado ({tipo_aging.lower()})",
                "valor": moeda(aging["total"]),
                "valor_cor": cor_valor_aging,
            },
            *[
                {"icone": "relogio", "label": f["faixa"], "valor": moeda(f["valor"])}
                for f in aging["por_faixa"]
            ],
        ],
        colunas=5,
    )

    if aging["itens"]:
        st.dataframe(
            [
                {
                    "Descrição": i["descricao"],
                    "Cliente/Fornecedor": i["terceiro"],
                    "Valor": moeda(i["valor"]),
                    "Dias em atraso": i["dias_atraso"],
                    "Faixa": i["faixa"],
                }
                for i in aging["itens"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(f"Nenhuma conta a {tipo_aging_valor} atrasada.")

with aba_comissoes:
    st.subheader("Comissões por Seguradora e por Cliente")

    col_data1, col_data2 = st.columns(2)
    data_inicio_com = col_data1.date_input(
        "Período — de", value=date.today().replace(day=1), format="DD/MM/YYYY", key="comissoes_data_inicio"
    )
    data_fim_com = col_data2.date_input(
        "Período — até", value=date.today(), format="DD/MM/YYYY", key="comissoes_data_fim"
    )

    st.markdown("##### Por seguradora")
    por_seguradora = calcular_comissoes_por_seguradora(
        client, data_inicio_com.isoformat(), data_fim_com.isoformat(), empresa_id=empresa_id
    )
    if por_seguradora:
        st.dataframe(
            [
                {
                    "Seguradora": s["seguradora"],
                    "Valor bruto": moeda(s["valor_bruto"]),
                    "Valor líquido": moeda(s["valor_liquido"]),
                    "Lotes": s["qtd_lotes"],
                    "Pendentes": s["pendente"],
                    "Divergentes": s["divergente"],
                }
                for s in por_seguradora
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma comissão no período.")

    st.markdown("##### Ranking de clientes (por comissão gerada)")
    por_cliente = calcular_comissoes_por_cliente(
        client, data_inicio_com.isoformat(), data_fim_com.isoformat(), empresa_id=empresa_id
    )
    if por_cliente:
        st.dataframe(
            [{"Cliente": c["cliente"], "Comissão no período": moeda(c["valor_comissao"])} for c in por_cliente],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma comissão no período.")

    linhas_comissoes_export = [
        {"Seguradora": s["seguradora"], "Valor Bruto": s["valor_bruto"], "Valor Líquido": s["valor_liquido"], "Lotes": s["qtd_lotes"]}
        for s in por_seguradora
    ]
    col_exp1, col_exp2, _ = st.columns([1, 1, 3])
    col_exp1.download_button(
        "⬇️ Excel",
        data=exportacao.gerar_excel(linhas_comissoes_export, "Comissões por Seguradora"),
        file_name=f"comissoes_{date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=not linhas_comissoes_export,
        key="comissoes_export_excel",
    )
    col_exp2.download_button(
        "⬇️ PDF",
        data=exportacao.gerar_pdf(linhas_comissoes_export, "Comissões por Seguradora"),
        file_name=f"comissoes_{date.today().isoformat()}.pdf",
        mime="application/pdf",
        disabled=not linhas_comissoes_export,
        key="comissoes_export_pdf",
    )

with aba_impostos:
    st.subheader("Impostos retidos sobre comissão")
    col_data1b, col_data2b = st.columns(2)
    data_inicio_imp = col_data1b.date_input(
        "Período — de", value=date.today().replace(day=1), format="DD/MM/YYYY", key="impostos_data_inicio"
    )
    data_fim_imp = col_data2b.date_input(
        "Período — até", value=date.today(), format="DD/MM/YYYY", key="impostos_data_fim"
    )

    impostos = calcular_impostos_retidos(
        client, data_inicio_imp.isoformat(), data_fim_imp.isoformat(), empresa_id=empresa_id
    )
    layout.cartoes_kpi(
        [
            {"icone": "pagar", "label": "IRRF", "valor": moeda(impostos["irrf"])},
            {"icone": "pagar", "label": "ISS", "valor": moeda(impostos["iss"])},
            {"icone": "pagar", "label": "INSS", "valor": moeda(impostos["inss"])},
            {"icone": "pagar", "label": "PIS/COFINS/CSLL", "valor": moeda(impostos["pis_cofins_csll"])},
            {"icone": "alerta", "cor": "#B23A3A", "label": "Total retido", "valor": moeda(impostos["total"]), "valor_cor": "#B23A3A"},
        ],
        colunas=5,
    )

    st.divider()
    st.subheader("Evolução financeira (receitas x despesas reais)")
    meses_evolucao = st.slider("Quantos meses pra trás?", min_value=3, max_value=24, value=12, key="evolucao_meses")
    evolucao = calcular_evolucao_mensal(client, meses=meses_evolucao, empresa_id=empresa_id)

    if evolucao:
        labels_meses = [f"{MESES_PT[int(e['mes'][5:7]) - 1][:3].capitalize()}/{e['mes'][2:4]}" for e in evolucao]
        receitas_meses = [e["receitas"] for e in evolucao]
        despesas_meses = [e["despesas"] for e in evolucao]
        st.markdown(grafico_fluxo_caixa(labels_meses, receitas_meses, despesas_meses), unsafe_allow_html=True)

        st.dataframe(
            [
                {
                    "Mês": labels_meses[idx],
                    "Receitas": moeda(e["receitas"]),
                    "Despesas": moeda(e["despesas"]),
                    "Resultado": moeda(e["resultado"]),
                }
                for idx, e in enumerate(evolucao)
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sem movimentações bancárias no período pra montar a evolução.")
