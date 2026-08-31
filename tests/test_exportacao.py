import pandas as pd

from exportacao import gerar_excel, gerar_pdf

LINHAS = [
    {"Vencimento": "01/09/2026", "Descrição": "Aluguel", "Valor": "R$ 1.000,00", "Situação": "previsto"},
    {"Vencimento": "05/09/2026", "Descrição": "Comissão Suhai", "Valor": "R$ 250,00", "Situação": "pago"},
]


def test_gerar_excel_contem_as_linhas():
    conteudo = gerar_excel(LINHAS, "Extrato")
    assert conteudo[:2] == b"PK"  # assinatura de arquivo .xlsx (zip)
    df = pd.read_excel(pd.io.common.BytesIO(conteudo))
    assert list(df["Descrição"]) == ["Aluguel", "Comissão Suhai"]
    assert len(df) == 2


def test_gerar_excel_lista_vazia_nao_quebra():
    conteudo = gerar_excel([], "Extrato")
    assert conteudo[:2] == b"PK"


def test_gerar_pdf_gera_bytes_validos():
    conteudo = gerar_pdf(LINHAS, "Extrato")
    assert conteudo[:5] == b"%PDF-"


def test_gerar_pdf_lista_vazia_nao_quebra():
    conteudo = gerar_pdf([], "Extrato — vazio")
    assert conteudo[:5] == b"%PDF-"
