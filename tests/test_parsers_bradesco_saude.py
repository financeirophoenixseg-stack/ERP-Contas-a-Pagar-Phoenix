from parsers.bradesco_saude import (
    _normalizar_apolice,
    _parse_data_br,
    _to_float_br,
    _valor_ultima_coluna,
)


def test_to_float_br_handles_native_numbers_from_xlsx():
    assert _to_float_br(582.929993) == 582.929993
    assert _to_float_br(0) == 0.0


def test_to_float_br_handles_nan():
    assert _to_float_br(float("nan")) == 0.0


def test_to_float_br_handles_brazilian_string_from_pdf():
    assert _to_float_br("2.180,21") == 2180.21
    assert _to_float_br("0,00") == 0.0


def test_valor_ultima_coluna_pega_a_coluna_no_pagamento():
    # linha com dois valores (Acumulado, No Pagamento) - o último é o que importa
    assert _valor_ultima_coluna("BASE ISSQN R$ 15.051,66 R$ 277,00") == "277,00"


def test_valor_ultima_coluna_linha_com_valor_isolado():
    # caso da linha "G" onde o R$ fica separado do número por causa do PDF
    assert _valor_ultima_coluna("G Valor Bruto ( R$ D+E) - F 277,00") == "277,00"


def test_valor_ultima_coluna_sem_valor():
    assert _valor_ultima_coluna("texto sem numero") == "0,00"


def test_parse_data_br():
    assert _parse_data_br("Extrato de Pagamento de 22/07/2026") == "2026-07-22"


def test_parse_data_br_sem_match():
    assert _parse_data_br("sem data aqui") == ""


def test_normalizar_apolice_planilha_e_pdf_dao_o_mesmo_resultado():
    assert _normalizar_apolice("001117397/000000001") == "1117397/1"
    assert _normalizar_apolice("1117397/1") == "1117397/1"


def test_normalizar_apolice_preserva_zero_puro():
    assert _normalizar_apolice("000/000") == "0/0"
