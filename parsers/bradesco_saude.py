"""Parser do extrato de comissão da Bradesco Saúde.

A Bradesco Saúde manda, para o mesmo pagamento, um PDF ("Resumo do
Extrato": corretor/CNPJ/data/totais + a mesma tabela de detalhes) e/ou uma
planilha ("Detalhes do Pagamento": uma linha por beneficiário). Os dois
relatórios são independentes — cada um sozinho já traz o suficiente para
montar o lote, então este parser aceita qualquer um dos dois, ou os dois
juntos (quando os dois vêm, o PDF fornece corretor/CNPJ/totais e a
planilha fornece os detalhes, por ser mais fácil de ler com certeza).

Diferença importante em relação à Suhai: aqui não existe nome de
cliente/empresa em nenhuma linha — só o beneficiário individual (ex.: um
integrante de uma família num plano de saúde coletivo). Várias linhas
compartilham o mesmo número de **apólice/subfatura**, que é quem
efetivamente identifica "o cliente" (o contratante do plano). Por isso
agrupamos as linhas por apólice e SOMAMOS o valor de comissão — uma
`LinhaComissao` por apólice, não por beneficiário. O nome do cliente em
si não vem no arquivo: quem resolve isso é a tabela `apolice_clientes`
(apólice -> cliente), fora deste parser.
"""

import re

import pandas as pd
import pdfplumber

from parsers.base import LinhaComissao, LoteComissao

TABLE_SETTINGS_DETALHES = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def _to_float_br(value) -> float:
    """Converte para float. A planilha traz números nativos (float/int);
    o texto extraído do PDF vem no formato brasileiro (1.234,56)."""
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


def detectar_pdf(texto: str) -> bool:
    """Assinatura do layout Bradesco Saúde: título 'Resumo do Extrato' e o
    rótulo 'PARCEIRO', ausentes no layout da Suhai."""
    return "Resumo do Extrato" in texto and "PARCEIRO" in texto.upper()


def detectar_xls(colunas: list[str]) -> bool:
    """Assinatura da planilha de detalhes: colunas específicas desse layout."""
    colunas_upper = {c.strip().upper() for c in colunas}
    return {"APÓLICE / SUBFATURA", "CERTIFICADO", "RAMO"} <= colunas_upper


def _extrair_texto_pdf(caminho_pdf: str) -> str:
    with pdfplumber.open(caminho_pdf) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


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
    banco_match = re.search(r"Banco\s*(\d+)\s*Ag.ncia\s*([\w-]+)\s*Conta\s*([\w-]+)", texto)

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
        "banco": banco_match.group(1).strip() if banco_match else "",
        "agencia": banco_match.group(2).strip().rstrip("-") if banco_match else "",
        "conta": banco_match.group(3).strip() if banco_match else "",
    }


def _linhas_do_pdf(caminho_pdf: str) -> list[dict]:
    """Extrai as linhas de detalhe (uma por beneficiário) direto da tabela
    com bordas da página 2 do PDF — mesmos dados da planilha, formato
    brasileiro (string com vírgula)."""
    linhas = []
    with pdfplumber.open(caminho_pdf) as pdf:
        for page in pdf.pages:
            for tabela in page.extract_tables(table_settings=TABLE_SETTINGS_DETALHES):
                for row in tabela:
                    if not row or len(row) < 12:
                        continue
                    apolice = (row[4] or "").strip()
                    if not apolice or "APOLICE" in apolice.upper() or "SUBFATURA" in apolice.upper():
                        continue
                    linhas.append(
                        {
                            "apolice": apolice,
                            "endosso": (row[5] or "").strip(),
                            "percentual": _to_float_br(row[10]),
                            "premio": _to_float_br(row[9]),
                            "valor": _to_float_br(row[11]),
                        }
                    )
    return linhas


