"""Parser do 'Analítico de Pagamentos de Comissões' da Porto Seguro.

A Porto Seguro exporta o mesmo relatório em dois formatos independentes —
PDF (impresso) e HTML (`.do`, gerado pelo portal) — cada um sozinho já
traz cabeçalho, detalhe e totais completos. Aceita qualquer um dos dois,
ou os dois juntos (o primeiro encontrado é usado).

Diferenças em relação à Suhai/Bradesco:
- Identifica o corretor por código **SUSEP** (não CNPJ) — ex.: '57557J'.
- Cada linha de produção já traz o nome do cliente na maioria dos casos,
  MAS algumas linhas vêm como 'Agenciamento Sub: <nº> Compet: ...', sem
  nome de cliente — nesses casos usamos a apólice (Apl/Prop) para
  resolver o cliente via `apolice_clientes`, igual à Bradesco Saúde.
- Há uma seção separada de "Débito/Crédito" (custos administrativos do
  corretor, ex.: manutenção de site) sem cliente nem apólice associados —
  não vira uma LinhaComissao própria, só entra no total do lote (já é o
  que a própria Porto Seguro faz ao calcular "A Pagar").
- O valor usado para conciliação bancária é o "A Pagar" (líquido já
  descontado do débito/crédito), não o "Líquido" (que ainda não desconta
  o débito/crédito do corretor).
- A tabela de detalhe às vezes tem uma coluna "Marca" (ex.: 'Porto') e às
  vezes não — o número de colunas varia entre PDF e HTML e entre os dois
  layouts, então localizamos apólice/endosso/parcela pela POSIÇÃO A PARTIR
  DO INÍCIO (depois de checar se a coluna 'Marca' existe, olhando se a
  segunda célula é texto ou um código de sucursal numérico) e prêmio/taxa/
  comissão/tipo pela posição A PARTIR DO FIM (essas 4 últimas colunas são
  estáveis em todos os formatos observados).
"""

import re
from html.parser import HTMLParser

import pdfplumber

from parsers.base import LinhaComissao, LoteComissao

TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


def _to_float_br(value) -> float:
    if value is None:
        return 0.0
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


def detectar_pdf(texto: str) -> bool:
    return "PAGAMENTOS DE COMISS" in texto.upper() and "SUSEP FAVORECIDA" in texto.upper()


def detectar_html(conteudo: str) -> bool:
    return "PAGAMENTOS DE COMISS" in conteudo.upper() and "SUSEP FAVORECIDA" in conteudo.upper()


class _TabelaHTML(HTMLParser):
    """Extrai linhas de <tr>/<td> de um HTML simples (sem dependências)."""

    def __init__(self):
        super().__init__()
        self.linhas: list[list[str]] = []
        self._linha: list[str] | None = None
        self._celula: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._linha = []
        elif tag == "td":
            self._celula = []

    def handle_endtag(self, tag):
        if tag == "td" and self._celula is not None:
            self._linha.append(" ".join("".join(self._celula).split()))
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            self.linhas.append(self._linha)
            self._linha = None

    def handle_data(self, data):
        if self._celula is not None:
            self._celula.append(data)


def _extrair_texto_e_linhas_pdf(caminho: str) -> tuple[str, list[list[str]]]:
    with pdfplumber.open(caminho) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
        linhas: list[list[str]] = []
        for page in pdf.pages:
            for tabela in page.extract_tables(table_settings=TABLE_SETTINGS):
                linhas.extend(tabela)
    return texto, linhas


def _extrair_linhas_html(caminho: str) -> list[list[str]]:
    with open(caminho, encoding="latin-1") as f:
        conteudo = f.read()
    parser = _TabelaHTML()
    parser.feed(conteudo)
    return parser.linhas


def _parse_header_pdf(texto: str) -> dict:
    ordem = re.search(r"Ordem de Pagamento:\s*(\S+)", texto)
    data = re.search(r"Data de Pagamento:\s*(\d{2}/\d{2}/\d{4})", texto)
    susep = re.search(r"Susep Favorecida:\s*(\S+)\s*-\s*(.+?)\s*Susep Oficial:", texto)
    totais = re.search(
        r"Comiss.o Bruta\s+INSS\s+IRRF\s+ISS\s+L.quido\s+D.bito/Cr.dito\s+A pagar\s*"
        r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+(-?[\d.,]+)\s+(-?[\d.,]+)",
        texto,
    )
    return {
        "data_pagamento": _parse_data_br(data.group(1)) if data else "",
        "susep": susep.group(1).strip() if susep else "",
        "corretor": susep.group(2).strip() if susep else "",
        "valor_bruto": _to_float_br(totais.group(1)) if totais else 0.0,
        "inss": _to_float_br(totais.group(2)) if totais else 0.0,
        "irrf": _to_float_br(totais.group(3)) if totais else 0.0,
        "iss": _to_float_br(totais.group(4)) if totais else 0.0,
        "a_pagar": _to_float_br(totais.group(7)) if totais else 0.0,
    }


