"""Lógica compartilhada de inserir uma transação bancária e tentar
conciliar automaticamente — usada tanto pelo importador manual de OFX
quanto pela sincronização via Pluggy (Open Finance). Mesma regra nos
dois casos, nessa ordem: lote de comissão pendente (mesma empresa/data/
valor líquido) > lançamento previsto (mesma empresa/tipo/valor) >
despesa/receita fixa de valor variável, reconhecida por
regras_identificacao (mesmo mês do vencimento provisionado)."""

from __future__ import annotations

from regras_identificacao import sugerir


def inserir_e_conciliar(
    client,
    *,
    ofx_importacao_id: str,
    conta_id: str,
    fit_id: str | None,
    data: str,
    valor: float,
    descricao: str | None,
    regras_identificacao: list[dict],
) -> bool:
    """Insere a transação em ofx_transacoes — levanta
    postgrest.exceptions.APIError (code '23505', unique_violation) se
    (conta_bancaria_id, fit_id) já existir, ou seja, se for uma
    duplicata; quem chama decide como tratar/contar isso — e tenta
    conciliar automaticamente. Retorna True se conciliou algo."""
    txn = (
        client.table("ofx_transacoes")
        .insert(
            {
                "ofx_importacao_id": ofx_importacao_id,
                "conta_bancaria_id": conta_id,
                "fit_id": fit_id or None,
                "data": data,
                "valor": valor,
                "descricao": descricao,
            }
        )
        .execute()
    )
    txn_id = txn.data[0]["id"]

    conta = client.table("contas_bancarias").select("empresa_id").eq("id", conta_id).execute().data[0]

    # 1) lote de comissão pendente da mesma empresa/data/valor líquido
    candidatos = (
        client.table("lotes_comissao")
        .select("id, valor_liquido")
        .eq("empresa_id", conta["empresa_id"])
        .eq("data_pagamento", data)
        .eq("status", "pendente")
        .execute()
        .data
        or []
    )
    match = next((c for c in candidatos if abs(c["valor_liquido"] - valor) < 0.005), None)
    if match:
        client.table("lotes_comissao").update(
            {"status": "conciliado", "ofx_transacao_id": txn_id}
        ).eq("id", match["id"]).execute()
        client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
        return True

    # 2) lançamento previsto (contas a pagar/receber) da mesma
    # empresa/tipo/valor — aceita alguns dias de diferença na data, já
    # que o crédito/débito pode cair antes/depois do vencimento previsto.
    tipo_esperado = "receber" if valor > 0 else "pagar"
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
    match_previsto = next((p for p in previstos if abs(p["valor"] - abs(valor)) < 0.005), None)
    if match_previsto:
        client.table("lancamentos_previstos").update(
            {"status": "pago", "data_pagamento": data, "ofx_transacao_id": txn_id}
        ).eq("id", match_previsto["id"]).execute()
        client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
        return True

    # 3) despesa/receita fixa de valor variável (ex.: conta de luz) —
    # reconhece o fornecedor/cliente pela descrição já ensinada
    # (Classificar Lançamentos) e casa com uma previsão do MESMO MÊS,
    # mesmo que o valor seja diferente do provisionado. Atualiza o valor
    # (e o das próximas ocorrências da mesma recorrência) pelo real.
    regra_desc = sugerir(regras_identificacao, descricao)
    if regra_desc and (regra_desc.get("fornecedor_id") or regra_desc.get("cliente_id")):
        mes_txn = data[:7]
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
            valor_real = abs(valor)
            client.table("lancamentos_previstos").update(
                {
                    "status": "pago",
                    "data_pagamento": data,
                    "ofx_transacao_id": txn_id,
                    "valor": valor_real,
                }
            ).eq("id", escolhido["id"]).execute()
            if escolhido.get("grupo_id"):
                # propaga o valor real pras próximas ocorrências já
                # provisionadas da mesma recorrência.
                client.table("lancamentos_previstos").update({"valor": valor_real}).eq(
                    "grupo_id", escolhido["grupo_id"]
                ).eq("status", "previsto").execute()
            client.table("ofx_transacoes").update({"conciliado": True}).eq("id", txn_id).execute()
            return True

    return False
