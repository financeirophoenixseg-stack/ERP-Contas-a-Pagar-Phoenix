import json
from unittest.mock import MagicMock, patch

import pytest

import leitor_ia


def _resposta_falsa(texto: str) -> MagicMock:
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = texto
    resposta = MagicMock()
    resposta.content = [bloco]
    return resposta


def test_ler_documento_retorna_json_valido():
    json_valido = json.dumps({"campo": "valor"})
    with patch("leitor_ia.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa(json_valido)

        resultado = leitor_ia.ler_documento(b"conteudo pdf fake", "prompt de sistema", "instrucao")

    assert resultado == {"campo": "valor"}


def test_ler_documento_remove_bloco_markdown():
    json_com_cerca = '```json\n{"campo": "valor"}\n```'
    with patch("leitor_ia.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa(json_com_cerca)

        resultado = leitor_ia.ler_documento(b"conteudo pdf fake", "prompt de sistema", "instrucao")

    assert resultado == {"campo": "valor"}


def test_ler_documento_json_invalido_levanta_erro():
    with patch("leitor_ia.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        instancia.messages.create.return_value = _resposta_falsa("isso não é json")

        with pytest.raises(RuntimeError):
            leitor_ia.ler_documento(b"conteudo pdf fake", "prompt de sistema", "instrucao")


def test_esta_configurado_depende_da_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert leitor_ia.esta_configurado() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    assert leitor_ia.esta_configurado() is True
