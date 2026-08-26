"""Registro de parsers de demonstrativo de comissão, um por seguradora.

Para adicionar uma nova seguradora: criar `parsers/<nome>.py` com uma função
`parse(caminho: str) -> LoteComissao` (ver `parsers/base.py`), validada contra
um PDF real da seguradora, e registrar aqui.
"""

from parsers import suhai
from parsers.base import LinhaComissao, LoteComissao

PARSERS = {
    "Suhai": suhai.parse,
}

__all__ = ["PARSERS", "LinhaComissao", "LoteComissao"]
