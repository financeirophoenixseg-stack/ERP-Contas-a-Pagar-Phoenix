"""Leitura automática de boletos/guias de pagamento via IA (Claude, com visão).

Diferente dos parsers de demonstrativo de comissão (`parsers/`), boletos e
guias de pagamento não têm um layout fixo por emissor — cada banco,
concessionária ou órgão público usa um formato diferente, e muitos PDFs
desses documentos vêm com o texto interno embaralhado (fonte incorporada sem
mapeamento de caracteres), o que impede a extração de texto tradicional
(mesma técnica usada em `parsers/base.py`).

Por isso aqui a extração é feita mandando o PDF direto pra IA interpretar
visualmente (como um humano leria), pedindo uma resposta em JSON estrito.
O valor/vencimento extraídos são só uma SUGESTÃO PARA CONFERÊNCIA — o
lançamento em `lancamentos_previstos` só é criado depois que o usuário
confere e confirma na tela, nunca automaticamente. Isso preserva a regra do
projeto de nunca deixar a IA decidir sozinha um valor financeiro que vira
lançamento contábil.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

import anthropic

MODELO = "claude-sonnet-5"

_PROMPT_SISTEMA = """Você lê boletos bancários e guias de pagamento brasileiras (FGTS, DAS, GPS, \
concessionárias, boletos comuns etc.) e extrai os dados em JSON estrito, sem nenhum texto antes ou depois.

Campos do JSON (todos obrigatórios, use null quando não encontrar):
- "valor": número (ex.: 1578.01), o valor total a pagar/recolher.
- "data_vencimento": string "AAAA-MM-DD".
- "descricao": string curta e objetiva identificando do que se trata (ex.: "FGTS 08/2026", \
"Energia elétrica - EDP", "DAS Simples Nacional 07/2026").
- "favorecido": string com o nome de quem vai receber o pagamento (banco, concessionária, órgão), ou null.
- "documento_pagador": CPF/CNPJ de quem deve pagar, só os dígitos, ou null se não aparecer.
- "confianca": "alta", "media" ou "baixa" — sua própria confiança na extração.
- "observacoes": string curta com qualquer ambiguidade relevante, ou null.

Responda SOMENTE o JSON, sem markdown, sem explicação."""


@dataclass
class DadosBoleto:
    valor: float | None
    data_vencimento: str | None
    descricao: str | None
    favorecido: str | None
    documento_pagador: str | None
    confianca: str
    observacoes: str | None


def esta_configurado() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ler_boleto(conteudo_pdf: bytes) -> DadosBoleto:
    """Envia o PDF do boleto/guia para a IA e retorna os dados extraídos.

    Levanta RuntimeError se a chamada falhar ou a resposta não vier em JSON
    válido — o chamador deve tratar como "não deu pra ler automaticamente,
    preencha manualmente", nunca preencher um lançamento sozinho a partir de
    um erro.
    """
    client = anthropic.Anthropic()

    resposta = client.messages.create(
        model=MODELO,
        max_tokens=1024,
        system=_PROMPT_SISTEMA,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(conteudo_pdf).decode(),
                        },
                    },
                    {"type": "text", "text": "Extraia os dados deste boleto/guia conforme instruído."},
                ],
            }
        ],
    )

    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Resposta da IA não veio em JSON válido: {texto[:300]!r}") from e

    return DadosBoleto(
        valor=dados.get("valor"),
        data_vencimento=dados.get("data_vencimento"),
        descricao=dados.get("descricao"),
        favorecido=dados.get("favorecido"),
        documento_pagador=dados.get("documento_pagador"),
        confianca=dados.get("confianca") or "baixa",
        observacoes=dados.get("observacoes"),
    )