def _linhas_do_xls(caminho_xls: str) -> tuple[list[dict], dict]:
    """Extrai as linhas de detalhe da planilha, e também retorna dados de
    cabeçalho que ela traz (data e conta bancária) — usados quando não há
    PDF disponível."""
    df = pd.read_excel(caminho_xls, header=1)
    df.columns = [str(c).strip() for c in df.columns]

    col_apolice = next(c for c in df.columns if "APÓLICE" in c.upper() or "APOLICE" in c.upper())
    col_endosso = next(c for c in df.columns if c.strip().upper() == "ENDOSSO")
    col_valor = next(c for c in df.columns if c.strip().upper() == "VALOR")
    col_premio = next(c for c in df.columns if "PRÊMIO" in c.upper() or "PREMIO" in c.upper())
    col_percentual = next(c for c in df.columns if c.strip() == "%")

    linhas = [
        {
            "apolice": str(row[col_apolice]).strip(),
            "endosso": str(row[col_endosso]).strip(),
            "percentual": _to_float_br(row[col_percentual]),
            "premio": _to_float_br(row[col_premio]),
            "valor": _to_float_br(row[col_valor]),
        }
        for _, row in df.iterrows()
    ]

    header = {"data_pagamento": "", "banco": "", "agencia": "", "conta": ""}
    col_data = next((c for c in df.columns if "DATA LAN" in c.upper()), None)
    if col_data is not None and len(df):
        data_valor = df[col_data].iloc[0]
        header["data_pagamento"] = str(data_valor)[:10] if pd.notna(data_valor) else ""

    col_banco = next((c for c in df.columns if "DADOS BANC" in c.upper()), None)
    if col_banco is not None and len(df):
        m = re.search(r"(\d+)\D+(\d+)\D+([\d-]+)", str(df[col_banco].iloc[0]))
        if m:
            header["banco"], header["agencia"], header["conta"] = m.group(1), m.group(2), m.group(3)

    return linhas, header


def _normalizar_apolice(apolice: str) -> str:
    """PDF e planilha formatam a mesma apólice de jeitos diferentes
    ('1117397/1' vs '001117397/000000001') — normaliza tirando zeros à
    esquerda de cada parte, para o mapeamento apolice->cliente funcionar
    igual não importa qual arquivo foi enviado."""
    partes = apolice.split("/")
    return "/".join(p.lstrip("0") or "0" for p in partes)


def _agrupar_por_apolice(linhas_cruas: list[dict]) -> list[LinhaComissao]:
    apolices: dict[str, list[dict]] = {}
    for linha in linhas_cruas:
        apolice = _normalizar_apolice(linha["apolice"])
        apolices.setdefault(apolice, []).append(linha)

    resultado = []
    for apolice, grupo in apolices.items():
        resultado.append(
            LinhaComissao(
                cliente="",  # resolvido fora do parser via apolice_clientes
                apolice=apolice,
                endosso=grupo[0]["endosso"],
                parcela=str(len(grupo)),  # nº de beneficiários agrupados nesta apólice
                percentual_comissao=grupo[0]["percentual"],
                tipo_raw="CRÉDITO",
                tipo="pagamento",
                valor_parcela=sum(g["premio"] for g in grupo),
                valor_comissao=sum(g["valor"] for g in grupo),
            )
        )
    return resultado


def parse(caminhos: list[str]) -> LoteComissao:
    caminho_pdf = next((c for c in caminhos if c.lower().endswith(".pdf")), None)
    caminho_xls = next((c for c in caminhos if c.lower().endswith((".xls", ".xlsx"))), None)

    header = {
        "corretor": "", "cnpj": "", "data_pagamento": "",
        "valor_bruto": 0.0, "irrf": 0.0, "iss": 0.0, "valor_liquido": 0.0,
        "banco": "", "agencia": "", "conta": "",
    }
    linhas_cruas: list[dict] = []

    if caminho_pdf:
        header.update(_parse_header_pdf(caminho_pdf))

    if caminho_xls:
        linhas_cruas, header_xls = _linhas_do_xls(caminho_xls)
        if not caminho_pdf:
            # sem PDF: usa data/conta que a própria planilha traz
            for campo in ("data_pagamento", "banco", "agencia", "conta"):
                if not header[campo] and header_xls[campo]:
                    header[campo] = header_xls[campo]
    elif caminho_pdf:
        linhas_cruas = _linhas_do_pdf(caminho_pdf)

    valor_bruto = header["valor_bruto"] or sum(l["valor"] for l in linhas_cruas)
    valor_liquido = header["valor_liquido"] or valor_bruto

    lote = LoteComissao(
        corretor=header["corretor"],
        cnpj=header["cnpj"],
        data_pagamento=header["data_pagamento"],
        valor_bruto=valor_bruto,
        irrf=header["irrf"],
        iss=header["iss"],
        inss=0.0,
        pis_cofins_csll=0.0,
        valor_liquido=valor_liquido,
        banco=header["banco"],
        agencia=header["agencia"],
        conta=header["conta"],
    )
    lote.linhas = _agrupar_por_apolice(linhas_cruas)
    return lote
