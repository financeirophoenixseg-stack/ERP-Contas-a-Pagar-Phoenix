"""Sugestão de classificação de lançamentos por padrão de descrição já ensinado."""


def sugerir(regras: list[dict], descricao: str) -> dict | None:
    desc_lower = (descricao or "").lower()
    for regra in regras:
        if regra["padrao_descricao"].lower() in desc_lower:
            return regra
    return None
