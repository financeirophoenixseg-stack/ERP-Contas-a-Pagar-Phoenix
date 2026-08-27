import json
from unittest.mock import MagicMock, patch

import pytest

import leitor_boleto


def _resposta_falsa(texto: str) -> MagicMock:
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = texto
    resposta = MagicMock()
    resposta.content = [bloco]
    return resposta


def test_ler_boleto_extrai_json_valido():
    json_valido = json.dumps(
        {
            "valor": 1578.01,
            "data_vencimento": "2026-09-18",
            "descricao": "FGTS 08/2026",
            "favorecido": "Caixa Econômica Federal",
            "documento_pagador": "08065152000100",
            "confianca": "alta",
            "observacoes": None,
        }
    )
    with patch("leitor_boleto.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa(json_valido)

        dados = leitor_boleto.ler_boleto(b"conteudo pdf fake")

    assert dados.valor == 1578.01
    assert dados.data_vencimento == "2026-09-18"
    assert dados.descricao == "FGTS 08/2026"
    assert dados.favorecido == "Caixa Econômica Federal"
    assert dados.confianca == "alta"


def test_ler_boleto_json_invalido_levanta_erro():
    with patch("leitor_boleto.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa("isso não é json")

        with pytest.raises(RuntimeError):
            leitor_boleto.ler_boleto(b"conteudo pdf fake")


def test_ler_boleto_confianca_ausente_vira_baixa():
    json_sem_confianca = json.dumps(
        {
            "valor": 100.0,
            "data_vencimento": "2026-01-01",
            "descricao": "Teste",
            "favorecido": None,
            "documento_pagador": None,
            "observacoes": None,
        }
    )
    with patch("leitor_boleto.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa(json_sem_confianca)

        dados = leitor_boleto.ler_boleto(b"conteudo pdf fake")

    assert dados.confianca == "baixa"


def test_esta_configurado_depende_da_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert leitor_boleto.esta_configurado() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    assert leitor_boleto.esta_configurado() is True
