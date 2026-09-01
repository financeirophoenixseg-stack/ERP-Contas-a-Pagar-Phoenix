from datetime import date, timedelta

import streamlit as st

import assistente_financeiro
import layout
from db import get_client
from formatacao import data_br, moeda
from graficos import grafico_donut_status, grafico_fluxo_caixa

st.set_page_config(page_title="ERP Phoenix/Vizentim", layout="wide")
layout.aplicar_logo()

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

with st.container(border=True):
    st.markdown("##### 🤖 Assistente Financeiro")
    st.caption(
        "Pergunte sobre contas a pagar/receber, comissões, fluxo de caixa ou DRE — as respostas "
        "vêm sempre de consultas reais aos dados do sistema, nunca de estimativa da IA."
    )

    if not assistente_financeiro.esta_configurado():
        st.info("Configure `ANTHROPIC_API_KEY` no arquivo `.env` para habilitar o assistente financeiro.")
    else:
        if "chat_financeiro" not in st.session_state:
            st.session_state["chat_financeiro"] = []

        for msg in st.session_state["chat_financeiro"]:
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                st.markdown(msg["content"])

        pergunta = st.chat_input("Ex.: quanto tenho a pagar essa semana? Qual cliente me deve mais?")
        if pergunta:
            st.session_state["chat_financeiro"].append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)
            with st.chat_message("assistant"):
                with st.spinner("Consultando os dados..."):
                    try:
                        resposta = assistente_financeiro.responder(st.session_state["chat_financeiro"], client)
                    except Exception as e:
                        resposta = f"Não consegui responder agora — houve um erro: {e}"
                st.markdown(resposta)
            st.session_state["chat_financeiro"].append({"role": "assistant", "content": resposta})

st.divider()

hoje = date.today()
hoje_iso = hoje.isoformat()

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
a_pagar_vencido = [p for p in a_pagar if p["data_vencimento"] < hoje_iso]
a_receber_vencido = [p for p in a_receber if p["data_vencimento"] < hoje_iso]

layout.cartoes_kpi(
    [
        {
            "icone": "pagar",
            "label": "A pagar (previsto)",
            "valor": moeda(sum(p["valor"] for p in a_pagar)),
            "pill_texto": f"{len(a_pagar)} lançamento(s)",
            "pill_classe": "pill-neutral",
        },
        {
            "icone": "alerta",
            "cor": "#B23A3A",
            "label": "A pagar vencido",
            "valor": moeda(sum(p["valor"] for p in a_pagar_vencido)),
            "pill_texto": f"{len(a_pagar_vencido)} lançamento(s)",
            "pill_classe": "pill-red",
        },
        {
            "icone": "receber",
            "label": "A receber (previsto)",
            "valor": moeda(sum(p["valor"] for p in a_receber)),
            "pill_texto": f"{len(a_receber)} lançamento(s)",
            "pill_classe": "pill-neutral",
        },
        {
            "icone": "receber",
            "cor": "#0ca30c",
            "label": "A receber vencido",
            "valor": moeda(sum(p["valor"] for p in a_receber_vencido)),
            "pill_texto": f"{len(a_receber_vencido)} lançamento(s)",
            "pill_classe": "pill-red" if a_receber_vencido else "pill-green",
        },
    ]
)

st.divider()

lotes = client.table("lotes_comissao").select("status, valor_liquido").execute().data or []
por_status = {"pendente": [], "conciliado": [], "divergente": []}
for l in lotes:
    por_status.setdefault(l["status"], []).append(l)

col_grafico, col_donut = st.columns([2, 1])

with col_grafico:
    st.markdown("##### Fluxo de caixa")
    st.caption("Últimos 6 meses — Receitas x Despesas (extratos OFX importados)")

    inicio_periodo = (hoje.replace(day=1) - timedelta(days=150)).isoformat()
    transacoes_periodo = (
        client.table("ofx_transacoes").select("data, valor").gte("data", inicio_periodo).execute().data or []
    )
    por_mes: dict[str, dict[str, float]] = {}
    cursor = hoje.replace(day=1)
    ordem_meses = []
    for _ in range(6):
        chave = cursor.strftime("%Y-%m")
        ordem_meses.append(chave)
        por_mes[chave] = {"receitas": 0.0, "despesas": 0.0}
        cursor = (cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    ordem_meses.reverse()

    for t in transacoes_periodo:
        chave = t["data"][:7]
        if chave in por_mes:
            if t["valor"] >= 0:
                por_mes[chave]["receitas"] += t["valor"]
            else:
                por_mes[chave]["despesas"] += abs(t["valor"])

    nomes_mes = {
        "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr", "05": "Mai", "06": "Jun",
        "07": "Jul", "08": "Ago", "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
    }
    labels_meses = [nomes_mes[chave[5:7]] for chave in ordem_meses]
    receitas_mes = [por_mes[chave]["receitas"] for chave in ordem_meses]
    despesas_mes = [por_mes[chave]["despesas"] for chave in ordem_meses]

    st.markdown(grafico_fluxo_caixa(labels_meses, receitas_mes, despesas_mes), unsafe_allow_html=True)

with col_donut:
    st.markdown("##### Comissões por status")
    st.caption("Lotes importados")
    st.markdown(
        grafico_donut_status(
            [
                ("Conciliadas", len(por_status["conciliado"]), "#0ca30c"),
                ("Pendentes", len(por_status["pendente"]), "#fab219"),
                ("Divergentes", len(por_status["divergente"]), "#d03b3b"),
            ],
            total_label="lotes",
        ),
        unsafe_allow_html=True,
    )

st.divider()

alertas = client.table("auditoria_alertas").select("id, tipo, descricao, created_at").eq("resolvido", False).order("created_at", desc=True).execute().data or []
if alertas:
    st.subheader(f"⚠️ {len(alertas)} alerta(s) de auditoria não resolvido(s)")
    st.dataframe(
        [{"Data": data_br(a["created_at"]), "Tipo": a["tipo"], "Descrição": a["descricao"]} for a in alertas],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Veja e resolva em **Alertas**.")
    st.divider()

n_empresas = len(client.table("empresas").select("id").execute().data or [])
n_contas = len(client.table("contas_bancarias").select("id").execute().data or [])
n_clientes = len(client.table("clientes").select("id").execute().data or [])

layout.cartoes_kpi(
    [
        {"icone": "maleta", "label": "Empresas", "valor": str(n_empresas)},
        {"icone": "banco", "label": "Contas bancárias", "valor": str(n_contas)},
        {"icone": "usuarios", "label": "Clientes cadastrados", "valor": str(n_clientes)},
    ]
)

st.caption("Ver [PLANO.md](.) para escopo completo, modelo de dados e cronograma.")
