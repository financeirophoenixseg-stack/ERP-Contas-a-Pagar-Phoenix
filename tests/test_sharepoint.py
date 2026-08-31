import pytest

import sharepoint


def test_caminho_para_url_aceita_caminho_normal():
    resultado = sharepoint._caminho_para_url("2026/08/boleto/abc123_arquivo.pdf")
    assert resultado == "2026/08/boleto/abc123_arquivo.pdf"


def test_caminho_para_url_recusa_segmento_de_travessia():
    with pytest.raises(ValueError):
        sharepoint._caminho_para_url("2026/08/boleto/abc123_../../../Contratos/importante.pdf")


def test_caminho_para_url_recusa_segmento_vazio():
    with pytest.raises(ValueError):
        sharepoint._caminho_para_url("2026//boleto/arquivo.pdf")


def test_caminho_para_url_escapa_caracteres_especiais():
    resultado = sharepoint._caminho_para_url("2026/08/boleto/arquivo com espaço.pdf")
    assert "%20" in resultado
