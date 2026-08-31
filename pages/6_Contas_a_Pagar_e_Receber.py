import hashlib
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

import leitor_boleto
import leitor_comprovante
import sharepoint
from db import get_client
from formatacao import data_br, moeda, parse_valor
from lancamentos import ParcelaGerada, gerar_parcelas, gerar_recorrencia

BUCKET_ANEXOS = "anexos"


def _hash_arquivo(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _anexo_duplicado(client, hash_valor: str) -> dict | None:
    """Retorna o anexo já existente com esse hash (mesmo arquivo enviado
    antes), ou None se for novo. Anexos antigos sem hash calculado (coluna
    null) nunca colidem — null nunca é igual a null em SQL."""
    existentes = client.table("anexos").select("id, nome_arquivo, created_at").eq("hash_arquivo", hash_valor).execute().data
    return existentes[0] if existentes else None


def _campo_valor(coluna, label: str, key: str, valor_inicial: float = 0.0) -> float:
    """Campo de texto livre pra digitar um valor em reais (aceita '1000',
    '1000,50' ou '1.000,50') — evita o campo numérico nativo do navegador,
    que mistura dígitos digitados com o conteúdo antigo do campo. Mostra o
    valor interpretado logo abaixo, formatado, pra o usuário conferir."""
    texto = coluna.text_input(label, value=moeda(valor_inicial).replace("R$ ", ""), key=key)
    try:
        valor = parse_valor(texto)
        if valor < 0:
            raise ValueError
        coluna.caption(moeda(valor))
    except ValueError:
        coluna.caption("⚠️ valor inválido — use só números, vírgula pra decimal")
        valor = 0.0
    return valor

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
    st.error("Cadastre ao menos uma empresa em **Configurações** antes de continuar.")
    st.stop()
empresas_por_id = {e["id"]: e["nome"] for e in empresas}

clientes = client.table("clientes").select("id, nome").order("nome").execute().data or []
fornecedores = client.table("fornecedores").select("id, nome").order("nome").execute().data or []
contas_plano = client.table("plano_contas").select("id, codigo, nome").order("codigo").execute().data or []
contas_bancarias = (
    client.table("contas_bancarias").select("id, banco, agencia, conta").order("conta").execute().data or []
)
nomes_fornecedor_todos = {f["id"]: f["nome"] for f in fornecedores}

st.subheader("📄 Ler boleto/guia automaticamente (via IA)")
if not leitor_boleto.esta_configurado():
    st.caption(
        "Configure `ANTHROPIC_API_KEY` no arquivo `.env` para habilitar a leitura automática de boletos. "
        "Enquanto isso, use o cadastro manual abaixo."
    )
else:
    boleto_pdf = st.file_uploader("Suba o PDF do boleto/guia", type=["pdf"], key="upload_boleto_ia")
    if boleto_pdf is not None and st.button("Ler boleto com IA"):
        with st.spinner("Lendo o boleto..."):
            try:
                dados_lidos = leitor_boleto.ler_boleto(boleto_pdf.getvalue())
                st.session_state["boleto_lido"] = dados_lidos
                st.session_state["boleto_lido_arquivo"] = {
                    "nome": boleto_pdf.name,
                    "conteudo": boleto_pdf.getvalue(),
                    "tipo": boleto_pdf.type,
                }
            except Exception as e:
                st.error(f"Não deu pra ler automaticamente este boleto: {e}")

    if st.session_state.get("boleto_lido"):
        dados = st.session_state["boleto_lido"]
        aviso = f"Confiança da leitura: **{dados.confianca}**"
        if dados.observacoes:
            aviso += f" — {dados.observacoes}"
        st.info(aviso)
        st.caption("Confira e corrija os dados abaixo antes de confirmar — nada é lançado sem sua confirmação.")

        c1, c2 = st.columns(2)
        valor_confirmado = _campo_valor(c1, "Valor (R$)", "valor_boleto_ia", valor_inicial=float(dados.valor or 0))
        try:
            venc_padrao = date.fromisoformat(dados.data_vencimento) if dados.data_vencimento else date.today()
        except ValueError:
            venc_padrao = date.today()
        vencimento_confirmado = c2.date_input(
            "Vencimento", value=venc_padrao, format="DD/MM/YYYY", key="vencimento_boleto_ia"
        )
        descricao_confirmada = st.text_input("Descrição", value=dados.descricao or "", key="descricao_boleto_ia")
        empresa_boleto_id = st.selectbox(
            "Empresa", options=list(empresas_por_id.keys()), format_func=lambda i: empresas_por_id[i], key="empresa_boleto_ia"
        )

        sugestao_fornecedor_id = None
        if dados.favorecido:
            alvo = dados.favorecido.lower()
            for fid, nome in nomes_fornecedor_todos.items():
                if nome.lower() in alvo or alvo in nome.lower():
                    sugestao_fornecedor_id = fid
                    break
        opcoes_fornecedor_boleto = ["(nenhum)", "+ Novo fornecedor"] + list(nomes_fornecedor_todos.keys())
        index_padrao = (
            opcoes_fornecedor_boleto.index(sugestao_fornecedor_id) if sugestao_fornecedor_id else 0
        )
        fornecedor_escolhido_boleto = st.selectbox(
            "Fornecedor",
            options=opcoes_fornecedor_boleto,
            index=index_padrao,
            format_func=lambda i: i if i in ("(nenhum)", "+ Novo fornecedor") else nomes_fornecedor_todos.get(i, i),
            key="fornecedor_boleto_ia",
        )
        novo_fornecedor_nome_boleto = None
        if fornecedor_escolhido_boleto == "+ Novo fornecedor":
            novo_fornecedor_nome_boleto = st.text_input(
                "Nome do novo fornecedor", value=dados.favorecido or "", key="novo_fornecedor_boleto_ia"
            )

        col_confirmar, col_descartar = st.columns(2)
        if col_confirmar.button("Cadastrar lançamento com estes dados", type="primary", key="confirmar_boleto_ia"):
            fornecedor_id_boleto = None
            if fornecedor_escolhido_boleto == "+ Novo fornecedor" and novo_fornecedor_nome_boleto and novo_fornecedor_nome_boleto.strip():
                fornecedor_id_boleto = (
                    client.table("fornecedores").insert({"nome": novo_fornecedor_nome_boleto.strip()}).execute().data[0]["id"]
                )
            elif fornecedor_escolhido_boleto not in ("(nenhum)", "+ Novo fornecedor"):
                fornecedor_id_boleto = fornecedor_escolhido_boleto

            criado = (
                client.table("lancamentos_previstos")
                .insert(
                    {
                        "empresa_id": empresa_boleto_id,
                        "tipo": "pagar",
                        "descricao": descricao_confirmada.strip() or "Boleto",
                        "valor": valor_confirmado,
                        "data_vencimento": vencimento_confirmado.isoformat(),
                        "status": "previsto",
                        "fornecedor_id": fornecedor_id_boleto,
                        "grupo_id": str(uuid.uuid4()),
                    }
                )
                .execute()
            )
            lancamento_id_boleto = criado.data[0]["id"]

            arquivo_info = st.session_state["boleto_lido_arquivo"]
            hoje = date.today()
            # nome do upload não é confiável (pode trazer ".." ou um caminho
            # absoluto) — usa só o nome do arquivo em si, sem componentes de diretório.
            nome_seguro = f"{uuid.uuid4().hex}_{Path(arquivo_info['nome']).name}"
            caminho_storage = f"{hoje.year}/{hoje.month:02d}/boleto/{nome_seguro}"
            try:
                client.storage.from_(BUCKET_ANEXOS).upload(
                    caminho_storage, arquivo_info["conteudo"], {"content-type": arquivo_info["tipo"] or "application/pdf"}
                )
                client.table("anexos").insert(
                    {
                        "lancamento_previsto_id": lancamento_id_boleto,
                        "tipo": "boleto",
                        "nome_arquivo": arquivo_info["nome"],
                        "storage_path": caminho_storage,
                        "hash_arquivo": _hash_arquivo(arquivo_info["conteudo"]),
                    }
                ).execute()
                if sharepoint.esta_configurado():
                    try:
                        sharepoint.enviar_arquivo(caminho_storage, arquivo_info["conteudo"])
                    except Exception as e:
                        st.warning(f"Anexo salvo, mas a cópia para o SharePoint falhou: {e}")
            except Exception as e:
                st.error(f"Lançamento criado, mas houve erro ao salvar o anexo: {e}")

            del st.session_state["boleto_lido"]
            del st.session_state["boleto_lido_arquivo"]
            st.success("Lançamento criado a partir do boleto, com o anexo já vinculado.")
            st.rerun()

        if col_descartar.button("Descartar leitura", key="descartar_boleto_ia"):
            del st.session_state["boleto_lido"]
            del st.session_state["boleto_lido_arquivo"]
            st.rerun()

st.divider()
st.subheader("📎 Enviar vários comprovantes de uma vez (IA vincula e dá baixa sozinha)")
if not leitor_comprovante.esta_configurado():
    st.caption("Configure `ANTHROPIC_API_KEY` no arquivo `.env` para habilitar a leitura automática de comprovantes.")
else:
    st.caption(
        "Cada comprovante é lido pela IA e casado com um lançamento previsto (por valor + proximidade de data). "
        "Quando o casamento é certo (exatamente um candidato), o anexo é vinculado e o lançamento marcado como "
        "pago automaticamente. Quando fica ambíguo ou a leitura não é confiável, o comprovante é salvo sem "
        "vínculo, para você resolver manualmente em **Todos os anexos**."
    )
    comprovantes = st.file_uploader(
        "Suba um ou vários PDFs de comprovante",
        type=["pdf"],
        accept_multiple_files=True,
        key="upload_comprovantes_lote",
    )
    if comprovantes and st.button("Processar comprovantes", type="primary"):
        resultados = []
        with st.spinner(f"Lendo {len(comprovantes)} comprovante(s)..."):
            for arquivo in comprovantes:
                conteudo = arquivo.getvalue()
                hoje = date.today()
                hash_valor = _hash_arquivo(conteudo)

                duplicado = _anexo_duplicado(client, hash_valor)
                if duplicado:
                    resultados.append(
                        {
                            "Arquivo": arquivo.name,
                            "Valor lido": "-",
                            "Resultado": f"⏭️ já enviado antes ({data_br(duplicado['created_at'])}) — ignorado",
                        }
                    )
                    continue

                # nome do upload não é confiável — usa só o nome do arquivo, sem componentes de diretório.
                nome_seguro = f"{uuid.uuid4().hex}_{Path(arquivo.name).name}"
                caminho_storage = f"{hoje.year}/{hoje.month:02d}/comprovante/{nome_seguro}"

                try:
                    dados = leitor_comprovante.ler_comprovante(conteudo)
                except Exception as e:
                    resultados.append({"Arquivo": arquivo.name, "Valor lido": "-", "Resultado": f"❌ erro na leitura: {e}"})
                    continue

                lancamento_id = None
                if dados.confianca != "baixa":
                    lancamento_id = leitor_comprovante.encontrar_lancamento_correspondente(
                        client, dados.valor, dados.data_pagamento, dados.favorecido
                    )

                try:
                    client.storage.from_(BUCKET_ANEXOS).upload(
                        caminho_storage, conteudo, {"content-type": arquivo.type or "application/pdf"}
                    )
                    client.table("anexos").insert(
                        {
                            "lancamento_previsto_id": lancamento_id,
                            "tipo": "comprovante",
                            "nome_arquivo": arquivo.name,
                            "storage_path": caminho_storage,
                            "hash_arquivo": hash_valor,
                        }
                    ).execute()
                    if sharepoint.esta_configurado():
                        try:
                            sharepoint.enviar_arquivo(caminho_storage, conteudo)
                        except Exception as e:
                            st.warning(f"'{arquivo.name}': anexo salvo, mas a cópia pro SharePoint falhou: {e}")
                except Exception as e:
                    resultados.append({"Arquivo": arquivo.name, "Valor lido": "-", "Resultado": f"❌ erro ao salvar: {e}"})
                    continue

                valor_lido = moeda(dados.valor) if dados.valor is not None else "-"
                if lancamento_id:
                    client.table("lancamentos_previstos").update(
                        {"status": "pago", "data_pagamento": (dados.data_pagamento or hoje.isoformat())[:10]}
                    ).eq("id", lancamento_id).execute()
                    resultados.append({"Arquivo": arquivo.name, "Valor lido": valor_lido, "Resultado": "✅ vinculado e marcado como pago"})
                else:
                    resultados.append(
                        {"Arquivo": arquivo.name, "Valor lido": valor_lido, "Resultado": "⚠️ salvo sem vínculo — revise manualmente"}
                    )

        st.dataframe(resultados, use_container_width=True, hide_index=True)
        st.success(f"{len(comprovantes)} comprovante(s) processado(s).")

st.divider()
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
    valor = _campo_valor(c1, "Valor (R$)", "valor_avulso")
    data_vencimento = c2.date_input("Data de vencimento", value=date.today(), format="DD/MM/YYYY")
    if valor > 0:
        parcelas_preview = [
            ParcelaGerada(parcela_atual=None, parcela_total=None, valor=valor, data_vencimento=data_vencimento)
        ]
elif modo == "Parcelado":
    c1, c2, c3 = st.columns(3)
    valor_total = _campo_valor(c1, "Valor total (R$)", "valor_parcelado")
    num_parcelas = c2.number_input("Número de parcelas", min_value=1, step=1, value=2)
    data_primeira = c3.date_input("Vencimento da 1ª parcela", value=date.today(), format="DD/MM/YYYY")
    if valor_total > 0:
        parcelas_preview = gerar_parcelas(valor_total, int(num_parcelas), data_primeira)
else:
    c1, c2, c3 = st.columns(3)
    valor_mensal = _campo_valor(c1, "Valor mensal (R$)", "valor_fixo")
    data_primeiro_vencimento = c2.date_input("1º vencimento", value=date.today(), format="DD/MM/YYYY")
    meses_a_gerar = c3.number_input("Gerar quantos meses à frente?", min_value=1, step=1, value=12)
    if valor_mensal > 0:
        parcelas_preview = gerar_recorrencia(valor_mensal, data_primeiro_vencimento, int(meses_a_gerar))

if parcelas_preview:
    st.caption(f"Prévia: {len(parcelas_preview)} lançamento(s) serão criados.")
    st.dataframe(
        [{"Parcela": f"{p.parcela_atual}/{p.parcela_total}" if p.parcela_atual else "-", "Vencimento": data_br(p.data_vencimento), "Valor": moeda(p.valor)} for p in parcelas_preview],
        use_container_width=True,
        hide_index=True,
    )

arquivo_anexo = st.file_uploader(
    "Anexar boleto/comprovante (opcional)",
    key="anexo_novo_lancamento",
    help="Fica salvo já vinculado ao lançamento (na 1ª parcela, se for parcelado/fixo).",
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
    primeiro_id = None
    for p in parcelas_preview:
        criado = client.table("lancamentos_previstos").insert(
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
        if primeiro_id is None:
            primeiro_id = criado.data[0]["id"]
    st.success(f"{len(parcelas_preview)} lançamento(s) cadastrado(s).")

    if arquivo_anexo is not None and primeiro_id is not None:
        hoje = date.today()
        # nome do upload não é confiável (pode trazer ".." ou um caminho
        # absoluto) — usa só o nome do arquivo em si, sem componentes de diretório.
        nome_seguro = f"{uuid.uuid4().hex}_{Path(arquivo_anexo.name).name}"
        caminho_storage = f"{hoje.year}/{hoje.month:02d}/boleto/{nome_seguro}"
        try:
            client.storage.from_(BUCKET_ANEXOS).upload(
                caminho_storage,
                arquivo_anexo.getvalue(),
                {"content-type": arquivo_anexo.type or "application/octet-stream"},
            )
            client.table("anexos").insert(
                {
                    "lancamento_previsto_id": primeiro_id,
                    "tipo": "boleto",
                    "nome_arquivo": arquivo_anexo.name,
                    "storage_path": caminho_storage,
                    "hash_arquivo": _hash_arquivo(arquivo_anexo.getvalue()),
                }
            ).execute()
            st.success(f"Anexo '{arquivo_anexo.name}' vinculado ao lançamento.")
            if sharepoint.esta_configurado():
                try:
                    sharepoint.enviar_arquivo(caminho_storage, arquivo_anexo.getvalue())
                except Exception as e:
                    st.warning(f"Anexo salvo, mas a cópia para o SharePoint falhou: {e}")
        except Exception as e:
            st.error(f"Lançamento criado, mas houve erro ao salvar o anexo: {e}")

st.divider()


def _secao_anexos(lancamento_id: str, key_prefix: str):
    anexos = (
        client.table("anexos")
        .select("id, tipo, nome_arquivo, storage_path, created_at")
        .eq("lancamento_previsto_id", lancamento_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    if anexos:
        for a in anexos:
            col_nome, col_baixar, col_apagar = st.columns([4, 1, 1])
            col_nome.write(f"📎 {a['tipo']} — {a['nome_arquivo']}")
            try:
                conteudo = client.storage.from_(BUCKET_ANEXOS).download(a["storage_path"])
                col_baixar.download_button(
                    "Baixar", data=conteudo, file_name=a["nome_arquivo"], key=f"{key_prefix}_baixar_{a['id']}"
                )
            except Exception as e:
                col_baixar.error("erro")
            if col_apagar.button("Apagar", key=f"{key_prefix}_apagar_{a['id']}"):
                client.storage.from_(BUCKET_ANEXOS).remove([a["storage_path"]])
                client.table("anexos").delete().eq("id", a["id"]).execute()
                if sharepoint.esta_configurado():
                    try:
                        sharepoint.remover_arquivo(a["storage_path"])
                    except Exception as e:
                        st.warning(f"Não foi possível remover a cópia no SharePoint: {e}")
                st.success("Anexo apagado.")
                st.rerun()
    else:
        st.caption("Nenhum anexo neste lançamento ainda.")

    col_tipo, col_arquivo = st.columns([1, 3])
    tipo_novo_anexo = col_tipo.radio(
        "Tipo", ["Boleto", "Comprovante", "Outro"], horizontal=False, key=f"{key_prefix}_tipo"
    )
    novo_arquivo = col_arquivo.file_uploader("Novo anexo", key=f"{key_prefix}_upload")
    if novo_arquivo is not None and st.button("Salvar anexo", key=f"{key_prefix}_salvar"):
        hoje = date.today()
        # nome do upload não é confiável (pode trazer ".." ou um caminho
        # absoluto) — usa só o nome do arquivo em si, sem componentes de diretório.
        nome_seguro = f"{uuid.uuid4().hex}_{Path(novo_arquivo.name).name}"
        caminho_storage = f"{hoje.year}/{hoje.month:02d}/{tipo_novo_anexo.lower()}/{nome_seguro}"
        try:
            client.storage.from_(BUCKET_ANEXOS).upload(
                caminho_storage, novo_arquivo.getvalue(), {"content-type": novo_arquivo.type or "application/octet-stream"}
            )
            client.table("anexos").insert(
                {
                    "lancamento_previsto_id": lancamento_id,
                    "tipo": tipo_novo_anexo.lower(),
                    "nome_arquivo": novo_arquivo.name,
                    "storage_path": caminho_storage,
                    "hash_arquivo": _hash_arquivo(novo_arquivo.getvalue()),
                }
            ).execute()
            st.success(f"Anexo '{novo_arquivo.name}' salvo.")
            if sharepoint.esta_configurado():
                try:
                    sharepoint.enviar_arquivo(caminho_storage, novo_arquivo.getvalue())
                except Exception as e:
                    st.warning(f"Anexo salvo, mas a cópia para o SharePoint falhou: {e}")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar anexo: {e}")


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
                "Vencimento": data_br(item["data_vencimento"]),
                "Descrição": item["descricao"],
                "Cliente/Fornecedor": terceiro,
                "Valor": moeda(item["valor"]),
                "Situação": situacao,
            }
        )
    st.dataframe(linhas, use_container_width=True, hide_index=True)

    pendentes = [i for i in itens if i["status"] == "previsto"]
    if pendentes:
        opcoes = {i["id"]: f"{data_br(i['data_vencimento'])} — {i['descricao']} — {moeda(i['valor'])}" for i in pendentes}
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

    opcoes_anexo = {i["id"]: f"{data_br(i['data_vencimento'])} — {i['descricao']} — {moeda(i['valor'])} ({i['status']})" for i in itens}
    lancamento_anexo_id = st.selectbox(
        "Anexos de:", options=list(opcoes_anexo.keys()), format_func=lambda i: opcoes_anexo[i], key=f"sel_anexo_{tipo_filtro}"
    )
    with st.expander("📎 Boletos e comprovantes deste lançamento"):
        _secao_anexos(lancamento_anexo_id, key_prefix=f"anexo_{tipo_filtro}_{lancamento_anexo_id}")


_tabela("pagar", "Contas a Pagar")
st.divider()
_tabela("receber", "Contas a Receber")

st.divider()
st.subheader("Todos os anexos")
filtro_tipo_global = st.selectbox("Filtrar por tipo", options=["Todos", "Boleto", "Comprovante", "Outro"], key="filtro_tipo_global")
query_global = client.table("anexos").select(
    "id, tipo, nome_arquivo, storage_path, created_at, lancamentos_previstos(descricao, data_vencimento)"
)
if filtro_tipo_global != "Todos":
    query_global = query_global.eq("tipo", filtro_tipo_global.lower())
anexos_globais = query_global.order("created_at", desc=True).limit(200).execute().data or []

lancamentos_para_vincular = (
    client.table("lancamentos_previstos")
    .select("id, descricao, valor, data_vencimento, status")
    .order("data_vencimento", desc=True)
    .limit(300)
    .execute()
    .data
    or []
)
opcoes_vincular = {
    l["id"]: f"{data_br(l['data_vencimento'])} — {l['descricao']} — {moeda(l['valor'])} ({l['status']})"
    for l in lancamentos_para_vincular
}

if not anexos_globais:
    st.info("Nenhum anexo guardado ainda.")
else:
    for a in anexos_globais:
        vinculo = a.get("lancamentos_previstos")
        rotulo = f"{vinculo['descricao']} ({data_br(vinculo['data_vencimento'])})" if vinculo else "sem vínculo a nenhum lançamento"
        with st.expander(f"📎 {data_br(a['created_at'])} — {a['tipo']} — {a['nome_arquivo']} — {rotulo}"):
            try:
                conteudo = client.storage.from_(BUCKET_ANEXOS).download(a["storage_path"])
                st.download_button("Baixar", data=conteudo, file_name=a["nome_arquivo"], key=f"global_baixar_{a['id']}")
            except Exception as e:
                st.error(f"Erro ao carregar arquivo: {e}")

            if not vinculo and opcoes_vincular:
                st.caption("Sem vínculo — selecione o lançamento certo:")
                col_sel, col_pago, col_btn = st.columns([3, 1, 1])
                lancamento_escolhido = col_sel.selectbox(
                    "Vincular a",
                    options=list(opcoes_vincular.keys()),
                    format_func=lambda i: opcoes_vincular[i],
                    key=f"vincular_sel_{a['id']}",
                )
                marcar_pago = col_pago.checkbox("Marcar pago", value=True, key=f"vincular_pago_{a['id']}")
                if col_btn.button("Vincular", key=f"vincular_btn_{a['id']}"):
                    client.table("anexos").update({"lancamento_previsto_id": lancamento_escolhido}).eq("id", a["id"]).execute()
                    if marcar_pago:
                        client.table("lancamentos_previstos").update(
                            {"status": "pago", "data_pagamento": date.today().isoformat()}
                        ).eq("id", lancamento_escolhido).execute()
                    st.success("Anexo vinculado.")
                    st.rerun()

            if st.button("Apagar", key=f"global_apagar_{a['id']}"):
                client.storage.from_(BUCKET_ANEXOS).remove([a["storage_path"]])
                client.table("anexos").delete().eq("id", a["id"]).execute()
                if sharepoint.esta_configurado():
                    try:
                        sharepoint.remover_arquivo(a["storage_path"])
                    except Exception as e:
                        st.warning(f"Não foi possível remover a cópia no SharePoint: {e}")
                st.success("Anexo apagado.")
                st.rerun()
