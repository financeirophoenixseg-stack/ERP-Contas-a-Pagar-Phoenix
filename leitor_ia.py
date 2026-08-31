"""Base compartilhada para leitura de documentos financeiros via IA (Claude,
com visão) — usada tanto pra boletos/guias (`leitor_boleto.py`) quanto pra
comprovantes de pagamento (`leitor_comprovante.py`). Ver `leitor_boleto.py`
pra entender por que a extração é feita via IA em vez de parser de texto
(esses documentos não têm layout fixo e muitos vêm com o PDF embaralhado)."""

from __future__ import annotations

import base64
import json
import os
import re

import anthropic

MODELO = "claude-sonnet-5"

_BLOCO_MARKDOWN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def esta_configurado() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ler_documento(conteudo_pdf: bytes, prompt_sistema: str, instrucao_usuario: str) -> dict:
    """Envia o PDF pra IA com o prompt de sistema dado e retorna o JSON já
    parseado (dict). Levanta RuntimeError se a chamada falhar ou a resposta
    não vier em JSON válido — o chamador decide como tratar (nunca deve
    assumir um valor financeiro a partir de um erro)."""
    client = anthropic.Anthropic()

    resposta = client.messages.create(
        model=MODELO,
        max_tokens=1024,
        system=prompt_sistema,
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
                    {"type": "text", "text": instrucao_usuario},
                ],
            }
        ],
    )

    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
    # a IA às vezes envolve o JSON num bloco markdown (```json ... ```)
    # mesmo quando instruída a não fazer isso — remove antes de parsear.
    texto_limpo = _BLOCO_MARKDOWN.sub("", texto).strip()

    try:
        return json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Resposta da IA não veio em JSON válido: {texto[:300]!r}") from e
