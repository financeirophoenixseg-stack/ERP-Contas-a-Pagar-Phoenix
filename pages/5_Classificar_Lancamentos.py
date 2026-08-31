import streamlit as st

import layout
from db import get_client
from formatacao import moeda
from regras_identificacao import sugerir

st.set_page_config(page_title="Classificar Lançamentos", layout="wide")
layout.aplicar_logo()
st.title("Classificar lançamentos")
st.caption(
    "Transações bancárias que não bateram com nenhuma comissão. Classifique como "
    "cliente (recebimento) ou fornecedor (pagamento) e escolha a conta do plano de "
    "contas — os próximos lançamentos parecidos serão sugeridos automaticamente."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

pendentes = (
    client.table("ofx_transacoes")
    .select("*, contas_bancarias(banco, agencia, conta, empresas(nome))")
    .eq("conciliado", False)
    .is_("cliente_id", "null")
    .is_("fornecedor_id", "null")
    .is_("plano_conta_id", "null")
    .order("data")
    .execute()
    .data
    or []
)

if not pendentes:
    st.success("Nenhum lançamento pendente de classificação.")
    st.stop()

clientes = client.table("clientes").select("id, nome").order("nome").execute().data or []
fornecedores = client.table("fornecedores").select("id, nome").order("nome").execute().data or []
contas = client.table("plano_contas").select("id, codigo, nome").order("codigo").execute().data or []
regras = client.table("regras_identificacao").select("*").execute().data or []

contas_opcoes = {c["id"]: f'{c["codigo"]} — {c["nome"]}' for c in contas}


st.caption(f"{len(pendentes)} lançamento(s) pendente(s).")

for txn in pendentes:
    conta_bancaria = txn.get("contas_bancarias") or {}
    empresa_nome = (conta_bancaria.get("empresas") or {}).get("nome", "?")
    titulo = f"{txn['data']} — {moeda(txn['valor'])} — {txn['descricao'] or 'sem descrição'} ({empresa_nome})"

    with st.expander(titulo):
        sugestao = sugerir(regras, txn["descricao"])
        if sugestao:
            st.info(
                "Sugestão automática (baseada em lançamento anterior parecido) já aplicada abaixo — "
                "confira e clique em Salvar."
            )

        tipo_default = 0
        if sugestao and sugestao.get("fornecedor_id"):
            tipo_default = 1
        tipo = st.radio(
            "Tipo",
            ["Cliente (recebimento)", "Fornecedor (pagamento)"],
            index=tipo_default,
            key=f"tipo_{txn['id']}",
            horizontal=True,
        )

        cliente_id = fornecedor_id = None
        if tipo.startswith("Cliente"):
            nomes = {c["id"]: c["nome"] for c in clientes}
            opcoes = ["+ Novo cliente"] + list(nomes.keys())
            default_idx = (
                (list(nomes.keys()).index(sugestao["cliente_id"]) + 1)
                if sugestao and sugestao.get("cliente_id") in nomes
                else 0
            )
            escolha = st.selectbox(
                "Cliente",
                options=opcoes,
                format_func=lambda i: "+ Novo cliente" if i == "+ Novo cliente" else nomes[i],
                index=default_idx,
                key=f"cliente_{txn['id']}",
            )
            if escolha == "+ Novo cliente":
                novo_nome = st.text_input("Nome do novo cliente", key=f"novo_cliente_{txn['id']}")
            else:
                cliente_id = escolha
        else:
            nomes = {f["id"]: f["nome"] for f in fornecedores}
            opcoes = ["+ Novo fornecedor"] + list(nomes.keys())
            default_idx = (
                (list(nomes.keys()).index(sugestao["fornecedor_id"]) + 1)
                if sugestao and sugestao.get("fornecedor_id") in nomes
                else 0
            )
            escolha = st.selectbox(
                "Fornecedor",
                options=opcoes,
                format_func=lambda i: "+ Novo fornecedor" if i == "+ Novo fornecedor" else nomes[i],
                index=default_idx,
                key=f"fornecedor_{txn['id']}",
            )
            if escolha == "+ Novo fornecedor":
                novo_nome = st.text_input("Nome do novo fornecedor", key=f"novo_fornecedor_{txn['id']}")
            else:
                fornecedor_id = escolha

        contas_ids = list(contas_opcoes.keys())
        default_conta_idx = (
            contas_ids.index(sugestao["plano_conta_id"])
            if sugestao and sugestao.get("plano_conta_id") in contas_ids
            else 0
        )
        plano_conta_id = st.selectbox(
            "Conta do plano de contas",
            options=contas_ids,
            format_func=lambda i: contas_opcoes[i],
            index=default_conta_idx,
            key=f"conta_{txn['id']}",
        )

        padrao_sugerido = txn["descricao"] or ""
        padrao = st.text_input(
            "Padrão para identificar lançamentos parecidos automaticamente",
            value=padrao_sugerido,
            key=f"padrao_{txn['id']}",
            help="Se a descrição de um lançamento futuro contiver este texto, a classificação será sugerida sozinha.",
        )

        if st.button("Salvar classificação", key=f"salvar_{txn['id']}", type="primary"):
            if tipo.startswith("Cliente") and cliente_id is None:
                if not novo_nome.strip():
                    st.warning("Informe o nome do novo cliente.")
                    st.stop()
                cliente_id = client.table("clientes").insert({"nome": novo_nome.strip()}).execute().data[0]["id"]
            elif tipo.startswith("Fornecedor") and fornecedor_id is None:
                if not novo_nome.strip():
                    st.warning("Informe o nome do novo fornecedor.")
                    st.stop()
                fornecedor_id = (
                    client.table("fornecedores").insert({"nome": novo_nome.strip()}).execute().data[0]["id"]
                )

            client.table("ofx_transacoes").update(
                {
                    "cliente_id": cliente_id,
                    "fornecedor_id": fornecedor_id,
                    "plano_conta_id": plano_conta_id,
                }
            ).eq("id", txn["id"]).execute()

            if padrao.strip():
                ja_existe = (
                    client.table("regras_identificacao")
                    .select("id")
                    .ilike("padrao_descricao", padrao.strip())
                    .execute()
                    .data
                )
                if not ja_existe:
                    client.table("regras_identificacao").insert(
                        {
                            "padrao_descricao": padrao.strip(),
                            "cliente_id": cliente_id,
                            "fornecedor_id": fornecedor_id,
                            "plano_conta_id": plano_conta_id,
                        }
                    ).execute()

            st.success("Classificado! Atualize a página para ver a próxima lista.")
