"""Formatação de valores para exibição (padrão brasileiro: ponto como
separador de milhar, vírgula como decimal) — usado em todas as telas pra
mostrar valores em reais, evitando o formato americano padrão do Python
(que usa vírgula como milhar e pode confundir a leitura, ex.: "R$ 6,579.32"
lido por engano como "6 vírgula 58")."""

from __future__ import annotations


def moeda(valor: float | int | None) -> str:
    """Formata um número como 'R$ 1.234,56'. None/valores ausentes viram 'R$ 0,00'."""
    valor = valor or 0
    texto = f"{valor:,.2f}"  # "1,234.56" (formato americano do Python)
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")  # "1.234,56"
    return f"R$ {texto}"
