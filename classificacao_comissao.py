"""Classifica uma movimentação de comissão como agenciamento ou vitalícia,
com base numa regra cadastrada por cliente (nº de parcelas de agenciamento).

Agenciamento: comissão de entrada, parcelas iniciais, % alto.
Vitalícia: comissão recorrente, continua enquanto a apólice estiver ativa,
% baixo. Sem regra cadastrada pro cliente, não classificamos (retorna
None) — não adivinhamos por percentual sozinho, pois varia por contrato.
"""


def classificar(parcela: str, regra: dict | None) -> str | None:
    if not regra:
        return None
    try:
        numero_parcela = int(str(parcela).strip())
    except (TypeError, ValueError):
        return None
    limite = regra.get("parcelas_agenciamento", 0) or 0
    return "agenciamento" if numero_parcela <= limite else "vitalicio"
