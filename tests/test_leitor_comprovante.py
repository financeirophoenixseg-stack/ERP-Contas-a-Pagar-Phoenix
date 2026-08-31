from unittest.mock import MagicMock, patch

import pytest

import leitor_comprovante


def test_ler_comprovante_extrai_dados():
    dados_ia = {
        "valor": 1000.0,
        "data_pagamento": "2026-08-27",
        "descricao": "Transferência - Energia EDP",
        "favorecido": "EDP",
        "pagador": "Vizentim",
        "confianca": "alta",
        "observacoes": None,
    }
    with patch("leitor_comprovante.ler_documento", return_value=dados_ia) as mock_ler:
        dados = leitor_comprovante.ler_comprovante(b"conteudo pdf fake")

    mock_ler.assert_called_once()
    assert dados.valor == 1000.0
    assert dados.data_pagamento == "2026-08-27"
    assert dados.favorecido == "EDP"


def test_ler_comprovante_propaga_erro():
    with patch("leitor_comprovante.ler_documento", side_effect=RuntimeError("erro")):
        with pytest.raises(RuntimeError):
            leitor_comprovante.ler_comprovante(b"conteudo pdf fake")


def _client_com_candidatos(candidatos: list[dict]) -> MagicMock:
    client = MagicMock()
    query = client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value
    query.execute.return_value.data = candidatos
    return client


def test_encontrar_lancamento_casamento_unico():
    client = _client_com_candidatos([{"id": "abc-123", "valor": 1000.0, "data_vencimento": "2026-08-25"}])
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, "2026-08-27")
    assert resultado == "abc-123"


def test_encontrar_lancamento_pagamento_atrasado_dentro_da_margem():
    # caso real observado: pagamento 4 dias após o vencimento (dentro dos +-7 dias)
    client = _client_com_candidatos([{"id": "abc-123", "valor": 500.0, "data_vencimento": "2026-08-23"}])
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 500.0, "2026-08-27")
    assert resultado == "abc-123"


def test_encontrar_lancamento_sem_candidato():
    client = _client_com_candidatos([])
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, "2026-08-27")
    assert resultado is None


def test_encontrar_lancamento_ambiguo_nao_decide():
    client = _client_com_candidatos(
        [
            {"id": "abc-123", "valor": 1000.0, "data_vencimento": "2026-08-25"},
            {"id": "def-456", "valor": 1000.0, "data_vencimento": "2026-08-26"},
        ]
    )
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, "2026-08-27")
    assert resultado is None


def test_encontrar_lancamento_valor_fora_da_tolerancia_filtrado():
    client = _client_com_candidatos([{"id": "abc-123", "valor": 1000.5, "data_vencimento": "2026-08-25"}])
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, "2026-08-27")
    assert resultado is None


def test_encontrar_lancamento_desempata_por_vencimento_exato():
    # dois pagamentos de R$500 na mesma janela, mas só um vence exatamente na data do pagamento
    client = _client_com_candidatos(
        [
            {"id": "abc-123", "valor": 500.0, "data_vencimento": "2026-08-27"},
            {"id": "def-456", "valor": 500.0, "data_vencimento": "2026-08-25"},
        ]
    )
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 500.0, "2026-08-27")
    assert resultado == "abc-123"


def test_encontrar_lancamento_desempata_por_nome_do_favorecido():
    client = _client_com_candidatos(
        [
            {"id": "abc-123", "valor": 500.0, "data_vencimento": "2026-08-25", "fornecedores": {"nome": "EDP Energia"}},
            {"id": "def-456", "valor": 500.0, "data_vencimento": "2026-08-26", "fornecedores": {"nome": "Locadora XPTO"}},
        ]
    )
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 500.0, "2026-08-27", favorecido="EDP")
    assert resultado == "abc-123"


def test_encontrar_lancamento_ainda_ambiguo_apos_desempate_nao_decide():
    # mesmo vencimento exato pros dois, nome não ajuda -> continua ambíguo
    client = _client_com_candidatos(
        [
            {"id": "abc-123", "valor": 500.0, "data_vencimento": "2026-08-27", "fornecedores": {"nome": "Fornecedor A"}},
            {"id": "def-456", "valor": 500.0, "data_vencimento": "2026-08-27", "fornecedores": {"nome": "Fornecedor B"}},
        ]
    )
    resultado = leitor_comprovante.encontrar_lancamento_correspondente(client, 500.0, "2026-08-27", favorecido="Sicoob")
    assert resultado is None


def test_encontrar_lancamento_sem_valor_ou_data_retorna_none():
    client = MagicMock()
    assert leitor_comprovante.encontrar_lancamento_correspondente(client, None, "2026-08-27") is None
    assert leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, None) is None
    assert leitor_comprovante.encontrar_lancamento_correspondente(client, 1000.0, "data-invalida") is None
