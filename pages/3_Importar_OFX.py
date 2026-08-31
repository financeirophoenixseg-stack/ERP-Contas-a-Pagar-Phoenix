import hashlib
import html

import streamlit as st
from postgrest.exceptions import APIError

import layout
from db import get_client
from formatacao import data_br, moeda
from ofx_parser import decode_ofx_bytes, parse_ofx
from regras_identificacao import sugerir

st.set_page_config(page_title="Importar OFX", layout="wide")
layout.aplicar_logo()
st.title("Importar extrato OFX")
st.caption(
    "A empresa é identificada automaticamente pela combinação banco + agência + conta."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()


@st.cache_data(ttl=30)
def carregar_contas():
    rows = (
        client.table("contas_bancarias")
        .select("id, banco, agencia, conta, empresas(nome)")
        .execute()
        .data
        or []
    )
    return {(r["banco"], r["agencia"], r["conta"]): r for r in rows}


contas_por_chave = carregar_contas()

arquivo = st.file_uploader("Selecione o arquivo .ofx", type=["ofx"])
if not arquivo:
    st.stop()

raw = arquivo.getvalue()
hash_arquivo = hashlib.sha256(raw).hexdigest()

ja_importado = (
    client.table("ofx_importacoes").select("id").eq("hash_arquivo", hash_arquivo).execute().data
)
if ja_importado:
    st.warning("Este arquivo já foi importado anteriormente. Nenhuma ação será feita.")
    st.stop()

texto = decode_ofx_bytes(raw)
transacoes = parse_ofx(texto)

if not transacoes:
    st.error("Nenhuma movimentação encontrada neste arquivo.")
    st.stop()

linhas = []
sem_conta_cadastrada = set()
for t in transacoes:
    chave = (t.account.bank_id, t.account.branch_id, t.account.acct_id)
    conta = contas_por_chave.get(chave)
    empresa = conta["empresas"]["nome"] if conta and conta.get("empresas") else None
    if not conta:
        sem_conta_cadastrada.add(chave)
    linhas.append(
        {
            "Empresa": empresa or "⚠️ conta não cadastrada",
            "Banco/Agência/Conta": f"{t.account.bank_id}/{t.account.branch_id}/{t.account.acct_id}",
            "Data": t.date,
            "Descrição": t.description,
            "Valor": t.amount,
            "_conta_id": conta["id"] if conta else None,
            "_fit_id": t.fit_id,
        }
    )

total_creditos = sum(linha["Valor"] for linha in linhas if linha["Valor"] >= 0)
total_debitos = sum(linha["Valor"] for linha in linhas if linha["Valor"] < 0)

st.markdown(
    layout._compacto(
        f"""
        <div class="card" style="padding:18px 22px;display:flex;align-items:center;justify-content:space-between;">
          <div style="display:flex;align-items:center;gap:14px;">
            <div style="width:38px;height:38px;border-radius:10px;background:rgba(30,95,191,0.09);display:flex;align-items:center;justify-content:center;color:#1E5FBF;">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h6l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M13 3v5h5"/></svg>
            </div>
            <div>
              <div style="font-size:13.5px;font-weight:600;color:#10233F;">{html.escape(arquivo.name)}</div>
              <div style="font-size:12px;color:#8592A8;margin-top:1px;">{len(linhas)} transações encontradas</div>
            </div>
          </div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

layout.cartoes_kpi(
    [
        {"icone": "check", "label": "Total de transações", "valor": str(len(linhas))},
        {"icone": "receber", "cor": "#0ca30c", "label": "Créditos", "valor": moeda(total_creditos), "valor_cor": "#0ca30c"},
        {"icone": "pagar", "label": "Débitos", "valor": moeda(total_debitos)},
    ]
)

if sem_conta_cadastrada:
    st.warning(
        "Contas não cadastradas encontradas no arquivo: "
        + ", ".join(f"{b}/{ag}/{c}" for b, ag, c in sem_conta_cadastrada)
        + ". Cadastre-as em **Configurações** antes de importar, para que a empresa "
        "seja identificada automaticamente."
    )

linhas_tabela = []
for linha in linhas:
    empresa_html = (
        '<span class="pill pill-amber">não cadastrada</span>'
        if linha["_conta_id"] is None
        else html.escape(linha["Empresa"])
    )
    cor_valor = "#0ca30c" if linha["Valor"] >= 0 else "#10233F"
    linhas_tabela.append(
        f"""<tr>
            <td>{empresa_html}</td>
            <td style="color:#8592A8;">{html.escape(linha['Banco/Agência/Conta'])}</td>
            <td>{data_br(linha['Data'])}</td>
            <td>{html.escape(linha['Descrição'] or '')}</td>
            <td style="text-align:right;font-weight:700;color:{cor_valor};">{'+' if linha['Valor'] >= 0 else ''}{moeda(linha['Valor'])}</td>
        </tr>"""
    )

st.markdown(
    layout._compacto(
        f"""
        <div class="card" style="padding:16px 22px;">
          <table class="tabela-custom">
            <thead>
              <tr>
                <th>Empresa</th>
                <th>Banco / Agência / Conta</th>
                <th>Data</th>
                <th>Descrição</th>
                <th style="text-align:right;">Valor</th>
              </tr>
            </thead>
            <tbody>
              {''.join(linhas_tabela)}
            </tbody>
          </table>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

pode_importar = all(linha["_conta_id"] for linha in linhas)
if not pode_importar:
    st.info("Cadastre as contas faltantes e reenvie o arquivo para importar.")
    st.stop()

if st.button("Confirmar importação", type="primary"):
    inseridas, duplicadas, conciliadas = 0, 0, 0
    regras_identificacao = client.table("regras_identificacao").select("*").execute().data or []
    conta_ids_no_arquivo = {linha["_conta_id"] for linha in linhas}
    importacao_ids = {}
    for conta_id in conta_ids_no_arquivo:
        resp = (
            client.table("ofx_importacoes")
            .insert(
                {
                    "conta_bancaria_id": conta_id,
                    "arquivo_nome": arquivo.name,
                    "hash_arquivo": hash_arquivo,
                }
            )
            .execute()
        )
        importacao_ids[conta_id] = resp.data[0]["id"]

    for linha in linhas:
        try:
            txn = (
                client.table("ofx_transacoes")
                .insert(
                    {
                        "ofx_importacao_id": importacao_ids[linha["_conta_id"]],
                        "conta_bancaria_id": linha["_conta_id"],
                        "fit_id": linha["_fit_id"] or None,
                        "data": linha["Data"],
                        "valor": linha["Valor"],
                        "descricao": linha["Descrição"],
                    }
                )
                .execute()
            )
            inseridas += 1

            # Tenta conciliar com algum lote de comissao ainda pendente da
            # mesma empresa, mesma data e mesmo valor liquido.
            conta = client.table("contas_bancarias").select("empresa_id").eq("id", linha["_conta_id"]).execute().data[0]
            candidatos = (
                client.table("lotes_comissao")
                .select("id, valor_liquido")
                .eq("empresa_id", conta["empresa_id"])
                .eq("data_pagamento", linha["Data"])
                .eq("status", "pendente")
                .execute()
                .data
                or []
            )
            match = next((c for c in candidatos if abs(c["valor_liquido"] - linha["Valor"]) < 0.005), None)
            txn_id = txn.data[0]["id"]
            if match:
                client.table("lotes_comissao").update(
                    {"status": "conciliado", "ofx_transacao_id": txn_id}
                ).eq("id", match["id"]).execute()
                client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
                conciliadas += 1
            else:
                # Tenta conciliar com uma conta a pagar/receber prevista
                # (mesma empresa, mesmo tipo pela direção do valor, mesmo
                # valor). Aceita alguns dias de diferença na data, já que o
                # crédito/débito pode cair antes/depois do vencimento previsto.
                tipo_esperado = "receber" if linha["Valor"] > 0 else "pagar"
                previstos = (
                    client.table("lancamentos_previstos")
                    .select("id, valor")
                    .eq("empresa_id", conta["empresa_id"])
                    .eq("tipo", tipo_esperado)
                    .eq("status", "previsto")
                    .execute()
                    .data
                    or []
                )
                match_previsto = next(
                    (p for p in previstos if abs(p["valor"] - abs(linha["Valor"])) < 0.005), None
                )
                if match_previsto:
                    client.table("lancamentos_previstos").update(
                        {"status": "pago", "data_pagamento": linha["Data"], "ofx_transacao_id": txn_id}
                    ).eq("id", match_previsto["id"]).execute()
                    client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
                    conciliadas += 1
                else:
                    # Última tentativa: despesa/receita fixa cujo valor varia
                    # (ex.: conta de luz) — reconhece o fornecedor/cliente pela
                    # descrição já ensinada (Classificar Lançamentos) e casa
                    # com uma previsão do MESMO MÊS, mesmo que o valor seja
                    # diferente do provisionado. Atualiza o valor (e o das
                    # próximas ocorrências da mesma recorrência) pelo real.
                    regra_desc = sugerir(regras_identificacao, linha["Descrição"])
                    if regra_desc and (regra_desc.get("fornecedor_id") or regra_desc.get("cliente_id")):
                        mes_txn = linha["Data"][:7]
                        query = (
                            client.table("lancamentos_previstos")
                            .select("id, grupo_id, valor, data_vencimento")
                            .eq("empresa_id", conta["empresa_id"])
                            .eq("tipo", tipo_esperado)
                            .eq("status", "previsto")
                        )
                        if regra_desc.get("fornecedor_id"):
                            query = query.eq("fornecedor_id", regra_desc["fornecedor_id"])
                        else:
                            query = query.eq("cliente_id", regra_desc["cliente_id"])
                        candidatos_fixa = query.execute().data or []
                        candidatos_mes = [c for c in candidatos_fixa if (c["data_vencimento"] or "")[:7] == mes_txn]
                        if len(candidatos_mes) == 1:
                            escolhido = candidatos_mes[0]
                            valor_real = abs(linha["Valor"])
                            client.table("lancamentos_previstos").update(
                                {
                                    "status": "pago",
                                    "data_pagamento": linha["Data"],
                                    "ofx_transacao_id": txn_id,
                                    "valor": valor_real,
                                }
                            ).eq("id", escolhido["id"]).execute()
                            if escolhido.get("grupo_id"):
                                # propaga o valor real para as proximas ocorrencias
                                # ja provisionadas da mesma recorrencia (ex.: conta fixa).
                                client.table("lancamentos_previstos").update({"valor": valor_real}).eq(
                                    "grupo_id", escolhido["grupo_id"]
                                ).eq("status", "previsto").execute()
                            client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
                            conciliadas += 1
        except APIError as e:
            if e.code == "23505":  # unique_violation: (conta_bancaria_id, fit_id) já existe
                duplicadas += 1
            else:
                raise

    msg = f"Importação concluída: {inseridas} novas movimentações, {duplicadas} já existiam."
    if conciliadas:
        msg += f" {conciliadas} lote(s) de comissão pendente(s) foram conciliados automaticamente."
    st.success(msg)
