"""Parser do demonstrativo de comissão da Suhai Seguradora (PDF).

Peculiaridades observadas no PDF real (`tests/fixtures/suhai_referencia.pdf`)
e tratadas aqui:
- A coluna "Apólice-Endosso" às vezes vem com cada caractere separado por
  espaço (artefato de espaçamento do PDF, não é conteúdo real) — removemos
  todo espaço antes de interpretar esses campos numéricos.
- O layout usa acentuação que o extrator de texto às vezes não decodifica
  (aparece como caractere de substituição) — a classificação do tipo de
  pagamento é feita por substrings sem acento, então não depende disso.
"""

import re

import pdfplumber

from parsers.base import LinhaComissao, LoteComissao

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "text_x_tolerance": 1,
}

TIPO_PATTERNS = [
    ("cancelamento", "cancelamento"),
    ("recup", "recuperacao"),
    ("adiantamento", "adiantamento"),
    ("corretagem", "pagamento"),
]


def _squeeze(value: str) -> str:
    """Remove todo espaço em branco (artefato de espaçamento do PDF)."""
    return re.sub(r"\s+", "", value or "")


def _to_float(value: str) -> float:
    value = _squeeze(value).replace(".", "").replace(",", ".")
    return float(value) if value else 0.0


def _classify_tipo(tipo_raw: str) -> str:
    lower = _squeeze(tipo_raw).lower()
    for keyword, tipo in TIPO_PATTERNS:
        if keyword in lower:
            return tipo
    return "ajuste"


def _limpar_nome_cliente(raw: str) -> str:
    """Remove código numérico solto que às vezes gruda no fim do nome do
    cliente (artefato de layout do PDF, ex.: 'FULANO DE TAL 278442')."""
    match = re.match(r"^(.*[A-Za-zÀ-ÿ])\s+\d+$", raw.strip())
    return match.group(1).strip() if match else raw.strip()


def _parse_apolice_endosso(raw: str) -> tuple[str, str]:
    squeezed = _squeeze(raw)
    match = re.match(r"^(\d+)End:(\d+)$", squeezed, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    return squeezed, ""


def _parse_data_br(data: str) -> str:
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", data)
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}" if match else ""


def parse(caminho: str) -> LoteComissao:
    with pdfplumber.open(caminho) as pdf:
        texto_completo = "\n".join(p.extract_text() or "" for p in pdf.pages)
        linhas_tabela: list[list[str]] = []
        for page in pdf.pages:
            for tabela in page.extract_tables(table_settings=TABLE_SETTINGS):
                linhas_tabela.extend(tabela)

    corretor_match = re.search(r"Corretor:\s*(.+?)\s+Data Pagto:\s*(\d{2}/\d{2}/\d{4})", texto_completo)
    cnpj_match = re.search(r"CNPJ\s*/\s*CPF\s*([\d./-]+)", texto_completo)

    def _valor(padrao: str) -> float:
        m = re.search(padrao, texto_completo)
        return _to_float(m.group(1)) if m else 0.0

    lote = LoteComissao(
        corretor=corretor_match.group(1).strip() if corretor_match else "",
        cnpj=cnpj_match.group(1).strip() if cnpj_match else "",
        data_pagamento=_parse_data_br(corretor_match.group(2)) if corretor_match else "",
        valor_bruto=_valor(r"Valor Total \(Tribut.rio\)\s*([\d.,]+)"),
        irrf=_valor(r"I\.R\.R\.F\s*([\d.,]+)"),
        iss=_valor(r"I\.S\.S\.\s*([\d.,]+)"),
        inss=_valor(r"I\.N\.S\.S\.\s*([\d.,]+)"),
        pis_cofins_csll=_valor(r"PIS\s*/\s*COFINS\s*/\s*CSLL\s*([\d.,]+)"),
        valor_liquido=_valor(r"Valor L.quido\s*([\d.,]+)"),
    )

    cabecalho = {"cliente", "apólice-endosso\\proposta", "parcela"}
    for row in linhas_tabela:
        if not row or len(row) < 7:
            continue
        cliente = (row[0] or "").strip()
        if not cliente or cliente.lower() in cabecalho:
            continue
        cliente = _limpar_nome_cliente(cliente)
        apolice, endosso = _parse_apolice_endosso(row[1])
        tipo_raw = (row[4] or "").strip()
        lote.linhas.append(
            LinhaComissao(
                cliente=cliente,
                apolice=apolice,
                endosso=endosso,
                parcela=_squeeze(row[2]),
                percentual_comissao=_to_float(row[3]),
                tipo_raw=tipo_raw,
                tipo=_classify_tipo(tipo_raw),
                valor_parcela=_to_float(row[5]),
                valor_comissao=_to_float(row[6]),
            )
        )

    return lote
