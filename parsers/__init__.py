"""Registro de parsers de demonstrativo de comissão, um por seguradora.

Cada entrada declara quantos/quais arquivos precisa (`arquivos`, uma lista de
rótulos exibidos na tela de importação) e uma função `parse` que recebe os
caminhos desses arquivos NESSA ORDEM e devolve um `LoteComissao`.

Para adicionar uma nova seguradora: criar `parsers/<nome>.py`, validar contra
documento(s) real(is) da seguradora, e registrar aqui.
"""

from parsers import bradesco_saude, suhai
from parsers.base import LinhaComissao, LoteComissao

PARSERS = {
    "Suhai": {
        "arquivos": ["PDF do demonstrativo"],
        "parse": lambda caminhos: suhai.parse(caminhos[0]),
    },
    "Bradesco Saúde": {
        "arquivos": ["PDF (Resumo do Extrato)", "Planilha de detalhes (XLS/XLSX)"],
        "parse": lambda caminhos: bradesco_saude.parse(caminhos[0], caminhos[1]),
    },
}

__all__ = ["PARSERS", "LinhaComissao", "LoteComissao"]
