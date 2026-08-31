from unittest.mock import MagicMock, patch

import pytest

import pluggy_integration


def _resposta_falsa(status_code: int, json_data: dict) -> MagicMock:
    resposta = MagicMock()
    resposta.status_code = status_code
    resposta.json.return_value = json_data
    resposta.text = str(json_data)
    return resposta


def test_esta_configurado_depende_das_env_vars(monkeypatch):
    monkeypatch.delenv("PLUGGY_CLIENT_ID", raising=False)
    monkeypatch.delenv("PLUGGY_CLIENT_SECRET", raising=False)
    assert pluggy_integration.esta_configurado() is False
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    assert pluggy_integration.esta_configurado() is True


def test_obter_api_key_autentica_e_retorna_chave(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = None
    pluggy_integration._cache_api_key["expira_em"] = 0

    with patch("pluggy_integration.requests.post", return_value=_resposta_falsa(200, {"apiKey": "chave-fake"})):
        chave = pluggy_integration.obter_api_key()

    assert chave == "chave-fake"


def test_obter_api_key_usa_cache_sem_chamar_de_novo(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = "chave-em-cache"
    import time

    pluggy_integration._cache_api_key["expira_em"] = time.time() + 3600

    with patch("pluggy_integration.requests.post") as mock_post:
        chave = pluggy_integration.obter_api_key()

    mock_post.assert_not_called()
    assert chave == "chave-em-cache"


def test_obter_api_key_erro_levanta_excecao(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = None
    pluggy_integration._cache_api_key["expira_em"] = 0

    with patch("pluggy_integration.requests.post", return_value=_resposta_falsa(401, {"message": "invalido"})):
        with pytest.raises(RuntimeError):
            pluggy_integration.obter_api_key()


def test_criar_connect_token(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = "chave-fake"
    import time

    pluggy_integration._cache_api_key["expira_em"] = time.time() + 3600

    with patch("pluggy_integration.requests.post", return_value=_resposta_falsa(200, {"accessToken": "token-fake"})):
        token = pluggy_integration.criar_connect_token()

    assert token == "token-fake"


def test_listar_contas(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = "chave-fake"
    import time

    pluggy_integration._cache_api_key["expira_em"] = time.time() + 3600

    resultado_api = {
        "results": [
            {"id": "conta-1", "name": "Conta Corrente", "subtype": "CHECKING_ACCOUNT", "number": "1234-5", "balance": 1000.0}
        ]
    }
    with patch("pluggy_integration.requests.get", return_value=_resposta_falsa(200, resultado_api)):
        contas = pluggy_integration.listar_contas("item-fake")

    assert len(contas) == 1
    assert contas[0].id == "conta-1"
    assert contas[0].nome == "Conta Corrente"
    assert contas[0].saldo == 1000.0


def test_listar_transacoes(monkeypatch):
    monkeypatch.setenv("PLUGGY_CLIENT_ID", "abc")
    monkeypatch.setenv("PLUGGY_CLIENT_SECRET", "def")
    pluggy_integration._cache_api_key["valor"] = "chave-fake"
    import time

    pluggy_integration._cache_api_key["expira_em"] = time.time() + 3600

    resultado_api = {
        "results": [{"id": "txn-1", "date": "2026-08-27T00:00:00.000Z", "description": "Pix recebido", "amount": 250.0}]
    }
    with patch("pluggy_integration.requests.get", return_value=_resposta_falsa(200, resultado_api)):
        transacoes = pluggy_integration.listar_transacoes("conta-1", desde="2026-08-01")

    assert len(transacoes) == 1
    assert transacoes[0].data == "2026-08-27"
    assert transacoes[0].valor == 250.0
