"""Geração de parcelas e recorrências para lançamentos previstos
(contas a pagar/receber que ainda vão acontecer)."""

import calendar
from dataclasses import dataclass
from datetime import date


def somar_meses(data: date, meses: int) -> date:
    """Soma meses a uma data, ajustando o dia se o mês destino for mais curto
    (ex.: 31/01 + 1 mês -> 28/02, não 03/03)."""
    mes_total = data.month - 1 + meses
    ano = data.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(data.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


@dataclass
class ParcelaGerada:
    parcela_atual: int | None
    parcela_total: int | None
    valor: float
    data_vencimento: date
    recorrente: bool = False


def gerar_parcelas(valor_total: float, num_parcelas: int, primeira_data: date) -> list[ParcelaGerada]:
    """Divide valor_total em num_parcelas mensais. A última parcela absorve
    a diferença de arredondamento, para a soma bater exatamente com o total."""
    if num_parcelas < 1:
        raise ValueError("num_parcelas deve ser >= 1")
    valor_parcela = round(valor_total / num_parcelas, 2)
    parcelas = []
    acumulado = 0.0
    for i in range(1, num_parcelas + 1):
        valor = valor_parcela if i < num_parcelas else round(valor_total - acumulado, 2)
        acumulado += valor
        parcelas.append(
            ParcelaGerada(
                parcela_atual=i,
                parcela_total=num_parcelas,
                valor=valor,
                data_vencimento=somar_meses(primeira_data, i - 1),
            )
        )
    return parcelas


def gerar_recorrencia(valor: float, primeira_data: date, quantidade_meses: int = 12) -> list[ParcelaGerada]:
    """Gera ocorrências futuras de uma despesa/receita fixa (mesmo valor todo
    mês). Gera só os próximos `quantidade_meses` — quando estiverem
    terminando, cadastre de novo para estender."""
    if quantidade_meses < 1:
        raise ValueError("quantidade_meses deve ser >= 1")
    return [
        ParcelaGerada(
            parcela_atual=None,
            parcela_total=None,
            valor=valor,
            data_vencimento=somar_meses(primeira_data, i),
            recorrente=True,
        )
        for i in range(quantidade_meses)
    ]
