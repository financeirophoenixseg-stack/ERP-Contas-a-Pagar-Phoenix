import hashlib
import uuid
from datetime import date, datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components
from postgrest.exceptions import APIError

import layout
import pluggy_integration
from conciliacao import inserir_e_conciliar
from db import get_client


def _sincronizar_conta_pluggy(client, conta_bancaria_id: str, integracao: dict) -> dict:
    """Puxa as transações da Pluggy pra essa conta e tenta conciliar
    automaticamente — mesma lógica de Importar OFX, só que a fonte é a
    API da Pluggy em vez de um arquivo .ofx. Evita duplicidade pelo id
    da transação na Pluggy (usado como fit_id, igual o FITID do OFX)."""
    account_id = integracao.get("pluggy_account_id")
    if not account_id:
        return {"erro": "Conta dentro do banco ainda não foi escolhida — desconecte e conecte de novo."}

    if integracao.get("ultima_sincronizacao"):
        dt_ultima = datetime.fromisoformat(str(integracao["ultima_sincronizacao"]).replace("Z", "+00:00"))
        desde = (dt_ultima.date() - timedelta(days=1)).isoformat()  # 1 dia de margem, evita perder transação de borda
    else:
        desde = (date.today() - timedelta(days=90)).isoformat()  # primeira sincronização: últimos 90 dias

    transacoes = pluggy_integration.listar_transacoes(account_id, desde=desde)

    hoje = date.today()
    hash_unico = hashlib.sha256(f"{account_id}-{hoje.isoformat()}-{uuid.uuid4().hex}".encode()).hexdigest()
    importacao = (
        client.table("ofx_importacoes")
        .insert(
            {
                "conta_bancaria_id": conta_bancaria_id,
                "arquivo_nome": f"Sincronização Pluggy — {hoje.isoformat()}",
                "hash_arquivo": hash_unico,
            }
        )
        .execute()
    )
    importacao_id = importacao.data[0]["id"]

    regras = client.table("regras_identificacao").select("*").execute().data or []
    inseridas = duplicadas = conciliadas = 0
    for t in transacoes:
        try:
            conciliou = inserir_e_conciliar(
                client,
                ofx_importacao_id=importacao_id,
                conta_id=conta_bancaria_id,
                fit_id=t.id,
                data=t.data,
                valor=t.valor,
                descricao=t.descricao,
                regras_identificacao=regras,
            )
            inseridas += 1
            if conciliou:
                conciliadas += 1
        except APIError as e:
            if e.code == "23505":  # unique_violation: (conta_bancaria_id, fit_id) já existe
                duplicadas += 1
            else:
                raise

    client.table("integracoes_bancarias").update(
        {"ultima_sincronizacao": datetime.now().isoformat(), "status": "ativo"}
    ).eq("id", integracao["id"]).execute()

    return {"inseridas": inseridas, "duplicadas": duplicadas, "conciliadas": conciliadas}

