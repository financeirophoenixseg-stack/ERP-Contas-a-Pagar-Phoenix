"""Registro de parsers de demonstrativo de comissão, um por seguradora.

Cada entrada declara:
- `detectar(texto_pdf) -> bool`: identifica se um PDF pertence a este layout,
  usada para reconhecer a seguradora automaticamente (sem o usuário escolher).
- `arquivos`: rótulos dos arquivos que o parser precisa, na ordem esperada
  pelo `parse` (o primeiro é sempre o PDF usado na detecção).
- `parse(caminhos) -> LoteComissao`.

Para adicionar uma nova seguradora: criar `parsers/<nome>.py` com essas duas
funções, validar contra documento(s) real(is) da seguradora, e registrar aqui.
"""

from parsers import bradesco_saude, suhai
from parsers.base import LinhaComissao, LoteComissao, extrair_texto_pdf

PARSERS = {
    "Suhai": {
        "arquivos": ["PDF do demonstrativo"],
        "detectar": suhai.detectar,
        "parse": lambda caminhos: suhai.parse(caminhos[0]),
    },
    "Bradesco Saúde": {
        "arquivos": ["PDF (Resumo do Extrato)", "Planilha de detalhes (XLS/XLSX)"],
        "detectar": bradesco_saude.detectar,
        "parse": lambda caminhos: bradesco_saude.parse(caminhos[0], caminhos[1]),
    },
}


def identificar_seguradora(caminho_pdf: str) -> str | None:
    """Devolve o nome da seguradora cujo layout bate com este PDF, ou None se
    nenhuma (ou mais de uma) bater."""
    texto = extrair_texto_pdf(caminho_pdf)
    candidatos = [nome for nome, info in PARSERS.items() if info["detectar"](texto)]
    return candidatos[0] if len(candidatos) == 1 else None


__all__ = ["PARSERS", "LinhaComissao", "LoteComissao", "identificar_seguradora"]
