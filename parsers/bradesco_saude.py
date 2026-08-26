"""Parser do extrato de comissão da Bradesco Saúde (PDF + XLS).

A Bradesco Saúde manda dois arquivos para o mesmo pagamento:
- um PDF ("Resumo do Extrato") com corretor/CNPJ/data/totais;
- uma planilha ("Detalhes do Pagamento") com uma linha por beneficiário.

Diferença importante em relação à Suhai: aqui não existe nome de
cliente/empresa nenhuma linha — só o beneficiário individual (ex.: um
integrante de uma família num plano de saúde coletivo). Várias linhas
compartilham o mesmo número de **apólice/subfatura**, que é quem
efetivamente identifica "o cliente" (o contratante do plano). Por isso
agrupamos as linhas por apólice e SOMAMOS o valor de comissão — uma
`LinhaComissao` por apólice, não por beneficiário.

O nome do cliente em si não vem no arquivo: quem resolve isso é a tabela
`apolice_clientes` (apólice -> cliente), fora deste parser.
"""

import re

import pandas as pd
import pdfplumber

from parsers.base import LinhaComissao, LoteComissao


def _to_float_br(value) -> float:
    """Converte para float. A planilha já traz números nativos (float/int);
    só o texto extraído do PDF vem no formato brasileiro (1.234,56)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if value != value else float(value)  # value != value só é True para NaN
    texto = str(value).strip()
    if not texto or texto.lower() == "nan":
        return 0.0
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _parse_data_br(data: str) -> str:
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", data or "")
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}" if match else ""


def _valor_ultima_coluna(texto_linha: str) -> str:
    """Numa linha da tabela de totais, o valor da coluna 'No Pagamento' é o
    último número no formato monetário brasileiro que aparece na linha."""
    valores = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto_linha)
    return valores[-1] if valores else "0,00"


def _parse_header_pdf(caminho_pdf: str) -> dict:
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
        linhas_tabela: list[list[str]] = []
        settings = {"vertical_strategy": "text", "horizontal_strategy": "text"}
        for tabela in pdf.pages[0].extract_tables(table_settings=settings):
            linhas_tabela.extend(tabela)

    corretor_match = re.search(r"PARCEIRO:\s*(.+)", texto)
    cnpj_match = re.search(r"CPF/CNPJ:\s*([\d./-]+)", texto)
    data_match = re.search(r"Extrato de Pagamento de\s*(\d{2}/\d{2}/\d{4})", texto)

    valor_bruto = irrf = iss = valor_liquido = 0.0
    for row in linhas_tabela:
        primeira = (row[0] or "").strip()
        texto_linha = " ".join(c for c in row if c).replace("\n", " ")
        if primeira == "G":
            valor_bruto = _to_float_br(_valor_ultima_coluna(texto_linha))
        elif texto_linha.strip().upper().startswith("IRRF") and "BASE" not in texto_linha.upper():
            irrf = _to_float_br(_valor_ultima_coluna(texto_linha))
        elif texto_linha.strip().upper().startswith("ISSQN") and "BASE" not in texto_linha.upper():
            iss = _to_float_br(_valor_ultima_coluna(texto_linha))
        elif "Valor" in texto_linha and re.search(r"L.quido", texto_linha, re.IGNORECASE):
            valor_liquido = _to_float_br(_valor_ultima_coluna(texto_linha))

    return {
        "corretor": corretor_match.group(1).strip() if corretor_match else "",
        "cnpj": cnpj_match.group(1).strip() if cnpj_match else "",
        "data_pagamento": _parse_data_br(data_match.group(1)) if data_match else "",
        "valor_bruto": valor_bruto,
        "irrf": irrf,
        "iss": iss,
        "valor_liquido": valor_liquido,
    }


def parse(caminho_pdf: str, caminho_xls: str) -> LoteComissao:
    header = _parse_header_pdf(caminho_pdf)

    df = pd.read_excel(caminho_xls, header=1)
    df.columns = [str(c).strip() for c in df.columns]

    col_apolice = next(c for c in df.columns if "APÓLICE" in c.upper() or "APOLICE" in c.upper())
    col_endosso = next(c for c in df.columns if c.strip().upper() == "ENDOSSO")
    col_valor = next(c for c in df.columns if c.strip().upper() == "VALOR")
    col_premio = next(c for c in df.columns if "PRÊMIO" in c.upper() or "PREMIO" in c.upper())
    col_percentual = next(c for c in df.columns if c.strip() == "%")

    lote = LoteComissao(
        corretor=header["corretor"],
        cnpj=header["cnpj"],
        data_pagamento=header["data_pagamento"],
        valor_bruto=header["valor_bruto"],
        irrf=header["irrf"],
        iss=header["iss"],
        inss=0.0,
        pis_cofins_csll=0.0,
        valor_liquido=header["valor_liquido"],
    )

    df["_apolice"] = df[col_apolice].astype(str).str.strip()
    for apolice, grupo in df.groupby("_apolice", sort=False):
        if not apolice or apolice.lower() == "nan":
            continue
        endosso = str(grupo[col_endosso].iloc[0]).strip()
        percentual = _to_float_br(grupo[col_percentual].iloc[0])
        valor_total = sum(_to_float_br(v) for v in grupo[col_valor])
        premio_total = sum(_to_float_br(v) for v in grupo[col_premio])
        lote.linhas.append(
            LinhaComissao(
                cliente="",  # resolvido fora do parser via apolice_clientes
                apolice=apolice,
                endosso=endosso,
                parcela=str(len(grupo)),  # nº de beneficiários agrupados nesta apólice
                percentual_comissao=percentual,
                tipo_raw="CRÉDITO",
                tipo="pagamento",
                valor_parcela=premio_total,
                valor_comissao=valor_total,
            )
        )

    return lote
