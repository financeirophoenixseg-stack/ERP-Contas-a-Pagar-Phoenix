from datetime import date

import pytest

from formatacao import data_br, moeda, parse_valor


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


def test_parse_valor_formato_brasileiro_com_milhar():
    assert parse_valor("1.000,50") == 1000.50
    assert parse_valor("1.234.567,89") == 1234567.89


def test_parse_valor_so_virgula_decimal():
    assert parse_valor("1000,5") == 1000.5
    assert parse_valor("0,00") == 0.0


def test_parse_valor_digitacao_simples_sem_milhar():
    assert parse_valor("1000") == 1000.0
    assert parse_valor("1000.5") == 1000.5


def test_parse_valor_com_prefixo_e_espacos():
    assert parse_valor("R$ 1.000,00") == 1000.0
    assert parse_valor("  1000,00  ") == 1000.0


def test_parse_valor_vazio_vira_zero():
    assert parse_valor("") == 0.0
    assert parse_valor(None) == 0.0


def test_parse_valor_invalido_levanta_erro():
    with pytest.raises(ValueError):
        parse_valor("abc")
    with pytest.raises(ValueError):
        parse_valor("12,34,56")
