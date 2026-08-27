import streamlit as st

from db import get_client

st.set_page_config(page_title="Configurações", layout="wide")
st.title("Configurações")
st.caption("Cadastro direto de Empresas, Contas Bancárias, Clientes, Fornecedores e Plano de Contas.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

(
    aba_empresas,
    aba_contas_bancarias,
    aba_clientes,
    aba_fornecedores,
    aba_plano_contas,
    aba_regras_comissao,
) = st.tabs(
    ["Empresas", "Contas Bancárias", "Clientes", "Fornecedores", "Plano de Contas", "Regras de Comissão"]
)

with aba_empresas:
    st.subheader("Nova empresa")
    st.caption("Ex.: Phoenix, Vizentim. Cada conta bancária é vinculada a uma empresa.")
    with st.form("nova_empresa", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome_empresa = col1.text_input("Nome da empresa")
        cnpj = col2.text_input(
            "CNPJ (opcional)", help="Usado para identificar automaticamente a empresa em demonstrativos de comissão."
        )
        if st.form_submit_button("Cadastrar empresa"):
            if not nome_empresa.strip():
                st.warning("Informe um nome.")
            else:
                try:
                    client.table("empresas").insert(
                        {"nome": nome_empresa.strip(), "cnpj": cnpj.strip() or None}
                    ).execute()
                    st.success(f"Empresa '{nome_empresa}' cadastrada.")
                except Exception as e:
                    st.error(f"Erro ao cadastrar: {e}")

    st.divider()
    st.subheader("Empresas cadastradas")
    empresas_todas = client.table("empresas").select("nome, cnpj, susep").order("nome").execute().data or []
    if empresas_todas:
        st.dataframe(empresas_todas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma empresa cadastrada ainda.")

with aba_contas_bancarias:
    st.subheader("Nova conta bancária")
    st.caption("Banco + agência + conta identificam automaticamente a empresa ao importar um OFX.")
    empresas = client.table("empresas").select("id, nome").order("nome").execute().data or []
    if not empresas:
        st.warning("Cadastre ao menos uma empresa (aba Empresas) antes de adicionar contas bancárias.")
    else:
        nomes_por_id_emp = {e["id"]: e["nome"] for e in empresas}
        with st.form("nova_conta_bancaria", clear_on_submit=True):
            empresa_id_conta = st.selectbox(
                "Empresa", options=list(nomes_por_id_emp.keys()), format_func=lambda i: nomes_por_id_emp[i]
            )
            col1, col2, col3 = st.columns(3)
            banco = col1.text_input("Banco (código)", placeholder="756")
            agencia = col2.text_input("Agência", placeholder="4406-7")
            conta = col3.text_input("Conta", placeholder="4928-0")
            if st.form_submit_button("Cadastrar conta"):
                if not (banco.strip() and agencia.strip() and conta.strip()):
                    st.warning("Preencha banco, agência e conta.")
                else:
                    try:
                        client.table("contas_bancarias").insert(
                            {
                                "empresa_id": empresa_id_conta,
                                "banco": banco.strip(),
                                "agencia": agencia.strip(),
                                "conta": conta.strip(),
                            }
                        ).execute()
                        st.success(f"Conta {conta} cadastrada para {nomes_por_id_emp[empresa_id_conta]}.")
                    except Exception as e:
                        st.error(f"Erro ao cadastrar (verifique se essa conta já existe): {e}")

    st.divider()
    st.subheader("Contas cadastradas")
    contas_todas = (
        client.table("contas_bancarias").select("banco, agencia, conta, empresas(nome)").order("banco").execute().data
        or []
    )
    if contas_todas:
        st.dataframe(
            [
                {
                    "Empresa": (c.get("empresas") or {}).get("nome", "?"),
                    "Banco": c["banco"],
                    "Agência": c["agencia"],
                    "Conta": c["conta"],
                }
                for c in contas_todas
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma conta cadastrada ainda.")

with aba_clientes:
    st.subheader("Novo cliente")
    empresas_cli = client.table("empresas").select("id, nome").order("nome").execute().data or []
    empresas_por_id = {e["id"]: e["nome"] for e in empresas_cli}

    with st.form("novo_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome")
        documento = col2.text_input("CPF/CNPJ (opcional)")
        empresa_principal_id = st.selectbox(
            "Empresa principal (opcional)",
            options=["(nenhuma)"] + list(empresas_por_id.keys()),
            format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else empresas_por_id[i],
        )
        if st.form_submit_button("Cadastrar cliente"):
            if not nome.strip():
                st.warning("Informe um nome.")
            else:
                client.table("clientes").insert(
                    {
                        "nome": nome.strip(),
                        "documento": documento.strip() or None,
                        "empresa_principal_id": None if empresa_principal_id == "(nenhuma)" else empresa_principal_id,
                    }
                ).execute()
                st.success(f"Cliente '{nome}' cadastrado.")

    st.divider()
    st.subheader("Clientes cadastrados")
    clientes = client.table("clientes").select("nome, documento, empresas(nome)").order("nome").execute().data or []
    if clientes:
        st.dataframe(
            [
                {"Nome": c["nome"], "Documento": c.get("documento") or "-", "Empresa principal": (c.get("empresas") or {}).get("nome", "-")}
                for c in clientes
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum cliente cadastrado ainda.")

with aba_fornecedores:
    st.subheader("Novo fornecedor")
    with st.form("novo_fornecedor", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nome_f = col1.text_input("Nome", key="nome_fornecedor")
        documento_f = col2.text_input("CPF/CNPJ (opcional)", key="doc_fornecedor")
        if st.form_submit_button("Cadastrar fornecedor"):
            if not nome_f.strip():
                st.warning("Informe um nome.")
            else:
                client.table("fornecedores").insert(
                    {"nome": nome_f.strip(), "documento": documento_f.strip() or None}
                ).execute()
                st.success(f"Fornecedor '{nome_f}' cadastrado.")

    st.divider()
    st.subheader("Fornecedores cadastrados")
    fornecedores = client.table("fornecedores").select("nome, documento").order("nome").execute().data or []
    if fornecedores:
        st.dataframe(
            [{"Nome": f["nome"], "Documento": f.get("documento") or "-"} for f in fornecedores],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum fornecedor cadastrado ainda.")

with aba_plano_contas:
    st.subheader("Nova conta")
    contas_existentes = client.table("plano_contas").select("id, codigo, nome").order("codigo").execute().data or []
    contas_por_id = {c["id"]: f'{c["codigo"]} — {c["nome"]}' for c in contas_existentes}

    with st.form("nova_conta_plano", clear_on_submit=True):
        col1, col2 = st.columns(2)
        codigo = col1.text_input("Código", placeholder="ex.: 5.1.6")
        nome_conta = col2.text_input("Nome da conta")
        col3, col4 = st.columns(2)
        tipo = col3.selectbox("Tipo", options=["ativo", "passivo", "patrimonio_liquido", "receita", "despesa"])
        conta_pai_id = col4.selectbox(
            "Conta pai (opcional)",
            options=["(nenhuma)"] + list(contas_por_id.keys()),
            format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else contas_por_id[i],
        )
        if st.form_submit_button("Cadastrar conta"):
            if not codigo.strip() or not nome_conta.strip():
                st.warning("Informe código e nome.")
            else:
                try:
                    client.table("plano_contas").insert(
                        {
                            "codigo": codigo.strip(),
                            "nome": nome_conta.strip(),
                            "tipo": tipo,
                            "conta_pai_id": None if conta_pai_id == "(nenhuma)" else conta_pai_id,
                        }
                    ).execute()
                    st.success(f"Conta '{codigo} — {nome_conta}' cadastrada.")
                except Exception as e:
                    st.error(f"Erro ao cadastrar (código já existe?): {e}")

    st.divider()
    st.subheader("Plano de contas")
    if contas_existentes:
        todas_contas = client.table("plano_contas").select("codigo, nome, tipo").order("codigo").execute().data or []
        st.dataframe(
            [{"Código": c["codigo"], "Nome": c["nome"], "Tipo": c["tipo"]} for c in todas_contas],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma conta cadastrada ainda.")

with aba_regras_comissao:
    clientes_regras = client.table("clientes").select("id, nome").order("nome").execute().data or []
    if not clientes_regras:
        st.info("Nenhum cliente cadastrado ainda.")
    else:
        nomes_por_id_regras = {c["id"]: c["nome"] for c in clientes_regras}

        regras = client.table("regras_classificacao_comissao").select("*").execute().data or []
        regra_por_cliente = {r["cliente_id"]: r for r in regras}

        st.header("Vitalício (Saúde/Vida)")
        st.caption(
            "Define, por cliente, quantas das primeiras parcelas são agenciamento (comissão de "
            "entrada, % alto) — da parcela seguinte em diante, o sistema classifica como vitalícia "
            "(recorrente) e já provisiona receita futura esperada em Contas a Pagar e Receber."
        )
        st.subheader("Cadastrar / atualizar regra")
        cliente_id_regra = st.selectbox(
            "Cliente", options=list(nomes_por_id_regras.keys()), format_func=lambda i: nomes_por_id_regras[i]
        )
        existente = regra_por_cliente.get(cliente_id_regra)

        col1, col2 = st.columns(2)
        parcelas_agenciamento = col1.number_input(
            "Quantas primeiras parcelas são agenciamento",
            min_value=0, step=1,
            value=existente["parcelas_agenciamento"] if existente else 3,
        )
        meses_provisionar = col2.number_input(
            "Provisionar quantos meses à frente quando for vitalício",
            min_value=1, max_value=200, step=1,
            value=existente["meses_provisionar"] if existente else 24,
            help="Saúde costuma ficar por volta de 24; vida (renovação anual) pode passar de 100.",
        )
        col3, col4 = st.columns(2)
        percentual_agenciamento = col3.number_input(
            "% comissão no agenciamento (referência)", min_value=0.0, max_value=100.0, step=0.01,
            value=float(existente["percentual_agenciamento"]) if existente and existente.get("percentual_agenciamento") else 0.0,
        )
        percentual_vitalicio = col4.number_input(
            "% comissão vitalícia (referência)", min_value=0.0, max_value=100.0, step=0.01,
            value=float(existente["percentual_vitalicio"]) if existente and existente.get("percentual_vitalicio") else 0.0,
        )

        if st.button("Salvar regra", type="primary", key="salvar_regra_vitalicio"):
            dados = {
                "cliente_id": cliente_id_regra,
                "parcelas_agenciamento": int(parcelas_agenciamento),
                "percentual_agenciamento": percentual_agenciamento or None,
                "percentual_vitalicio": percentual_vitalicio or None,
                "meses_provisionar": int(meses_provisionar),
            }
            if existente:
                client.table("regras_classificacao_comissao").update(dados).eq("id", existente["id"]).execute()
            else:
                client.table("regras_classificacao_comissao").insert(dados).execute()
            st.success("Regra salva.")
            st.rerun()

        st.divider()
        st.subheader("Regras cadastradas")
        if regras:
            st.dataframe(
                [
                    {
                        "Cliente": nomes_por_id_regras.get(r["cliente_id"], "?"),
                        "Parcelas agenciamento": r["parcelas_agenciamento"],
                        "% agenciamento": r.get("percentual_agenciamento"),
                        "% vitalício": r.get("percentual_vitalicio"),
                        "Meses a provisionar": r["meses_provisionar"],
                    }
                    for r in regras
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma regra cadastrada ainda.")

        st.divider()
        st.header("Parcelamento (Auto/RE)")
        st.caption(
            "Define, por apólice, o número total de parcelas esperadas. Ao chegar uma comissão de "
            "uma parcela, se ainda faltam parcelas, o sistema provisiona as restantes como receita "
            "futura (mesmo valor da última observada), atualizando sozinho quando a próxima chegar de verdade."
        )

        regras_parc = client.table("regras_parcelamento").select("*, clientes(nome)").execute().data or []

        st.subheader("Cadastrar / atualizar regra")
        col1, col2, col3 = st.columns(3)
        apolice_parc = col1.text_input("Número da apólice")
        cliente_parc_id = col2.selectbox(
            "Cliente (opcional, só referência)",
            options=["(nenhum)"] + list(nomes_por_id_regras.keys()),
            format_func=lambda i: "(nenhum)" if i == "(nenhum)" else nomes_por_id_regras[i],
        )
        total_parcelas = col3.number_input("Total de parcelas da apólice", min_value=1, step=1, value=12)

        if st.button("Salvar regra de parcelamento", type="primary", disabled=not apolice_parc.strip()):
            dados = {
                "apolice": apolice_parc.strip(),
                "cliente_id": None if cliente_parc_id == "(nenhum)" else cliente_parc_id,
                "total_parcelas": int(total_parcelas),
            }
            existente_parc = next((r for r in regras_parc if r["apolice"] == apolice_parc.strip()), None)
            if existente_parc:
                client.table("regras_parcelamento").update(dados).eq("id", existente_parc["id"]).execute()
            else:
                client.table("regras_parcelamento").insert(dados).execute()
            st.success("Regra de parcelamento salva.")
            st.rerun()

        st.divider()
        st.subheader("Regras de parcelamento cadastradas")
        if regras_parc:
            st.dataframe(
                [
                    {
                        "Apólice": r["apolice"],
                        "Cliente": (r.get("clientes") or {}).get("nome", "-"),
                        "Total de parcelas": r["total_parcelas"],
                    }
                    for r in regras_parc
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Nenhuma regra de parcelamento cadastrada ainda.")
