"""Registro de parsers de demonstrativo de comissão, um por seguradora.

Cada entrada declara:
- `detectar_pdf(texto_pdf) -> bool` (opcional): reconhece esse layout pelo
  texto de um PDF enviado.
- `detectar_xls(colunas) -> bool` (opcional): reconhece esse layout pelas
  colunas de uma planilha enviada.
- `parse(caminhos) -> LoteComissao`: recebe os caminhos de TODOS os arquivos
  enviados (o parser decide o que usar de cada um).

Uma seguradora pode ter só `detectar_pdf` (ex.: Suhai, que só manda PDF), só
`detectar_xls`, ou os dois (ex.: Bradesco Saúde, que manda os dois relatórios
de forma independente — qualquer um sozinho já é suficiente).

Para adicionar uma nova seguradora: criar `parsers/<nome>.py` com essas
funções, validar contra documento(s) real(is), e registrar aqui.
"""

import pandas as pd

from parsers import bradesco_saude, suhai
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
}


def _colunas_xlsx(caminho: str) -> list[str]:
    return [str(c) for c in pd.read_excel(caminho, header=1, nrows=0).columns]


def identificar_seguradora(caminhos: list[str]) -> str | None:
    """Devolve o nome da seguradora cujo layout bate com os arquivos
    enviados (PDF e/ou planilha), ou None se nenhuma (ou mais de uma) bater."""
    caminho_pdf = next((c for c in caminhos if c.lower().endswith(".pdf")), None)
    caminho_xls = next((c for c in caminhos if c.lower().endswith((".xls", ".xlsx"))), None)

    texto_pdf = extrair_texto_pdf(caminho_pdf) if caminho_pdf else None
    colunas_xls = _colunas_xlsx(caminho_xls) if caminho_xls else None

    candidatos = set()
    for nome, info in PARSERS.items():
        if texto_pdf is not None and info.get("detectar_pdf") and info["detectar_pdf"](texto_pdf):
            candidatos.add(nome)
        if colunas_xls is not None and info.get("detectar_xls") and info["detectar_xls"](colunas_xls):
            candidatos.add(nome)

    return next(iter(candidatos)) if len(candidatos) == 1 else None


__all__ = ["PARSERS", "LinhaComissao", "LoteComissao", "identificar_seguradora"]
