from datetime import date

from formatacao import data_br, moeda


def test_moeda_formato_brasileiro():
    assert moeda(1000) == "R$ 1.000,00"
    assert moeda(6579.32) == "R$ 6.579,32"
    assert moeda(1234567.9) == "R$ 1.234.567,90"


def test_moeda_valores_ausentes():
    assert moeda(0) == "R$ 0,00"
    assert moeda(None) == "R$ 0,00"


def test_moeda_valor_negativo():
    assert moeda(-150.5) == "R$ -150,50"


def test_data_br_string_iso():
    assert data_br("2026-08-31") == "31/08/2026"
    assert data_br("2026-08-31T00:00:00") == "31/08/2026"


def test_data_br_objeto_date():
    assert data_br(date(2026, 8, 31)) == "31/08/2026"


def test_data_br_ausente():
    assert data_br(None) == "-"
    assert data_br("") == "-"


def test_data_br_texto_nao_reconhecido_volta_como_esta():
    assert data_br("sem vínculo") == "sem vínculo"
