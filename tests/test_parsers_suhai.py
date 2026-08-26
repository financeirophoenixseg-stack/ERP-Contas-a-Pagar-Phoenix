from parsers.suhai import (
    _classify_tipo,
    _limpar_nome_cliente,
    _parse_apolice_endosso,
    _to_float,
)


def test_to_float_handles_thousands_and_negative():
    assert _to_float("2.180,21") == 2180.21
    assert _to_float("-52,85") == -52.85
    assert _to_float("0,00") == 0.0
    assert _to_float("977,59") == 977.59


def test_classify_tipo_cancelamento_precedes_adiantamento():
    assert _classify_tipo("Cancelamento de Adiantamento") == "cancelamento"


def test_classify_tipo_recuperacao():
    assert _classify_tipo("Recup. Comissao de Corretagem") == "recuperacao"


def test_classify_tipo_adiantamento():
    assert _classify_tipo("Pagamento de Adiantamento") == "adiantamento"


def test_classify_tipo_pagamento_corretagem():
    assert _classify_tipo("Pagto. Comiss�o de Corretagem") == "pagamento"


def test_classify_tipo_handles_character_spaced_artifact():
    assert _classify_tipo("C a n c e l a m e n t o d e A diantamento") == "cancelamento"


def test_parse_apolice_endosso_normal():
    assert _parse_apolice_endosso("1003112197766 End: 0000000") == ("1003112197766", "0000000")


def test_parse_apolice_endosso_character_spaced_artifact():
    assert _parse_apolice_endosso("1 0 0 3 1 1 1 6 7 2 4 6 7 E n d : 3 3 0 9 7 8 3") == (
        "1003111672467",
        "3309783",
    )


def test_limpar_nome_cliente_strips_trailing_code():
    assert _limpar_nome_cliente("JOSE ADRIANO PINHEIRO COSTA 278442") == "JOSE ADRIANO PINHEIRO COSTA"


def test_limpar_nome_cliente_keeps_normal_name():
    assert _limpar_nome_cliente("RICARDO NERES DE SANTANA") == "RICARDO NERES DE SANTANA"
