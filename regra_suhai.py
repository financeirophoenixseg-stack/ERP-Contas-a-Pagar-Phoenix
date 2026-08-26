"""Regra de cálculo de comissão da Suhai ("Cálculo Comissão - Novo Suhai.xlsx",
aba "Planilha de Cálculo 73%", fórmulas extraídas diretamente do arquivo).

Total Comissão = Prêmio × percentual. Suhai paga essa comissão em até
`parcelas_enquadradas` parcelas (não necessariamente = nº de parcelas do
prêmio da apólice): pega 73% do valor de uma parcela e divide pela
comissão de uma parcela — como comissão-por-parcela = valor_parcela ×
percentual e 73%-do-valor = valor_parcela × 0.73, o valor_parcela se
cancela na divisão: a razão só depende do percentual de comissão.

    parcelas_enquadradas = INT(0.73 / percentual)

Isso permite prever, a partir de uma única parcela observada, quantas
parcelas futuras ainda vão receber comissão (e com qual valor, assumindo
prêmio/percentual constantes) — sem precisar cadastrar nada por apólice.

Só se aplica a linhas do tipo 'pagamento' (comissão normal de vigência) —
adiantamento/cancelamento/recuperação não seguem essa fórmula (o valor
delas não é valor_parcela × percentual).
"""

LIMIAR = 0.73
TOLERANCIA_PADRAO = 0.05


def parcelas_enquadradas(percentual_comissao: float) -> int:
    """Quantas parcelas recebem comissão, dado o percentual (ex.: 20.0 = 20%)."""
    taxa = (percentual_comissao or 0) / 100
    if taxa <= 0:
        return 0
    return int(LIMIAR / taxa)


def comissao_esperada(valor_parcela: float, percentual_comissao: float) -> float:
    return round((valor_parcela or 0) * (percentual_comissao or 0) / 100, 2)


def bate_com_formula(
    valor_comissao_real: float,
    valor_parcela: float,
    percentual_comissao: float,
    tolerancia: float = TOLERANCIA_PADRAO,
) -> bool:
    """Confirma que esta linha segue a regra de comissão de vigência (e não
    é um adiantamento/cancelamento, que tem valor calculado diferente)."""
    esperado = comissao_esperada(valor_parcela, percentual_comissao)
    return abs(esperado - valor_comissao_real) <= tolerancia
