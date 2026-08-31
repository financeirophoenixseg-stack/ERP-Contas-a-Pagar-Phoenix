import hashlib
import tempfile
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

from classificacao_comissao import classificar, parcelas_restantes
from regra_suhai import bate_com_formula, parcelas_enquadradas
from db import get_client
from formatacao import moeda
from lancamentos import gerar_recorrencia, somar_meses
from parsers import PARSERS, identificar_seguradora

st.set_page_config(page_title="Importar Comissão", layout="wide")
st.title("Importar demonstrativo de comissão")
st.caption(
    "Envie o(s) arquivo(s) do demonstrativo (PDF e/ou planilha — cada seguradora aceita o "
    "que ela manda, um arquivo já basta). A seguradora e a empresa responsável são "
    "identificadas automaticamente."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

arquivos = st.file_uploader("Arquivo(s) do demonstrativo", accept_multiple_files=True)
if not arquivos:
    st.stop()

raw_por_nome = {a.name: a.getvalue() for a in arquivos}
hash_arquivo = hashlib.sha256(b"".join(raw_por_nome[a.name] for a in arquivos)).hexdigest()

ja_importado = (
    client.table("lotes_comissao").select("id").eq("hash_arquivo", hash_arquivo).execute().data
)
if ja_importado:
    st.warning("Este demonstrativo já foi importado anteriormente. Nenhuma ação será feita.")
    st.stop()

with tempfile.TemporaryDirectory() as tmp:
    caminhos = []
    for arquivo in arquivos:
        # nome do upload não é confiável (pode trazer ".." ou um caminho
        # absoluto) — usa só o nome do arquivo em si, sem componentes de diretório.
        nome_seguro = Path(arquivo.name).name
        caminho = Path(tmp) / nome_seguro
        caminho.write_bytes(raw_por_nome[arquivo.name])
        caminhos.append(str(caminho))

    seguradora_nome = identificar_seguradora(caminhos)
    if not seguradora_nome:
        st.error(
            "Não consegui identificar automaticamente a seguradora pelo layout deste(s) "
            "arquivo(s). Verifique se é um demonstrativo de uma seguradora já suportada."
        )
        st.stop()

    st.success(f"Seguradora identificada automaticamente: **{seguradora_nome}**")
    lote = PARSERS[seguradora_nome]["parse"](caminhos)

if not lote.linhas:
    st.error("Nenhuma linha de comissão encontrada nestes arquivos.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Data de pagamento", lote.data_pagamento or "?")
col2.metric("Valor bruto (tributário)", moeda(lote.valor_bruto))
col3.metric("Valor líquido", moeda(lote.valor_liquido))
identificador = (
    f"CNPJ: {lote.cnpj}" if lote.cnpj
    else f"SUSEP: {lote.susep}" if lote.susep
    else f"Código comissionado: {lote.codigo_comissionado}" if lote.codigo_comissionado
    else ""
)
st.caption(f"Corretor: {lote.corretor} — {identificador}")

empresas = client.table("empresas").select("id, nome, cnpj, susep, codigo_comissionado").execute().data or []
empresa_por_cnpj = {e["cnpj"]: e for e in empresas if e.get("cnpj")}
empresa_resolvida = empresa_por_cnpj.get(lote.cnpj) if lote.cnpj else None
identificado_por = "CNPJ"

if not empresa_resolvida and lote.susep:
    empresa_por_susep = {e["susep"]: e for e in empresas if e.get("susep")}
    empresa_resolvida = empresa_por_susep.get(lote.susep)
    identificado_por = "SUSEP"

if not empresa_resolvida and lote.codigo_comissionado:
    empresa_por_codigo = {e["codigo_comissionado"]: e for e in empresas if e.get("codigo_comissionado")}
    empresa_resolvida = empresa_por_codigo.get(lote.codigo_comissionado)
    identificado_por = "código comissionado"

if not empresa_resolvida and lote.conta:
    # sem CNPJ (ex.: só a planilha foi enviada) — tenta pela conta bancária,
    # ignorando a agência (o número de agência vem formatado diferente entre
    # o extrato da seguradora e o nosso cadastro).
    contas = (
        client.table("contas_bancarias")
        .select("banco, conta, empresas(id, nome)")
        .eq("conta", lote.conta)
        .execute()
        .data
        or []
    )
    if len(contas) == 1:
        empresa_resolvida = contas[0]["empresas"]
        identificado_por = "conta bancária"

if empresa_resolvida:
    st.success(f"Empresa identificada automaticamente pelo {identificado_por}: **{empresa_resolvida['nome']}**")
    empresa_id = empresa_resolvida["id"]
else:
    motivo = (
        f"CNPJ '{lote.cnpj}'" if lote.cnpj
        else f"SUSEP '{lote.susep}'" if lote.susep
        else f"código comissionado '{lote.codigo_comissionado}'" if lote.codigo_comissionado
        else f"conta '{lote.conta}'" if lote.conta
        else "nenhum dado"
    )
    st.warning(
        f"{motivo} não está vinculado a nenhuma empresa cadastrada. Selecione manualmente:"
    )
    if not empresas:
        st.error("Cadastre ao menos uma empresa em **Configurações** antes de importar.")
        st.stop()
    nomes_por_id = {e["id"]: e["nome"] for e in empresas}
    empresa_id = st.selectbox("Empresa responsável", options=list(nomes_por_id.keys()), format_func=lambda i: nomes_por_id[i])
    if lote.cnpj and st.checkbox(
        f"Salvar CNPJ {lote.cnpj} para esta empresa (próximas importações serão automáticas)"
    ):
        try:
            client.table("empresas").update({"cnpj": lote.cnpj}).eq("id", empresa_id).execute()
            st.info("CNPJ salvo.")
        except Exception as e:
            st.error(f"Erro ao salvar CNPJ: {e}")
    if lote.susep and st.checkbox(
        f"Salvar SUSEP {lote.susep} para esta empresa (próximas importações serão automáticas)"
    ):
        try:
            client.table("empresas").update({"susep": lote.susep}).eq("id", empresa_id).execute()
            st.info("SUSEP salvo.")
        except Exception as e:
            st.error(f"Erro ao salvar SUSEP: {e}")
    if lote.codigo_comissionado and st.checkbox(
        f"Salvar código comissionado {lote.codigo_comissionado} para esta empresa (próximas importações serão automáticas)"
    ):
        try:
            client.table("empresas").update({"codigo_comissionado": lote.codigo_comissionado}).eq("id", empresa_id).execute()
            st.info("Código comissionado salvo.")
        except Exception as e:
            st.error(f"Erro ao salvar código comissionado: {e}")

st.divider()
st.subheader(f"{len(lote.linhas)} movimentações de comissão")
st.dataframe(
    [
        {
            "Cliente": l.cliente or "(por apólice)",
            "Apólice": l.apolice,
            "Endosso": l.endosso,
            "Parcela": l.parcela,
            "% Comissão": l.percentual_comissao,
            "Tipo": l.tipo,
            "Valor Parcela": moeda(l.valor_parcela),
            "Valor Comissão": moeda(l.valor_comissao),
        }
        for l in lote.linhas
    ],
    use_container_width=True,
    hide_index=True,
)

# Linhas sem nome de cliente direto (ex.: Bradesco Saúde) são identificadas
# pela apólice — resolvidas via apolice_clientes, com cadastro manual na
# primeira vez que uma apólice aparece.
apolices_sem_nome = sorted({l.apolice for l in lote.linhas if not l.cliente})
mapa_apolice_cliente = {}
if apolices_sem_nome:
    mapeamentos = (
        client.table("apolice_clientes").select("apolice, cliente_id").execute().data or []
    )
    mapa_apolice_cliente = {m["apolice"]: m["cliente_id"] for m in mapeamentos}

    clientes_todos = client.table("clientes").select("id, nome").order("nome").execute().data or []
    nomes_por_id_cliente = {c["id"]: c["nome"] for c in clientes_todos}

    apolices_novas = [a for a in apolices_sem_nome if a not in mapa_apolice_cliente]
    if apolices_novas:
        st.divider()
        st.subheader("Apólices sem cliente cadastrado")
        st.caption(
            "Este demonstrativo não traz o nome do cliente, só o número da apólice. "
            "Associe cada apólice a um cliente uma única vez — nas próximas importações "
            "ela já será reconhecida automaticamente."
        )
        for apolice in apolices_novas:
            opcoes = ["+ Novo cliente"] + list(nomes_por_id_cliente.keys())
            escolha = st.selectbox(
                f"Cliente da apólice {apolice}",
                options=opcoes,
                format_func=lambda i: "+ Novo cliente" if i == "+ Novo cliente" else nomes_por_id_cliente[i],
                key=f"apolice_{apolice}",
            )
            if escolha == "+ Novo cliente":
                novo_nome = st.text_input("Nome do cliente", key=f"novo_cliente_apolice_{apolice}")
                mapa_apolice_cliente[apolice] = ("novo", novo_nome)
            else:
                # cliente já existe, mas o mapeamento apolice->cliente ainda não
                # foi salvo — precisa ser gravado ao confirmar, por isso o "existente"
                # (distinto de uma apólice cujo mapeamento já veio do banco).
                mapa_apolice_cliente[apolice] = ("existente", escolha)

faltando_resolver = [
    a for a in apolices_sem_nome
    if a not in mapa_apolice_cliente or mapa_apolice_cliente[a] == ("novo", "")
]

if faltando_resolver:
    st.info("Associe um cliente a todas as apólices acima para poder confirmar a importação.")
    st.stop()

if st.button("Confirmar importação", type="primary"):
    seguradora = client.table("seguradoras").select("id").eq("nome", seguradora_nome).execute().data
    seguradora_id = (
        seguradora[0]["id"]
        if seguradora
        else client.table("seguradoras").insert({"nome": seguradora_nome}).execute().data[0]["id"]
    )

    # Motor de conciliação: procura crédito no OFX com mesma data/valor.
    # Se achar em conta de OUTRA empresa, gera alerta de auditoria em vez de aceitar.
    candidatos = (
        client.table("ofx_transacoes")
        .select("id, valor, data, conciliado, contas_bancarias(empresa_id)")
        .eq("data", lote.data_pagamento)
        .eq("conciliado", False)
        .execute()
        .data
        or []
    )
    match_mesma_empresa = [
        c for c in candidatos
        if abs(c["valor"] - lote.valor_liquido) < 0.005 and c["contas_bancarias"]["empresa_id"] == empresa_id
    ]
    match_outra_empresa = [
        c for c in candidatos
        if abs(c["valor"] - lote.valor_liquido) < 0.005 and c["contas_bancarias"]["empresa_id"] != empresa_id
    ]

    if match_mesma_empresa:
        ofx_transacao_id = match_mesma_empresa[0]["id"]
        status = "conciliado"
        client.table("ofx_transacoes").update({"conciliado": True}).eq("id", ofx_transacao_id).execute()
    else:
        ofx_transacao_id = None
        status = "divergente" if match_outra_empresa else "pendente"

    lote_resp = (
        client.table("lotes_comissao")
        .insert(
            {
                "seguradora_id": seguradora_id,
                "empresa_id": empresa_id,
                "arquivo_origem": ", ".join(a.name for a in arquivos),
                "hash_arquivo": hash_arquivo,
                "data_pagamento": lote.data_pagamento,
                "valor_bruto": lote.valor_bruto,
                "valor_irrf": lote.irrf,
                "valor_iss": lote.iss,
                "valor_inss": lote.inss,
                "valor_pis_cofins_csll": lote.pis_cofins_csll,
                "valor_liquido": lote.valor_liquido,
                "ofx_transacao_id": ofx_transacao_id,
                "status": status,
            }
        )
        .execute()
    )
    lote_id = lote_resp.data[0]["id"]

    if match_outra_empresa:
        client.table("auditoria_alertas").insert(
            {
                "tipo": "empresa_divergente",
                "descricao": (
                    f"Comissão da empresa '{empresa_id}' (lote {lote.data_pagamento}, "
                    f"{moeda(lote.valor_liquido)}) encontrada em conta bancária de outra empresa."
                ),
                "lote_id": lote_id,
            }
        ).execute()

    def resolver_cliente_por_nome(nome: str, clientes_existentes: dict) -> str:
        chave = nome.strip().lower()
        cliente_id = clientes_existentes.get(chave)
        if not cliente_id:
            novo = (
                client.table("clientes")
                .insert({"nome": nome.strip(), "empresa_principal_id": empresa_id})
                .execute()
            )
            cliente_id = novo.data[0]["id"]
            clientes_existentes[chave] = cliente_id
        return cliente_id

    def resolver_cliente_por_apolice(apolice: str, clientes_existentes: dict) -> str:
        escolha = mapa_apolice_cliente[apolice]
        if isinstance(escolha, tuple):
            tipo_escolha, valor = escolha
            cliente_id = (
                resolver_cliente_por_nome(valor, clientes_existentes) if tipo_escolha == "novo" else valor
            )
            client.table("apolice_clientes").insert(
                {"apolice": apolice, "cliente_id": cliente_id}
            ).execute()
            return cliente_id
        return escolha  # mapeamento já existia no banco antes desta importação

    def _provisionar_ocorrencias(cliente_id: str, apolice: str, valor: float, quantidade: int, descricao: str) -> None:
        """Se já existem provisões futuras (pendentes) dessa apólice, só
        atualiza o valor pelo mais recente observado (sem duplicar);
        senão, cria `quantidade` ocorrências mensais futuras."""
        if quantidade <= 0:
            return
        existentes = (
            client.table("lancamentos_previstos")
            .select("id")
            .eq("cliente_id", cliente_id)
            .eq("apolice", apolice)
            .eq("tipo", "receber")
            .eq("status", "previsto")
            .execute()
            .data
            or []
        )
        if existentes:
            client.table("lancamentos_previstos").update({"valor": valor}).eq(
                "cliente_id", cliente_id
            ).eq("apolice", apolice).eq("tipo", "receber").eq("status", "previsto").execute()
            return

        data_base = date.fromisoformat(lote.data_pagamento) if lote.data_pagamento else date.today()
        grupo_id = str(uuid.uuid4())
        for ocorrencia in gerar_recorrencia(valor, somar_meses(data_base, 1), quantidade):
            client.table("lancamentos_previstos").insert(
                {
                    "empresa_id": empresa_id,
                    "tipo": "receber",
                    "descricao": descricao,
                    "valor": ocorrencia.valor,
                    "data_vencimento": ocorrencia.data_vencimento.isoformat(),
                    "status": "previsto",
                    "cliente_id": cliente_id,
                    "grupo_id": grupo_id,
                    "recorrente": True,
                    "apolice": apolice,
                }
            ).execute()

    def provisionar_vitalicio(cliente_id: str, apolice: str, valor: float, regra: dict) -> None:
        """Comissão vitalícia = vai se repetir todo mês enquanto a apólice durar."""
        _provisionar_ocorrencias(
            cliente_id, apolice, valor, regra["meses_provisionar"],
            f"Comissão vitalícia prevista — apólice {apolice}",
        )

    def provisionar_parcelamento(cliente_id: str, apolice: str, valor: float, parcela: str, regra: dict) -> None:
        """Auto/RE: nº de parcelas restantes conhecido (regras_parcelamento)."""
        restantes = parcelas_restantes(parcela, regra["total_parcelas"])
        _provisionar_ocorrencias(
            cliente_id, apolice, valor, restantes,
            f"Comissão parcelada prevista — apólice {apolice}",
        )

    try:
        clientes_existentes = {
            c["nome"].strip().lower(): c["id"]
            for c in client.table("clientes").select("id, nome").execute().data or []
        }
        regras_por_cliente = {
            r["cliente_id"]: r
            for r in client.table("regras_classificacao_comissao").select("*").execute().data or []
        }
        regras_parcelamento_por_apolice = {
            r["apolice"]: r
            for r in client.table("regras_parcelamento").select("*").execute().data or []
        }
        inseridas = 0
        for linha in lote.linhas:
            if linha.cliente:
                cliente_id = resolver_cliente_por_nome(linha.cliente, clientes_existentes)
            else:
                cliente_id = resolver_cliente_por_apolice(linha.apolice, clientes_existentes)

            regra = regras_por_cliente.get(cliente_id)
            # se a própria seguradora já diz a categoria (ex.: Hapvida marca
            # repique/reagenciamento por linha), isso tem prioridade sobre a
            # classificação genérica por regra de cliente.
            categoria = linha.categoria_sugerida or classificar(linha.parcela, regra)

            client.table("movimentacoes_comissao").insert(
                {
                    "lote_id": lote_id,
                    "cliente_id": cliente_id,
                    "tipo": linha.tipo,
                    "apolice": linha.apolice,
                    "parcela": linha.parcela,
                    "percentual_comissao": linha.percentual_comissao,
                    "valor_parcela": linha.valor_parcela,
                    "valor_comissao": linha.valor_comissao,
                    "categoria": categoria,
                }
            ).execute()
            inseridas += 1

            if categoria == "vitalicio" and linha.apolice:
                provisionar_vitalicio(cliente_id, linha.apolice, linha.valor_comissao, regra)

            regra_parcelamento = regras_parcelamento_por_apolice.get(linha.apolice)
            if regra_parcelamento and linha.tipo == "pagamento":
                provisionar_parcelamento(
                    cliente_id, linha.apolice, linha.valor_comissao, linha.parcela, regra_parcelamento
                )
            elif (
                seguradora_nome == "Suhai"
                and linha.tipo == "pagamento"
                and bate_com_formula(linha.valor_comissao, linha.valor_parcela, linha.percentual_comissao)
            ):
                # Regra da Suhai (planilha "Novo Suhai", 73%): dá pra prever
                # quantas parcelas futuras recebem comissão só pelo percentual,
                # sem precisar cadastrar nada por apólice.
                regra_suhai = {"total_parcelas": parcelas_enquadradas(linha.percentual_comissao)}
                provisionar_parcelamento(
                    cliente_id, linha.apolice, linha.valor_comissao, linha.parcela, regra_suhai
                )
    except Exception as e:
        # desfaz o lote parcial para permitir nova tentativa (o hash_arquivo
        # senão ficaria "já importado" com dados incompletos, travado).
        client.table("movimentacoes_comissao").delete().eq("lote_id", lote_id).execute()
        client.table("auditoria_alertas").delete().eq("lote_id", lote_id).execute()
        if ofx_transacao_id:
            client.table("ofx_transacoes").update({"conciliado": False}).eq("id", ofx_transacao_id).execute()
        client.table("lotes_comissao").delete().eq("id", lote_id).execute()
        st.error(f"Erro ao importar (revertido, pode tentar de novo): {e}")
        st.stop()

    if status == "conciliado":
        st.success(f"Lote conciliado automaticamente! {inseridas} movimentações registradas.")
    elif status == "divergente":
        st.error(
            f"⚠️ {inseridas} movimentações registradas, mas o crédito bancário correspondente "
            "foi encontrado em conta de OUTRA empresa. Alerta de auditoria criado — revise antes de aceitar."
        )
    else:
        st.warning(
            f"{inseridas} movimentações registradas. Nenhum crédito bancário correspondente foi "
            "encontrado ainda — importe o OFX do período para tentar conciliar."
        )
