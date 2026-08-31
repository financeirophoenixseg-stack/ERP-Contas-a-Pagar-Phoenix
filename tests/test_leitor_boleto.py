from unittest.mock import patch

import pytest

import leitor_boleto


def test_ler_boleto_extrai_dados():
    dados_ia = {
        "valor": 1578.01,
        "data_vencimento": "2026-09-18",
        "descricao": "FGTS 08/2026",
        "favorecido": "Caixa Econômica Federal",
        "documento_pagador": "08065152000100",
        "confianca": "alta",
        "observacoes": None,
    }
    with patch("leitor_boleto.ler_documento", return_value=dados_ia) as mock_ler:
        dados = leitor_boleto.ler_boleto(b"conteudo pdf fake")

    mock_ler.assert_called_once()
    assert dados.valor == 1578.01
    assert dados.data_vencimento == "2026-09-18"
    assert dados.descricao == "FGTS 08/2026"
    assert dados.favorecido == "Caixa Econômica Federal"
    assert dados.confianca == "alta"


def test_ler_boleto_propaga_erro_de_leitura():
    with patch("leitor_boleto.ler_documento", side_effect=RuntimeError("resposta inválida")):
        with pytest.raises(RuntimeError):
            leitor_boleto.ler_boleto(b"conteudo pdf fake")


def test_ler_boleto_confianca_ausente_vira_baixa():
    dados_ia = {
        "valor": 100.0,
        "data_vencimento": "2026-01-01",
        "descricao": "Teste",
        "favorecido": None,
        "documento_pagador": None,
        "observacoes": None,
    }
    with patch("leitor_boleto.ler_documento", return_value=dados_ia):
        dados = leitor_boleto.ler_boleto(b"conteudo pdf fake")

    assert dados.confianca == "baixa"


def test_esta_configurado_depende_da_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert leitor_boleto.esta_configurado() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    assert leitor_boleto.esta_configurado() is True
