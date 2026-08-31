"""Formatação de valores para exibição (padrão brasileiro: ponto como
separador de milhar, vírgula como decimal; datas em DD/MM/AAAA) — usado em
todas as telas pra evitar o formato americano padrão do Python (que usa
vírgula como milhar e pode confundir a leitura, ex.: "R$ 6,579.32" lido por
engano como "6 vírgula 58") e o formato ISO cru vindo do Supabase
("2026-08-31" em vez de "31/08/2026")."""

from __future__ import annotations

from datetime import date, datetime


def moeda(valor: float | int | None) -> str:
    """Formata um número como 'R$ 1.234,56'. None/valores ausentes viram 'R$ 0,00'."""
    valor = valor or 0
    texto = f"{valor:,.2f}"  # "1,234.56" (formato americano do Python)
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")  # "1.234,56"
    return f"R$ {texto}"


def data_br(valor: date | datetime | str | None) -> str:
    """Formata uma data como 'DD/MM/AAAA'. Aceita date/datetime ou string ISO
    ('2026-08-31' ou '2026-08-31T00:00:00'), vinda direto do Supabase.
    None/valores ausentes ou não reconhecidos voltam como '-' (ou o texto
    original, se não parecer uma data)."""
    if valor is None or valor == "":
        return "-"
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    try:
        return datetime.strptime(str(valor)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(valor)
