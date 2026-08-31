"""Leitura automática de comprovantes de pagamento via IA (Claude, com
visão) + vínculo automático com o lançamento previsto correspondente.

Mesma lógica do `leitor_boleto.py` (comprovante também não tem layout fixo:
cada banco/app gera o seu), mas aqui o objetivo é diferente: em vez de criar
um lançamento novo, o comprovante representa um pagamento que JÁ aconteceu —
então tentamos casar com um lançamento PREVISTO já existente (por valor +
proximidade de data) e, se o casamento for inequívoco (exatamente um
candidato), vincular o anexo e marcar como pago automaticamente.

Isso é diferente de "inventar" um valor financeiro: o valor do lançamento já
existia antes (criado manualmente ou por uma comissão/regra), o comprovante
só está confirmando que ele foi pago. Quando o casamento é ambíguo (0 ou 2+
candidatos), NADA é decidido sozinho — o comprovante fica salvo sem vínculo,
para revisão manual, exatamente como qualquer outra situação incerta neste
projeto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from leitor_ia import esta_configurado, ler_documento  # noqa: F401 (re-exportado)

_PROMPT_SISTEMA = """Você lê comprovantes de pagamento/transferência/Pix brasileiros (bancos, apps de \
pagamento, etc.) e extrai os dados em JSON estrito, sem nenhum texto antes ou depois.

Campos do JSON (todos obrigatórios, use null quando não encontrar):
- "valor": número (ex.: 1578.01), o valor pago/transferido.
- "data_pagamento": string "AAAA-MM-DD", a data em que o pagamento foi efetuado.
- "descricao": string curta e objetiva identificando do que se trata, se der pra inferir (ex.: \
"Transferência - Energia EDP", "Pix - FGTS"), ou null.
- "favorecido": string com o nome de quem recebeu o pagamento, ou null.
- "pagador": string com o nome de quem pagou, ou null.
- "confianca": "alta", "media" ou "baixa" — sua própria confiança na extração.
- "observacoes": string curta com qualquer ambiguidade relevante, ou null.

Responda SOMENTE o JSON, sem markdown, sem explicação."""

TOLERANCIA_VALOR = 0.01
TOLERANCIA_DIAS = 3


@dataclass
class DadosComprovante:
    valor: float | None
    data_pagamento: str | None
    descricao: str | None
    favorecido: str | None
    pagador: str | None
    confianca: str
    observacoes: str | None


def ler_comprovante(conteudo_pdf: bytes) -> DadosComprovante:
    """Envia o PDF do comprovante para a IA e retorna os dados extraídos.

    Levanta RuntimeError se a chamada falhar ou a resposta não vier em JSON
    válido — o chamador trata como "não deu pra ler", nunca assume um
    vínculo/baixa a partir de um erro.
    """
    dados = ler_documento(conteudo_pdf, _PROMPT_SISTEMA, "Extraia os dados deste comprovante conforme instruído.")

    return DadosComprovante(
        valor=dados.get("valor"),
        data_pagamento=dados.get("data_pagamento"),
        descricao=dados.get("descricao"),
        favorecido=dados.get("favorecido"),
        pagador=dados.get("pagador"),
        confianca=dados.get("confianca") or "baixa",
        observacoes=dados.get("observacoes"),
    )


def encontrar_lancamento_correspondente(client, valor: float | None, data_pagamento: str | None) -> str | None:
    """Procura, entre os lançamentos previstos ainda não pagos, exatamente
    UM candidato cujo valor bata (± TOLERANCIA_VALOR) e cuja data de
    vencimento esteja a até TOLERANCIA_DIAS dias da data do pagamento.
    Retorna o id do lançamento se o casamento for inequívoco, ou None se não
    houver candidato ou houver mais de um (ambíguo — não decide sozinho)."""
    if valor is None or not data_pagamento:
        return None

    try:
        data_ref = datetime.strptime(data_pagamento[:10], "%Y-%m-%d").date()
    except ValueError:
        return None

    data_min = (data_ref - timedelta(days=TOLERANCIA_DIAS)).isoformat()
    data_max = (data_ref + timedelta(days=TOLERANCIA_DIAS)).isoformat()

    candidatos = (
        client.table("lancamentos_previstos")
        .select("id, valor, data_vencimento")
        .eq("status", "previsto")
        .gte("data_vencimento", data_min)
        .lte("data_vencimento", data_max)
        .execute()
        .data
        or []
    )
    candidatos = [c for c in candidatos if abs(c["valor"] - valor) < TOLERANCIA_VALOR]

    if len(candidatos) == 1:
        return candidatos[0]["id"]
    return None
