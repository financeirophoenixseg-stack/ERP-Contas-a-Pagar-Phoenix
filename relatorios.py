"""DRE e Balanço Patrimonial — CALCULADOS a partir dos lançamentos já
classificados (plano de contas, comissões, lançamentos previstos pagos).

Deliberadamente não é a IA que "escreve" esses números: ela pode ajudar a
sugerir a classificação de um lançamento (ver `regras_identificacao.py`),
mas o relatório em si é sempre uma soma determinística — para não arriscar
apresentar uma demonstração financeira com números inventados.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta


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


# ---------------------------------------------------------------------------
# Relatórios gerenciais (tela "Relatórios") — mesma disciplina do DRE/Balanço
# acima: tudo somado a partir dos dados reais já lançados, nada estimado ou
# escrito pela IA.
# ---------------------------------------------------------------------------


def calcular_fluxo_projetado(client, empresa_id: str | None = None) -> dict:
    """Fluxo de caixa PROJETADO (diferente do realizado, que é feito a partir
    do OFX): agrupa os lançamentos previstos (ainda não pagos) em faixas de
    dias até o vencimento — atrasado, 0-30, 31-60, 61-90 e mais de 90 dias —
    somando entradas (a receber) e saídas (a pagar) de cada faixa. Soma
    também o caixa atual (mesma base do balanço) pra dar o saldo projetado
    acumulado até o fim de cada faixa."""
    hoje = date.today()
    query = client.table("lancamentos_previstos").select("tipo, valor, data_vencimento, empresa_id").eq(
        "status", "previsto"
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    itens = query.execute().data or []

    faixas = [
        ("Atrasado", None, -1),
        ("Hoje a 30 dias", 0, 30),
        ("31 a 60 dias", 31, 60),
        ("61 a 90 dias", 61, 90),
        ("Mais de 90 dias", 91, None),
    ]
    buckets = []
    for nome, ini, fim in faixas:
        entradas = 0.0
        saidas = 0.0
        for i in itens:
            dias_ate = (date.fromisoformat(i["data_vencimento"]) - hoje).days
            dentro = (ini is None or dias_ate >= ini) and (fim is None or dias_ate <= fim)
            if not dentro:
                continue
            if i["tipo"] == "receber":
                entradas += i["valor"]
            else:
                saidas += i["valor"]
        buckets.append(
            {
                "periodo": nome,
                "entradas": round(entradas, 2),
                "saidas": round(saidas, 2),
                "saldo_liquido": round(entradas - saidas, 2),
            }
        )

    caixa_atual = calcular_balanco(client, empresa_id=empresa_id)["ativo"]["Caixa e Bancos"]
    saldo_acumulado = caixa_atual
    for b in buckets:
        saldo_acumulado = round(saldo_acumulado + b["saldo_liquido"], 2)
        b["saldo_projetado_acumulado"] = saldo_acumulado

    return {"caixa_atual": round(caixa_atual, 2), "buckets": buckets}


def calcular_aging(client, tipo: str, empresa_id: str | None = None) -> dict:
    """Aging de contas a pagar/receber: lançamentos previstos já vencidos,
    agrupados em faixas de dias em atraso (0-30 / 31-60 / 61-90 / mais de
    90). `tipo`: 'pagar' ou 'receber'."""
    hoje = date.today()
    query = (
        client.table("lancamentos_previstos")
        .select("descricao, valor, data_vencimento, clientes(nome), fornecedores(nome)")
        .eq("status", "previsto")
        .eq("tipo", tipo)
        .lt("data_vencimento", hoje.isoformat())
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    itens = query.execute().data or []

    ordem_faixas = ["0-30 dias", "31-60 dias", "61-90 dias", "Mais de 90 dias"]
    totais_por_faixa = {f: 0.0 for f in ordem_faixas}
    detalhes = []
    for i in itens:
        dias = (hoje - date.fromisoformat(i["data_vencimento"])).days
        if dias <= 30:
            faixa = "0-30 dias"
        elif dias <= 60:
            faixa = "31-60 dias"
        elif dias <= 90:
            faixa = "61-90 dias"
        else:
            faixa = "Mais de 90 dias"
        totais_por_faixa[faixa] += i["valor"]
        terceiro = (i.get("clientes") or {}).get("nome") or (i.get("fornecedores") or {}).get("nome") or "-"
        detalhes.append(
            {
                "descricao": i["descricao"],
                "terceiro": terceiro,
                "valor": round(i["valor"], 2),
                "dias_atraso": dias,
                "faixa": faixa,
            }
        )

    return {
        "total": round(sum(totais_por_faixa.values()), 2),
        "por_faixa": [{"faixa": f, "valor": round(totais_por_faixa[f], 2)} for f in ordem_faixas],
        "itens": sorted(detalhes, key=lambda x: -x["dias_atraso"]),
    }


def calcular_comissoes_por_seguradora(client, data_inicio: str, data_fim: str, empresa_id: str | None = None) -> list[dict]:
    """Comissões agrupadas por seguradora no período — bruto, líquido,
    quantidade de lotes e quantos estão pendentes/divergentes — ordenado do
    maior líquido pro menor."""
    query = (
        client.table("lotes_comissao")
        .select("valor_bruto, valor_liquido, status, seguradoras(nome)")
        .gte("data_pagamento", data_inicio)
        .lte("data_pagamento", data_fim)
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    lotes = query.execute().data or []

    por_seguradora: dict[str, dict] = {}
    for l in lotes:
        nome = (l.get("seguradoras") or {}).get("nome") or "(sem seguradora)"
        s = por_seguradora.setdefault(
            nome, {"bruto": 0.0, "liquido": 0.0, "qtd_lotes": 0, "pendente": 0, "divergente": 0}
        )
        s["bruto"] += l["valor_bruto"] or 0
        s["liquido"] += l["valor_liquido"] or 0
        s["qtd_lotes"] += 1
        if l["status"] == "pendente":
            s["pendente"] += 1
        elif l["status"] == "divergente":
            s["divergente"] += 1

    resultado = [
        {
            "seguradora": nome,
            "valor_bruto": round(v["bruto"], 2),
            "valor_liquido": round(v["liquido"], 2),
            "qtd_lotes": v["qtd_lotes"],
            "pendente": v["pendente"],
            "divergente": v["divergente"],
        }
        for nome, v in por_seguradora.items()
    ]
    return sorted(resultado, key=lambda x: -x["valor_liquido"])


def calcular_comissoes_por_cliente(
    client, data_inicio: str, data_fim: str, empresa_id: str | None = None, limite: int = 20
) -> list[dict]:
    """Ranking de clientes por valor de comissão gerada no período (soma de
    movimentacoes_comissao.valor_comissao dos lotes pagos dentro do
    período), do maior pro menor."""
    query_lotes = (
        client.table("lotes_comissao").select("id, empresa_id").gte("data_pagamento", data_inicio).lte("data_pagamento", data_fim)
    )
    if empresa_id:
        query_lotes = query_lotes.eq("empresa_id", empresa_id)
    lotes = query_lotes.execute().data or []
    lote_ids = [l["id"] for l in lotes]
    if not lote_ids:
        return []

    movimentacoes = (
        client.table("movimentacoes_comissao").select("valor_comissao, clientes(nome)").in_("lote_id", lote_ids).execute().data
        or []
    )

    por_cliente: dict[str, float] = {}
    for m in movimentacoes:
        nome = (m.get("clientes") or {}).get("nome") or "(sem cliente)"
        por_cliente[nome] = por_cliente.get(nome, 0.0) + m["valor_comissao"]

    ranking = sorted(por_cliente.items(), key=lambda kv: -kv[1])[:limite]
    return [{"cliente": nome, "valor_comissao": round(v, 2)} for nome, v in ranking]


def calcular_impostos_retidos(client, data_inicio: str, data_fim: str, empresa_id: str | None = None) -> dict:
    """Consolida os impostos retidos sobre comissão (IRRF/ISS/INSS/PIS-
    COFINS-CSLL) de todos os lotes do período — útil pro planejamento
    tributário/contador, sem precisar somar lote por lote na mão."""
    query = (
        client.table("lotes_comissao")
        .select("valor_irrf, valor_iss, valor_inss, valor_pis_cofins_csll")
        .gte("data_pagamento", data_inicio)
        .lte("data_pagamento", data_fim)
    )
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    lotes = query.execute().data or []

    total_irrf = sum(l["valor_irrf"] or 0 for l in lotes)
    total_iss = sum(l["valor_iss"] or 0 for l in lotes)
    total_inss = sum(l["valor_inss"] or 0 for l in lotes)
    total_pis = sum(l["valor_pis_cofins_csll"] or 0 for l in lotes)

    return {
        "irrf": round(total_irrf, 2),
        "iss": round(total_iss, 2),
        "inss": round(total_inss, 2),
        "pis_cofins_csll": round(total_pis, 2),
        "total": round(total_irrf + total_iss + total_inss + total_pis, 2),
    }


def calcular_evolucao_mensal(client, meses: int = 12, empresa_id: str | None = None) -> list[dict]:
    """Evolução mensal de receitas/despesas reais (OFX) — igual ao gráfico
    do Dashboard, mas com período configurável (o Dashboard é fixo em 6
    meses) e devolvendo os dados brutos pra tabela/exportação."""
    hoje = date.today()
    inicio = (hoje.replace(day=1) - timedelta(days=31 * max(meses, 1))).isoformat()
    query = client.table("ofx_transacoes").select("data, valor, contas_bancarias(empresa_id)").gte("data", inicio)
    transacoes = query.execute().data or []
    if empresa_id:
        transacoes = [t for t in transacoes if (t.get("contas_bancarias") or {}).get("empresa_id") == empresa_id]

    por_mes: dict[str, dict[str, float]] = {}
    for t in transacoes:
        chave = t["data"][:7]
        por_mes.setdefault(chave, {"receitas": 0.0, "despesas": 0.0})
        if t["valor"] >= 0:
            por_mes[chave]["receitas"] += t["valor"]
        else:
            por_mes[chave]["despesas"] += abs(t["valor"])

    meses_ordenados = sorted(por_mes.keys())[-meses:]
    return [
        {
            "mes": m,
            "receitas": round(por_mes[m]["receitas"], 2),
            "despesas": round(por_mes[m]["despesas"], 2),
            "resultado": round(por_mes[m]["receitas"] - por_mes[m]["despesas"], 2),
        }
        for m in meses_ordenados
    ]
