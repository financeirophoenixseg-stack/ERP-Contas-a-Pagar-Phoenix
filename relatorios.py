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
