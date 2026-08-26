import uuid
from datetime import date

import streamlit as st

from db import get_client
from lancamentos import ParcelaGerada, gerar_parcelas, gerar_recorrencia

st.set_page_config(page_title="Contas a Pagar e Receber", layout="wide")
st.title("Contas a Pagar e Receber")
st.caption(
    "Lançamentos previstos — antes de acontecer no banco. Avulso, parcelado ou fixo/recorrente. "
    "Quando o crédito/débito correspondente aparecer no OFX, o sistema concilia sozinho."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

empresas = client.table("empresas").select("id, nome").order("nome").execute().data or []
if not empresas:
    st.error("Cadastre ao menos uma empresa em **Empresas** antes de continuar.")
    st.stop()
empresas_por_id = {e["id"]: e["nome"] for e in empresas}

clientes = client.table("clientes").select("id, nome").order("nome").execute().data or []
fornecedores = client.table("fornecedores").select("id, nome").order("nome").execute().data or []
contas_plano = client.table("plano_contas").select("id, codigo, nome").order("codigo").execute().data or []
contas_bancarias = (
    client.table("contas_bancarias").select("id, banco, agencia, conta").order("conta").execute().data or []
)

st.subheader("Novo lançamento")
tipo_label = st.radio("Tipo", ["Pagar (despesa)", "Receber (receita)"], horizontal=True)
tipo = "pagar" if tipo_label.startswith("Pagar") else "receber"

col1, col2 = st.columns(2)
empresa_id = col1.selectbox("Empresa", options=list(empresas_por_id.keys()), format_func=lambda i: empresas_por_id[i])
descricao = col2.text_input("Descrição", placeholder="Aluguel do escritório" if tipo == "pagar" else "Comissão prevista")

col3, col4 = st.columns(2)
if tipo == "pagar":
    opcoes_fornecedor = ["(nenhum)", "+ Novo fornecedor"] + [f["id"] for f in fornecedores]
    nomes_fornecedor = {f["id"]: f["nome"] for f in fornecedores}
    escolha_terceiro = col3.selectbox(
        "Fornecedor",
        options=opcoes_fornecedor,
        format_func=lambda i: i if i in ("(nenhum)", "+ Novo fornecedor") else nomes_fornecedor[i],
    )
    novo_terceiro_nome = col3.text_input("Nome do novo fornecedor") if escolha_terceiro == "+ Novo fornecedor" else None
else:
    opcoes_terceiro = ["(nenhum)", "+ Novo cliente"] + [c["id"] for c in clientes]
    nomes_cliente = {c["id"]: c["nome"] for c in clientes}
    escolha_terceiro = col3.selectbox(
        "Cliente",
        options=opcoes_terceiro,
        format_func=lambda i: i if i in ("(nenhum)", "+ Novo cliente") else nomes_cliente[i],
    )
    novo_terceiro_nome = col3.text_input("Nome do novo cliente") if escolha_terceiro == "+ Novo cliente" else None

contas_opcoes = {c["id"]: f'{c["codigo"]} — {c["nome"]}' for c in contas_plano}
plano_conta_id = col4.selectbox(
    "Conta do plano de contas", options=["(nenhuma)"] + list(contas_opcoes.keys()),
    format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else contas_opcoes[i],
)

conta_bancaria_opcoes = {c["id"]: f'{c["banco"]}/{c["agencia"]}/{c["conta"]}' for c in contas_bancarias}
conta_bancaria_id = st.selectbox(
    "Conta bancária esperada (opcional)",
    options=["(nenhuma)"] + list(conta_bancaria_opcoes.keys()),
    format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else conta_bancaria_opcoes[i],
)

modo = st.radio("Como é esse lançamento?", ["Avulso", "Parcelado", "Fixo (recorrente todo mês)"], horizontal=True)

parcelas_preview = []
if modo == "Avulso":
    c1, c2 = st.columns(2)
    valor = c1.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
    data_vencimento = c2.date_input("Data de vencimento", value=date.today())
    if valor > 0:
        parcelas_preview = [
            ParcelaGerada(parcela_atual=None, parcela_total=None, valor=valor, data_vencimento=data_vencimento)
        ]
elif modo == "Parcelado":
    c1, c2, c3 = st.columns(3)
    valor_total = c1.number_input("Valor total (R$)", min_value=0.0, step=0.01, format="%.2f")
    num_parcelas = c2.number_input("Número de parcelas", min_value=1, step=1, value=2)
    data_primeira = c3.date_input("Vencimento da 1ª parcela", value=date.today())
    if valor_total > 0:
        parcelas_preview = gerar_parcelas(valor_total, int(num_parcelas), data_primeira)
else:
    c1, c2, c3 = st.columns(3)
    valor_mensal = c1.number_input("Valor mensal (R$)", min_value=0.0, step=0.01, format="%.2f")
    data_primeiro_vencimento = c2.date_input("1º vencimento", value=date.today())
    meses_a_gerar = c3.number_input("Gerar quantos meses à frente?", min_value=1, step=1, value=12)
    if valor_mensal > 0:
        parcelas_preview = gerar_recorrencia(valor_mensal, data_primeiro_vencimento, int(meses_a_gerar))

if parcelas_preview:
    st.caption(f"Prévia: {len(parcelas_preview)} lançamento(s) serão criados.")
    st.dataframe(
        [{"Parcela": f"{p.parcela_atual}/{p.parcela_total}" if p.parcela_atual else "-", "Vencimento": p.data_vencimento, "Valor": p.valor} for p in parcelas_preview],
        use_container_width=True,
        hide_index=True,
    )

if st.button("Cadastrar", type="primary", disabled=not parcelas_preview or not descricao.strip()):
    cliente_id = fornecedor_id = None
    if escolha_terceiro == "+ Novo fornecedor" and novo_terceiro_nome and novo_terceiro_nome.strip():
        fornecedor_id = client.table("fornecedores").insert({"nome": novo_terceiro_nome.strip()}).execute().data[0]["id"]
    elif escolha_terceiro == "+ Novo cliente" and novo_terceiro_nome and novo_terceiro_nome.strip():
        cliente_id = client.table("clientes").insert({"nome": novo_terceiro_nome.strip()}).execute().data[0]["id"]
    elif escolha_terceiro not in ("(nenhum)", "+ Novo fornecedor", "+ Novo cliente"):
        if tipo == "pagar":
            fornecedor_id = escolha_terceiro
        else:
            cliente_id = escolha_terceiro

    grupo_id = str(uuid.uuid4())
    for p in parcelas_preview:
        client.table("lancamentos_previstos").insert(
            {
                "empresa_id": empresa_id,
                "tipo": tipo,
                "descricao": descricao.strip(),
                "valor": p.valor,
                "data_vencimento": p.data_vencimento.isoformat(),
                "status": "previsto",
                "cliente_id": cliente_id,
                "fornecedor_id": fornecedor_id,
                "plano_conta_id": None if plano_conta_id == "(nenhuma)" else plano_conta_id,
                "conta_bancaria_id": None if conta_bancaria_id == "(nenhuma)" else conta_bancaria_id,
                "grupo_id": grupo_id,
                "parcela_atual": p.parcela_atual,
                "parcela_total": p.parcela_total,
                "recorrente": p.recorrente,
            }
        ).execute()
    st.success(f"{len(parcelas_preview)} lançamento(s) cadastrado(s).")

st.divider()


def _tabela(tipo_filtro: str, titulo: str):
    st.subheader(titulo)
    itens = (
        client.table("lancamentos_previstos")
        .select("id, descricao, valor, data_vencimento, status, clientes(nome), fornecedores(nome)")
        .eq("tipo", tipo_filtro)
        .in_("status", ["previsto", "pago"])
        .order("data_vencimento")
        .execute()
        .data
        or []
    )
    if not itens:
        st.info("Nenhum lançamento.")
        return

    hoje = date.today().isoformat()
    linhas = []
    for item in itens:
        situacao = item["status"]
        if situacao == "previsto" and item["data_vencimento"] < hoje:
            situacao = "atrasado"
        terceiro = (item.get("clientes") or {}).get("nome") or (item.get("fornecedores") or {}).get("nome") or "-"
        linhas.append(
            {
                "Vencimento": item["data_vencimento"],
                "Descrição": item["descricao"],
                "Cliente/Fornecedor": terceiro,
                "Valor": item["valor"],
                "Situação": situacao,
            }
        )
    st.dataframe(linhas, use_container_width=True, hide_index=True)

    pendentes = [i for i in itens if i["status"] == "previsto"]
    if pendentes:
        opcoes = {i["id"]: f"{i['data_vencimento']} — {i['descricao']} — R$ {i['valor']:.2f}" for i in pendentes}
        col_a, col_b, col_c = st.columns([3, 1, 1])
        selecionado = col_a.selectbox("Ação rápida em:", options=list(opcoes.keys()), format_func=lambda i: opcoes[i], key=f"sel_{tipo_filtro}")
        if col_b.button("Marcar como pago", key=f"pago_{tipo_filtro}"):
            client.table("lancamentos_previstos").update(
                {"status": "pago", "data_pagamento": date.today().isoformat()}
            ).eq("id", selecionado).execute()
            st.success("Marcado como pago.")
            st.rerun()
        if col_c.button("Cancelar", key=f"cancelar_{tipo_filtro}"):
            client.table("lancamentos_previstos").update({"status": "cancelado"}).eq("id", selecionado).execute()
            st.success("Cancelado.")
            st.rerun()


_tabela("pagar", "Contas a Pagar")
st.divider()
_tabela("receber", "Contas a Receber")
