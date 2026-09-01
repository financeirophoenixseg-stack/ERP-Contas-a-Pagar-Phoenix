"""DRE e Balanço Patrimonial — CALCULADOS a partir dos lançamentos já
classificados (plano de contas, comissões, lançamentos previstos pagos).

Deliberadamente não é a IA que "escreve" esses números: ela pode ajudar a
sugerir a classificação de um lançamento (ver `regras_identificacao.py`),
mas o relatório em si é sempre uma soma determinística — para não arriscar
apresentar uma demonstração financeira com números inventados.
"""

from dataclasses import dataclass, field


@dataclass
class LinhaDRE:
    tipo_conta: str  # 'receita' | 'despesa'
    categoria: str
    valor: float  # sempre positivo


def montar_dre(linhas: list[LinhaDRE]) -> dict:
    receitas: dict[str, float] = {}
    despesas: dict[str, float] = {}
    for linha in linhas:
        alvo = receitas if linha.tipo_conta == "receita" else despesas
        alvo[linha.categoria] = alvo.get(linha.categoria, 0.0) + linha.valor

    total_receitas = round(sum(receitas.values()), 2)
    total_despesas = round(sum(despesas.values()), 2)
    return {
        "receitas": receitas,
        "despesas": despesas,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "resultado": round(total_receitas - total_despesas, 2),
    }


def montar_balanco(caixa: float, contas_a_receber: float, contas_a_pagar: float) -> dict:
    """Balanço simplificado (não é contabilidade de partidas dobradas real):
    Ativo = caixa (soma do que passou pelo banco) + contas a receber
    previstas; Passivo = contas a pagar previstas; Patrimônio Líquido é a
    diferença (Ativo - Passivo), não uma conta de capital rastreada à parte."""
    ativo_circulante = round(caixa, 2) + round(contas_a_receber, 2)
    passivo_circulante = round(contas_a_pagar, 2)
    return {
        "ativo": {"Caixa e Bancos": round(caixa, 2), "Contas a Receber": round(contas_a_receber, 2)},
        "passivo": {"Contas a Pagar": passivo_circulante},
        "total_ativo": round(ativo_circulante, 2),
        "total_passivo": passivo_circulante,
        "patrimonio_liquido": round(ativo_circulante - passivo_circulante, 2),
    }


def calcular_dre(client, data_inicio: str, data_fim: str, empresa_id: str | None = None) -> dict:
    """Monta o DRE do período consultando o Supabase — mesma lógica usada
    pela tela DRE e Balanço (`pages/9_DRE_e_Balanco.py`), extraída aqui pra
    ser reaproveitada também pelo assistente financeiro (`assistente_financeiro.py`)
    sem duplicar a consulta e correr o risco dos dois números divergirem.
    `data_inicio`/`data_fim` no formato 'AAAA-MM-DD'."""
    linhas_dre: list[LinhaDRE] = []

    query = (
        client.table("lotes_comissao")
        .select("id, empresa_id, data_pagamento, valor_irrf, valor_iss, valor_inss, valor_pis_cofins_csll")
        .gte("data_pagamento", data_inicio)
        .lte("data_pagamento", data_fim)
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    lotes_periodo = query.execute().data or []
    lote_ids = [l["id"] for l in lotes_periodo]

    if lote_ids:
        movimentacoes = (
            client.table("movimentacoes_comissao").select("valor_comissao").in_("lote_id", lote_ids).execute().data
            or []
        )
        total_comissoes = sum(m["valor_comissao"] for m in movimentacoes)
        if total_comissoes:
            if total_comissoes > 0:
                linhas_dre.append(LinhaDRE("receita", "Receita de Comissões (bruto)", total_comissoes))
            else:
                linhas_dre.append(
                    LinhaDRE("despesa", "Cancelamentos/Estornos de Comissão (líquido negativo)", -total_comissoes)
                )

        total_impostos = sum(
            (l["valor_irrf"] or 0) + (l["valor_iss"] or 0) + (l["valor_inss"] or 0) + (l["valor_pis_cofins_csll"] or 0)
            for l in lotes_periodo
        )
        if total_impostos:
            linhas_dre.append(
                LinhaDRE("despesa", "Impostos sobre Comissões (IRRF/ISS/INSS/PIS-COFINS-CSLL)", total_impostos)
            )

    query = (
        client.table("lancamentos_previstos")
        .select("tipo, valor, descricao, plano_contas(nome)")
        .eq("status", "pago")
        .gte("data_pagamento", data_inicio)
        .lte("data_pagamento", data_fim)
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    for lanc in query.execute().data or []:
        categoria = (lanc.get("plano_contas") or {}).get("nome") or (
            "Outras Receitas" if lanc["tipo"] == "receber" else "Outras Despesas"
        )
        linhas_dre.append(LinhaDRE("receita" if lanc["tipo"] == "receber" else "despesa", categoria, lanc["valor"]))

    query = (
        client.table("ofx_transacoes")
        .select("valor, plano_contas(nome, tipo), contas_bancarias(empresa_id)")
        .not_.is_("plano_conta_id", "null")
        .gte("data", data_inicio)
        .lte("data", data_fim)
    )
    for txn in query.execute().data or []:
        if empresa_id and txn["contas_bancarias"]["empresa_id"] != empresa_id:
            continue
        conta = txn.get("plano_contas") or {}
        if conta.get("tipo") in ("receita", "despesa"):
            linhas_dre.append(LinhaDRE(conta["tipo"], conta["nome"], abs(txn["valor"])))

    return montar_dre(linhas_dre)


def calcular_balanco(client, empresa_id: str | None = None) -> dict:
    """Monta o balanço simplificado consultando o Supabase — mesma lógica
    usada pela tela DRE e Balanço. Diferente do DRE, não é filtrado por
    período: 'Caixa' é a soma de todo o histórico de OFX já importado."""
    todas_transacoes = client.table("ofx_transacoes").select("valor, contas_bancarias(empresa_id)").execute().data or []
    caixa = sum(
        t["valor"] for t in todas_transacoes if not empresa_id or t["contas_bancarias"]["empresa_id"] == empresa_id
    )

    query_receber = client.table("lancamentos_previstos").select("valor, empresa_id").eq("status", "previsto").eq("tipo", "receber")
    query_pagar = client.table("lancamentos_previstos").select("valor, empresa_id").eq("status", "previsto").eq("tipo", "pagar")
    if empresa_id:
        query_receber = query_receber.eq("empresa_id", empresa_id)
        query_pagar = query_pagar.eq("empresa_id", empresa_id)
    contas_a_receber = sum(r["valor"] for r in query_receber.execute().data or [])
    contas_a_pagar = sum(r["valor"] for r in query_pagar.execute().data or [])

    return montar_balanco(caixa, contas_a_receber, contas_a_pagar)
