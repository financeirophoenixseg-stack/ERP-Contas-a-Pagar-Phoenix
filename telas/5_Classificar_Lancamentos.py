import html

import streamlit as st

import layout
from db import get_client
from formatacao import data_br, moeda
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
nomes_clientes = {c["id"]: c["nome"] for c in clientes}
nomes_fornecedores = {f["id"]: f["nome"] for f in fornecedores}


def _salvar_classificacao(txn_id, cliente_id, fornecedor_id, plano_conta_id, padrao, novo_nome=None, tipo_novo=None):
    if novo_nome:
        if tipo_novo == "cliente":
            cliente_id = client.table("clientes").insert({"nome": novo_nome.strip()}).execute().data[0]["id"]
        else:
            fornecedor_id = (
                client.table("fornecedores").insert({"nome": novo_nome.strip()}).execute().data[0]["id"]
            )

    client.table("ofx_transacoes").update(
        {"cliente_id": cliente_id, "fornecedor_id": fornecedor_id, "plano_conta_id": plano_conta_id}
    ).eq("id", txn_id).execute()

    if padrao and padrao.strip():
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


st.markdown(
    layout._compacto(
        f"""
        <div class="card" style="padding:14px 20px;margin-bottom:6px;">
          <span style="font-size:13.5px;color:#5B6B85;font-weight:600;">{len(pendentes)} lançamento(s) pendente(s) de classificação</span>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

for txn in pendentes:
    conta_bancaria = txn.get("contas_bancarias") or {}
    empresa_nome = (conta_bancaria.get("empresas") or {}).get("nome", "?")
    sugestao = sugerir(regras, txn["descricao"])
    manual_key = f"manual_{txn['id']}"
    manual_ativo = st.session_state.get(manual_key, False)

    with st.container(border=True):
        cor_valor = "#0ca30c" if txn["valor"] >= 0 else "#10233F"
        st.markdown(
            layout._compacto(
                f"""
                <div style="display:flex;align-items:center;justify-content:space-between;padding:2px 2px 10px 2px;">
                  <div style="display:flex;align-items:center;gap:12px;">
                    <div class="kpi-icon" style="background:rgba(30,95,191,0.09);color:#1E5FBF;">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{layout.ICONES['banco']}</svg>
                    </div>
                    <div>
                      <div style="font-size:13.5px;font-weight:600;color:#10233F;">{html.escape(txn['descricao'] or 'sem descrição')}</div>
                      <div style="font-size:12px;color:#8592A8;margin-top:1px;">{data_br(txn['data'])} · {html.escape(empresa_nome)}</div>
                    </div>
                  </div>
                  <span style="font-family:'Manrope',sans-serif;font-weight:700;font-size:15px;color:{cor_valor};">{'+' if txn['valor'] >= 0 else ''}{moeda(txn['valor'])}</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        if sugestao and not manual_ativo:
            if sugestao.get("cliente_id") and sugestao["cliente_id"] in nomes_clientes:
                quem = f"Cliente: {nomes_clientes[sugestao['cliente_id']]}"
            elif sugestao.get("fornecedor_id") and sugestao["fornecedor_id"] in nomes_fornecedores:
                quem = f"Fornecedor: {nomes_fornecedores[sugestao['fornecedor_id']]}"
            else:
                quem = "—"
            conta_txt = contas_opcoes.get(sugestao.get("plano_conta_id"), "—")

            st.markdown(
                layout._compacto(
                    f"""
                    <div style="background:rgba(30,95,191,0.05);border:1px solid rgba(30,95,191,0.15);border-radius:10px;padding:12px 14px;margin-bottom:10px;">
                      <span class="pill pill-blue" style="margin-bottom:6px;">Sugestão automática</span>
                      <div style="font-size:13px;color:#10233F;margin-top:6px;">{html.escape(quem)} — {html.escape(conta_txt)}</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
            col_usar, col_manual, _ = st.columns([1, 1, 2])
            if col_usar.button("Usar sugestão", key=f"usar_{txn['id']}", type="primary"):
                _salvar_classificacao(
                    txn["id"],
                    sugestao.get("cliente_id"),
                    sugestao.get("fornecedor_id"),
                    sugestao.get("plano_conta_id"),
                    padrao=None,
                )
                st.success("Classificado a partir da sugestão!")
                st.rerun()
            if col_manual.button("Classificar manual", key=f"manual_btn_{txn['id']}"):
                st.session_state[manual_key] = True
                st.rerun()
        else:
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
            novo_nome = None
            if tipo.startswith("Cliente"):
                opcoes = ["+ Novo cliente"] + list(nomes_clientes.keys())
                default_idx = (
                    (list(nomes_clientes.keys()).index(sugestao["cliente_id"]) + 1)
                    if sugestao and sugestao.get("cliente_id") in nomes_clientes
                    else 0
                )
                escolha = st.selectbox(
                    "Cliente",
                    options=opcoes,
                    format_func=lambda i: "+ Novo cliente" if i == "+ Novo cliente" else nomes_clientes[i],
                    index=default_idx,
                    key=f"cliente_{txn['id']}",
                )
                if escolha == "+ Novo cliente":
                    novo_nome = st.text_input("Nome do novo cliente", key=f"novo_cliente_{txn['id']}")
                else:
                    cliente_id = escolha
            else:
                opcoes = ["+ Novo fornecedor"] + list(nomes_fornecedores.keys())
                default_idx = (
                    (list(nomes_fornecedores.keys()).index(sugestao["fornecedor_id"]) + 1)
                    if sugestao and sugestao.get("fornecedor_id") in nomes_fornecedores
                    else 0
                )
                escolha = st.selectbox(
                    "Fornecedor",
                    options=opcoes,
                    format_func=lambda i: "+ Novo fornecedor" if i == "+ Novo fornecedor" else nomes_fornecedores[i],
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

            padrao = st.text_input(
                "Padrão para identificar lançamentos parecidos automaticamente",
                value=txn["descricao"] or "",
                key=f"padrao_{txn['id']}",
                help="Se a descrição de um lançamento futuro contiver este texto, a classificação será sugerida sozinha.",
            )

            if st.button("Salvar classificação", key=f"salvar_{txn['id']}", type="primary"):
                if tipo.startswith("Cliente") and cliente_id is None:
                    if not (novo_nome or "").strip():
                        st.warning("Informe o nome do novo cliente.")
                        st.stop()
                elif tipo.startswith("Fornecedor") and fornecedor_id is None:
                    if not (novo_nome or "").strip():
                        st.warning("Informe o nome do novo fornecedor.")
                        st.stop()

                _salvar_classificacao(
                    txn["id"],
                    cliente_id,
                    fornecedor_id,
                    plano_conta_id,
                    padrao,
                    novo_nome=novo_nome,
                    tipo_novo="cliente" if tipo.startswith("Cliente") else "fornecedor",
                )
                st.session_state.pop(manual_key, None)
                st.success("Classificado! Atualizando a lista...")
                st.rerun()
