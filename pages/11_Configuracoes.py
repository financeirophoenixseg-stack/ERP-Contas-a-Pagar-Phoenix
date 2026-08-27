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

aba_empresas, aba_contas_bancarias, aba_clientes, aba_fornecedores, aba_plano_contas = st.tabs(
    ["Empresas", "Contas Bancárias", "Clientes", "Fornecedores", "Plano de Contas"]
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