st.set_page_config(page_title="Configurações", layout="wide")
layout.aplicar_logo()
st.title("Configurações")
st.caption("Tudo que configura o sistema: cadastros, regras de comissão e de identificação automática.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

(
    aba_empresas,
    aba_contas_bancarias,
    aba_integracao_bancaria,
    aba_clientes,
    aba_fornecedores,
    aba_plano_contas,
    aba_regras_comissao,
    aba_regras_identificacao,
    aba_apolice_clientes,
    aba_aparencia,
) = st.tabs(
    [
        "Empresas",
        "Contas Bancárias",
        "Integração Bancária",
        "Clientes",
        "Fornecedores",
        "Plano de Contas",
        "Regras de Comissão",
        "Regras de Identificação",
        "Apólice → Cliente",
        "Aparência",
    ]
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

with aba_integracao_bancaria:
    st.subheader("Integração bancária (Open Finance, via Pluggy)")
    st.caption(
        "Conecta direto com o banco pra puxar o extrato automaticamente, sem precisar exportar/importar OFX "
        "manualmente. Usa a Pluggy como agregadora certificada de Open Finance — sua senha do banco nunca passa "
        "pelo nosso sistema, o login acontece dentro da tela oficial de consentimento do próprio banco."
    )

    if not pluggy_integration.esta_configurado():
        st.info(
            "**Ainda não configurado.** Pra ativar:\n\n"
            "1. Crie uma conta em [pluggy.ai](https://pluggy.ai) (tem plano gratuito pra poucas conexões).\n"
            "2. No painel da Pluggy, gere um **Client ID** e **Client Secret**.\n"
            "3. Adicione no arquivo `.env` do sistema:\n"
            "```\nPLUGGY_CLIENT_ID=...\nPLUGGY_CLIENT_SECRET=...\n```\n"
            "4. Reinicie o sistema (fechar e abrir `abrir.bat`) — essa tela libera sozinha."
        )
    else:
        st.warning(
            "⚠️ Nem a conexão (widget de escolher o banco e fazer login) nem a sincronização (puxar as "
            "transações) foram testadas contra uma conta real da Pluggy ainda — a lógica está pronta, mas o "
            "primeiro uso de verdade precisa ser conferido com cuidado."
        )
        contas_bancarias_todas = (
            client.table("contas_bancarias")
            .select("id, banco, agencia, conta, empresas(nome)")
            .order("banco")
            .execute()
            .data
            or []
        )
        integracoes = client.table("integracoes_bancarias").select("*").execute().data or []
        por_conta = {i["conta_bancaria_id"]: i for i in integracoes}

        if not contas_bancarias_todas:
            st.info("Cadastre uma conta bancária primeiro (aba **Contas Bancárias**).")
        else:
            for c in contas_bancarias_todas:
                integracao = por_conta.get(c["id"])
                rotulo = f"{(c.get('empresas') or {}).get('nome', '?')} — {c['banco']}/{c['agencia']}/{c['conta']}"
                status = integracao["status"] if integracao else "não conectada"
                with st.expander(f"🏦 {rotulo} — {status}"):
                    if integracao:
                        st.write(f"**Status:** {integracao['status']}")
                        st.write(f"**Última sincronização:** {integracao['ultima_sincronizacao'] or 'nunca'}")
                        col_sync, col_desc = st.columns(2)
                        if col_sync.button("🔄 Sincronizar agora", key=f"sincronizar_{c['id']}", type="primary"):
                            with st.spinner("Buscando transações na Pluggy..."):
                                try:
                                    resultado = _sincronizar_conta_pluggy(client, c["id"], integracao)
                                except Exception as e:
                                    st.error(f"Erro ao sincronizar: {e}")
                                else:
                                    if "erro" in resultado:
                                        st.error(resultado["erro"])
                                    else:
                                        msg = (
                                            f"{resultado['inseridas']} nova(s) transação(ões), "
                                            f"{resultado['duplicadas']} já existia(m)."
                                        )
                                        if resultado["conciliadas"]:
                                            msg += f" {resultado['conciliadas']} conciliada(s) automaticamente."
                                        st.success(msg)
                                        st.rerun()
                        if col_desc.button("Desconectar", key=f"desconectar_{c['id']}"):
                            client.table("integracoes_bancarias").delete().eq("id", integracao["id"]).execute()
                            st.success("Desconectado.")
                            st.rerun()
                    else:
                        if st.button("Conectar", key=f"conectar_{c['id']}"):
                            try:
                                st.session_state[f"connect_token_{c['id']}"] = pluggy_integration.criar_connect_token()
                            except Exception as e:
                                st.error(f"Erro ao gerar conexão: {e}")

                        token = st.session_state.get(f"connect_token_{c['id']}")
                        if token:
                            components.html(
                                f"""
                                <div id="pluggy-connect-{c['id']}"></div>
                                <script src="https://cdn.pluggy.ai/pluggy-connect/v3/pluggy-connect.js"></script>
                                <script>
                                  const connect = new PluggyConnect({{
                                    connectToken: "{token}",
                                    includeSandbox: false,
                                    onSuccess: (data) => {{
                                      document.getElementById('pluggy-connect-{c['id']}').innerText =
                                        'Conectado! Copie este código e cole no campo abaixo: ' + data.item.id;
                                    }},
                                    onError: (error) => {{
                                      document.getElementById('pluggy-connect-{c['id']}').innerText =
                                        'Erro: ' + JSON.stringify(error);
                                    }},
                                  }});
                                  connect.init();
                                </script>
                                """,
                                height=600,
                            )
                            item_id_colado = st.text_input(
                                "Depois de conectar, cole aqui o código (item id) que apareceu:",
                                key=f"item_id_{c['id']}",
                            )
                            if item_id_colado.strip() and st.button("Salvar conexão", key=f"salvar_conexao_{c['id']}"):
                                try:
                                    contas_pluggy = pluggy_integration.listar_contas(item_id_colado.strip())
                                except Exception as e:
                                    st.error(f"Não deu pra confirmar a conexão: {e}")
                                else:
                                    client.table("integracoes_bancarias").insert(
                                        {
                                            "conta_bancaria_id": c["id"],
                                            "pluggy_item_id": item_id_colado.strip(),
                                            "pluggy_account_id": contas_pluggy[0].id if len(contas_pluggy) == 1 else None,
                                            "status": "ativo",
                                        }
                                    ).execute()
                                    st.success("Conexão salva.")
                                    del st.session_state[f"connect_token_{c['id']}"]
                                    st.rerun()

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

with aba_regras_identificacao:
    st.caption(
        "Padrão de texto na descrição do OFX → cliente/fornecedor/conta contábil sugerida "
        "automaticamente. Normalmente é criada sozinha ao classificar um lançamento ou "
        "conciliar uma conta fixa — aqui dá pra ver, cadastrar uma nova na mão, ou apagar."
    )
    clientes_ri = client.table("clientes").select("id, nome").order("nome").execute().data or []
    fornecedores_ri = client.table("fornecedores").select("id, nome").order("nome").execute().data or []
    contas_ri = client.table("plano_contas").select("id, codigo, nome").order("codigo").execute().data or []
    nomes_cliente_ri = {c["id"]: c["nome"] for c in clientes_ri}
    nomes_fornecedor_ri = {f["id"]: f["nome"] for f in fornecedores_ri}
    nomes_conta_ri = {c["id"]: f'{c["codigo"]} — {c["nome"]}' for c in contas_ri}

    st.subheader("Nova regra")
    with st.form("nova_regra_identificacao", clear_on_submit=True):
        padrao = st.text_input("Padrão de texto (ex.: EDP, ALUGUEL)")
        alvo_tipo = st.radio("Aponta para", ["Cliente", "Fornecedor"], horizontal=True)
        if alvo_tipo == "Cliente":
            alvo_id = st.selectbox("Cliente", options=list(nomes_cliente_ri.keys()), format_func=lambda i: nomes_cliente_ri[i]) if clientes_ri else None
        else:
            alvo_id = st.selectbox("Fornecedor", options=list(nomes_fornecedor_ri.keys()), format_func=lambda i: nomes_fornecedor_ri[i]) if fornecedores_ri else None
        plano_conta_ri = st.selectbox(
            "Conta do plano de contas (opcional)",
            options=["(nenhuma)"] + list(nomes_conta_ri.keys()),
            format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else nomes_conta_ri[i],
        )
        if st.form_submit_button("Cadastrar regra"):
            if not padrao.strip() or not alvo_id:
                st.warning("Informe o padrão de texto e um cliente/fornecedor.")
            else:
                client.table("regras_identificacao").insert(
                    {
                        "padrao_descricao": padrao.strip(),
                        "cliente_id": alvo_id if alvo_tipo == "Cliente" else None,
                        "fornecedor_id": alvo_id if alvo_tipo == "Fornecedor" else None,
                        "plano_conta_id": None if plano_conta_ri == "(nenhuma)" else plano_conta_ri,
                    }
                ).execute()
                st.success("Regra cadastrada.")
                st.rerun()

    st.divider()
    st.subheader("Regras cadastradas")
    regras_ri = (
        client.table("regras_identificacao")
        .select("id, padrao_descricao, clientes(nome), fornecedores(nome), plano_contas(codigo, nome)")
        .execute()
        .data
        or []
    )
    if regras_ri:
        st.dataframe(
            [
                {
                    "Padrão": r["padrao_descricao"],
                    "Cliente": (r.get("clientes") or {}).get("nome", "-"),
                    "Fornecedor": (r.get("fornecedores") or {}).get("nome", "-"),
                    "Conta": f'{(r.get("plano_contas") or {}).get("codigo", "")} {(r.get("plano_contas") or {}).get("nome", "")}'.strip() or "-",
                }
                for r in regras_ri
            ],
            use_container_width=True,
            hide_index=True,
        )
        opcoes_ri = {r["id"]: r["padrao_descricao"] for r in regras_ri}
        col_a, col_b = st.columns([3, 1])
        excluir_ri = col_a.selectbox("Apagar regra:", options=list(opcoes_ri.keys()), format_func=lambda i: opcoes_ri[i], key="excluir_ri")
        if col_b.button("Apagar", key="botao_excluir_ri"):
            client.table("regras_identificacao").delete().eq("id", excluir_ri).execute()
            st.success("Regra apagada.")
            st.rerun()
    else:
        st.info("Nenhuma regra de identificação cadastrada ainda.")

with aba_apolice_clientes:
    st.caption(
        "Mapeamento apólice → cliente, usado quando o demonstrativo de comissão não traz o "
        "nome do cliente (ex.: Bradesco Saúde, Porto Seguro). Normalmente criado sozinho ao "
        "importar — aqui dá pra pré-cadastrar, ver ou corrigir."
    )
    clientes_ac = client.table("clientes").select("id, nome").order("nome").execute().data or []
    nomes_cliente_ac = {c["id"]: c["nome"] for c in clientes_ac}

    st.subheader("Novo mapeamento")
    with st.form("novo_apolice_cliente", clear_on_submit=True):
        apolice_ac = st.text_input("Número da apólice")
        cliente_ac_id = (
            st.selectbox("Cliente", options=list(nomes_cliente_ac.keys()), format_func=lambda i: nomes_cliente_ac[i])
            if clientes_ac
            else None
        )
        if st.form_submit_button("Cadastrar mapeamento"):
            if not apolice_ac.strip() or not cliente_ac_id:
                st.warning("Informe a apólice e o cliente.")
            else:
                try:
                    client.table("apolice_clientes").insert(
                        {"apolice": apolice_ac.strip(), "cliente_id": cliente_ac_id}
                    ).execute()
                    st.success("Mapeamento cadastrado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cadastrar (apólice já mapeada?): {e}")

    st.divider()
    st.subheader("Mapeamentos cadastrados")
    mapeamentos_ac = (
        client.table("apolice_clientes").select("id, apolice, clientes(nome)").order("apolice").execute().data or []
    )
    if mapeamentos_ac:
        st.dataframe(
            [{"Apólice": m["apolice"], "Cliente": (m.get("clientes") or {}).get("nome", "-")} for m in mapeamentos_ac],
            use_container_width=True,
            hide_index=True,
        )
        opcoes_ac = {m["id"]: m["apolice"] for m in mapeamentos_ac}
        col_a, col_b = st.columns([3, 1])
        excluir_ac = col_a.selectbox("Apagar mapeamento:", options=list(opcoes_ac.keys()), format_func=lambda i: opcoes_ac[i], key="excluir_ac")
        if col_b.button("Apagar", key="botao_excluir_ac"):
            client.table("apolice_clientes").delete().eq("id", excluir_ac).execute()
            st.success("Mapeamento apagado.")
            st.rerun()
    else:
        st.info("Nenhum mapeamento cadastrado ainda.")

with aba_aparencia:
    st.subheader("Logo do sistema")
    st.caption(
        "Aparece no topo do menu lateral, em todas as telas. Envie uma imagem (PNG com fundo "
        "transparente fica melhor) — a mais recente sempre substitui a anterior."
    )

    try:
        arquivos_logo = client.storage.from_(layout.BUCKET_ASSETS).list()
    except Exception as e:
        arquivos_logo = []
        st.warning(f"Não consegui checar a logo atual (bucket '{layout.BUCKET_ASSETS}' existe no Storage?): {e}")

    logo_existe = any(a["name"] == layout.CAMINHO_LOGO for a in (arquivos_logo or []))
    if logo_existe:
        try:
            url_logo_atual = client.storage.from_(layout.BUCKET_ASSETS).get_public_url(layout.CAMINHO_LOGO)
            st.image(url_logo_atual, width=200, caption="Logo atual")
        except Exception:
            st.caption("Logo cadastrada, mas não consegui pré-visualizar.")
    else:
        st.caption("Nenhuma logo enviada ainda — o menu lateral fica só com o nome do sistema.")

    nova_logo = st.file_uploader("Nova logo", type=["png", "jpg", "jpeg"], key="upload_logo")
    if nova_logo is not None and st.button("Salvar logo", type="primary"):
        try:
            conteudo_logo = nova_logo.getvalue()
            content_type = nova_logo.type or "image/png"
            if logo_existe:
                client.storage.from_(layout.BUCKET_ASSETS).update(
                    layout.CAMINHO_LOGO, conteudo_logo, {"content-type": content_type}
                )
            else:
                client.storage.from_(layout.BUCKET_ASSETS).upload(
                    layout.CAMINHO_LOGO, conteudo_logo, {"content-type": content_type}
                )
            st.success("Logo salva — recarregue a página pra ver no menu lateral.")
            st.rerun()
        except Exception as e:
            st.error(
                f"Erro ao salvar a logo (crie um bucket público chamado '{layout.BUCKET_ASSETS}' no Supabase "
                f"Storage antes, se ainda não existir): {e}"
            )
