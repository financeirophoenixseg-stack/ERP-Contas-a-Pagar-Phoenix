"""Estruturas comuns a qualquer parser de demonstrativo de comissão.

Cada seguradora tem seu próprio layout de PDF, mas todas produzem um
`LoteComissao` com estes mesmos campos — é o que o resto do sistema
(resolução de empresa por CNPJ, criação de clientes, conciliação) consome,
sem precisar saber qual seguradora gerou o arquivo.
"""

from dataclasses import dataclass, field

import pdfplumber


def extrair_texto_pdf(caminho: str) -> str:
    with pdfplumber.open(caminho) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


@dataclass
class LinhaComissao:
    cliente: str
    apolice: str
    endosso: str
    parcela: str
    percentual_comissao: float
    tipo_raw: str
    tipo: str  # 'pagamento' | 'adiantamento' | 'cancelamento' | 'recuperacao' | 'ajuste'
    valor_parcela: float
    valor_comissao: float


@dataclass
class LoteComissao:
    corretor: str
    cnpj: str
    data_pagamento: str  # YYYY-MM-DD
    valor_bruto: float
    irrf: float
    iss: float
    inss: float
    pis_cofins_csll: float
    valor_liquido: float
    linhas: list[LinhaComissao] = field(default_factory=list)
    # Opcionais: preenchidos por seguradoras cujo arquivo traz banco/agência/
    # conta (ex.: Bradesco), usados como identificação alternativa da empresa
    # quando o CNPJ não está disponível (ex.: quando só a planilha foi enviada).
    banco: str = ""
    agencia: str = ""
    conta: str = ""