def _parse_header_html(linhas: list[list[str]]) -> dict:
    resultado = {
        "data_pagamento": "", "susep": "", "corretor": "",
        "valor_bruto": 0.0, "inss": 0.0, "irrf": 0.0, "iss": 0.0, "a_pagar": 0.0,
    }
    for i, row in enumerate(linhas):
        primeira = (row[0] or "").strip()
        if primeira.startswith("Ordem de Pagamento") and len(row) >= 4:
            resultado["data_pagamento"] = _parse_data_br(row[3])
        elif primeira.startswith("Susep Favorecida") and len(row) >= 2:
            m = re.match(r"(\S+)\s*-\s*(.+)", row[1].strip())
            if m:
                resultado["susep"] = m.group(1)
                resultado["corretor"] = m.group(2).strip()
        elif primeira == "Comissão Bruta" and len(row) >= 7 and i + 1 < len(linhas):
            valores = linhas[i + 1]
            resultado["valor_bruto"] = _to_float_br(valores[0])
            resultado["inss"] = _to_float_br(valores[1])
            resultado["irrf"] = _to_float_br(valores[2])
            resultado["iss"] = _to_float_br(valores[3])
            resultado["a_pagar"] = _to_float_br(valores[6])
    return resultado


_RE_TIPO = re.compile(r"^\d+\s*-\s*\S")
_RE_AGENCIAMENTO = re.compile(r"^Agenciamento\s", re.IGNORECASE)


def _linhas_producao(linhas_tabela: list[list[str]]) -> list[LinhaComissao]:
    resultado = []
    for row in linhas_tabela:
        if not row or not row[0] or row[0].strip().lower().startswith("total"):
            continue
        if len(row) < 11:
            continue
        tipo_raw = (row[-1] or "").strip()
        if not tipo_raw or not _RE_TIPO.match(tipo_raw):
            continue

        premio, taxa, comissao = row[-4], row[-3], row[-2]
        # coluna "Marca" existe? se a 2ª célula for puramente numérica, é o
        # código de Sucursal direto (sem Marca); senão é o nome da marca.
        tem_marca = not (row[1] or "").strip().isdigit()
        if tem_marca:
            apolice, endosso, parcela = row[4], row[5], row[6]
        else:
            apolice, endosso, parcela = row[3], row[4], row[5]

        historico = row[0].strip()
        cliente = "" if _RE_AGENCIAMENTO.match(historico) else historico

        resultado.append(
            LinhaComissao(
                cliente=cliente,
                apolice=(apolice or "").strip(),
                endosso=(endosso or "").strip(),
                parcela=(parcela or "").strip(),
                percentual_comissao=_to_float_br(taxa),
                tipo_raw=tipo_raw,
                tipo="pagamento",
                valor_parcela=_to_float_br(premio),
                valor_comissao=_to_float_br(comissao),
            )
        )
    return resultado


def parse(caminhos: list[str]) -> LoteComissao:
    caminho_pdf = next((c for c in caminhos if c.lower().endswith(".pdf")), None)
    caminho_html = next((c for c in caminhos if c.lower().endswith((".html", ".htm", ".do"))), None)

    if caminho_pdf:
        texto, linhas_tabela = _extrair_texto_e_linhas_pdf(caminho_pdf)
        header = _parse_header_pdf(texto)
    elif caminho_html:
        linhas_tabela = _extrair_linhas_html(caminho_html)
        header = _parse_header_html(linhas_tabela)
    else:
        raise ValueError("Nenhum PDF ou HTML da Porto Seguro encontrado nos arquivos enviados.")

    linhas = _linhas_producao(linhas_tabela)

    return LoteComissao(
        corretor=header["corretor"],
        cnpj="",
        susep=header["susep"],
        data_pagamento=header["data_pagamento"],
        valor_bruto=header["valor_bruto"],
        irrf=header["irrf"],
        iss=header["iss"],
        inss=header["inss"],
        pis_cofins_csll=0.0,
        valor_liquido=header["a_pagar"],
        linhas=linhas,
    )
