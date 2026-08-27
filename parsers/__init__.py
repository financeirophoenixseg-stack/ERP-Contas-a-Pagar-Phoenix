"""Registro de parsers de demonstrativo de comissão, um por seguradora.

Cada entrada declara:
- `detectar_pdf(texto_pdf) -> bool` (opcional): reconhece esse layout pelo
  texto de um PDF enviado.
- `detectar_xls(colunas) -> bool` (opcional): reconhece esse layout pelas
  colunas de uma planilha enviada.
- `detectar_html(conteudo) -> bool` (opcional): reconhece esse layout pelo
  conteúdo de um arquivo HTML/`.do` enviado.
- `detectar_csv(colunas) -> bool` (opcional): reconhece esse layout pelas
  colunas de um CSV enviado.
- `parse(caminhos) -> LoteComissao`: recebe os caminhos de TODOS os arquivos
  enviados (o parser decide o que usar de cada um).

Uma seguradora pode ter qualquer combinação dessas detecções — Suhai só tem
`detectar_pdf`; Bradesco Saúde tem `detectar_pdf` e `detectar_xls`; Porto
Seguro tem `detectar_pdf` e `detectar_html`; Hapvida tem `detectar_csv` — em
todos os casos, qualquer um dos arquivos aceitos sozinho já é suficiente.

Para adicionar uma nova seguradora: criar `parsers/<nome>.py` com essas
funções, validar contra documento(s) real(is), e registrar aqui.
"""

import pandas as pd

from parsers import bradesco_saude, hapvida, porto_seguro, suhai
from parsers.base import LinhaComissao, LoteComissao, extrair_texto_pdf

PARSERS = {
    "Suhai": {
        "detectar_pdf": suhai.detectar,
        "parse": lambda caminhos: suhai.parse(next(c for c in caminhos if c.lower().endswith(".pdf"))),
    },
    "Bradesco Saúde": {
        "detectar_pdf": bradesco_saude.detectar_pdf,
        "detectar_xls": bradesco_saude.detectar_xls,
        "parse": bradesco_saude.parse,
    },
    "Porto Seguro": {
        "detectar_pdf": porto_seguro.detectar_pdf,
        "detectar_html": porto_seguro.detectar_html,
        "parse": porto_seguro.parse,
    },
    "Hapvida": {
        "detectar_csv": hapvida.detectar_csv,
        "parse": hapvida.parse,
    },
}


def _colunas_xlsx(caminho: str) -> list[str]:
    return [str(c) for c in pd.read_excel(caminho, header=1, nrows=0).columns]


def _conteudo_html(caminho: str) -> str:
    with open(caminho, encoding="latin-1") as f:
        return f.read()


def _colunas_csv(caminho: str) -> list[str]:
    import csv

    with open(caminho, encoding="cp1252") as f:
        return [h.strip() for h in next(csv.reader(f, delimiter=";"))]


def identificar_seguradora(caminhos: list[str]) -> str | None:
    """Devolve o nome da seguradora cujo layout bate com os arquivos
    enviados (PDF e/ou planilha e/ou HTML e/ou CSV), ou None se nenhuma (ou
    mais de uma) bater."""
    caminho_pdf = next((c for c in caminhos if c.lower().endswith(".pdf")), None)
    caminho_xls = next((c for c in caminhos if c.lower().endswith((".xls", ".xlsx"))), None)
    caminho_html = next((c for c in caminhos if c.lower().endswith((".html", ".htm", ".do"))), None)
    caminho_csv = next((c for c in caminhos if c.lower().endswith(".csv")), None)

    texto_pdf = extrair_texto_pdf(caminho_pdf) if caminho_pdf else None
    colunas_xls = _colunas_xlsx(caminho_xls) if caminho_xls else None
    conteudo_html = _conteudo_html(caminho_html) if caminho_html else None
    colunas_csv = _colunas_csv(caminho_csv) if caminho_csv else None

    candidatos = set()
    for nome, info in PARSERS.items():
        if texto_pdf is not None and info.get("detectar_pdf") and info["detectar_pdf"](texto_pdf):
            candidatos.add(nome)
        if colunas_xls is not None and info.get("detectar_xls") and info["detectar_xls"](colunas_xls):
            candidatos.add(nome)
        if conteudo_html is not None and info.get("detectar_html") and info["detectar_html"](conteudo_html):
            candidatos.add(nome)
        if colunas_csv is not None and info.get("detectar_csv") and info["detectar_csv"](colunas_csv):
            candidatos.add(nome)

    return next(iter(candidatos)) if len(candidatos) == 1 else None


__all__ = ["PARSERS", "LinhaComissao", "LoteComissao", "identificar_seguradora"]
