from conciliacao import inserir_e_conciliar
from conftest import FakeSupabaseClient


def _client_base(**extra_tabelas):
    dados = {
        "contas_bancarias": [{"id": "conta-1", "empresa_id": "emp-1"}],
        "lotes_comissao": [],
        "lancamentos_previstos": [],
        "regras_identificacao": [],
        **extra_tabelas,
    }
    return FakeSupabaseClient(dados)


def test_concilia_com_lote_de_comissao_pendente():
    client = _client_base(
        lotes_comissao=[
            {
                "id": "lote-1",
                "empresa_id": "emp-1",
                "data_pagamento": "2026-08-21",
                "valor_liquido": 977.59,
                "status": "pendente",
            }
        ],
    )
    conciliou = inserir_e_conciliar(
        client,
        ofx_importacao_id="imp-1",
        conta_id="conta-1",
        fit_id="FIT1",
        data="2026-08-21",
        valor=977.59,
        descricao="SUHAI SEGURADORA",
        regras_identificacao=[],
    )
    assert conciliou is True
    txn = client.table("ofx_transacoes").select("*").execute().data[0]
    assert txn["conciliado"] is True
    lote = client.table("lotes_comissao").select("*").eq("id", "lote-1").execute().data[0]
    assert lote["status"] == "conciliado"
    assert lote["ofx_transacao_id"] == txn["id"]


def test_concilia_com_lancamento_previsto():
    client = _client_base(
        lancamentos_previstos=[
            {"id": "lanc-1", "empresa_id": "emp-1", "tipo": "pagar", "valor": 250.0, "status": "previsto"},
        ],
    )
    conciliou = inserir_e_conciliar(
        client,
        ofx_importacao_id="imp-1",
        conta_id="conta-1",
        fit_id="FIT2",
        data="2026-08-25",
        valor=-250.0,
        descricao="Pagamento fornecedor",
        regras_identificacao=[],
    )
    assert conciliou is True
    lanc = client.table("lancamentos_previstos").select("*").eq("id", "lanc-1").execute().data[0]
    assert lanc["status"] == "pago"
    assert lanc["data_pagamento"] == "2026-08-25"


def test_concilia_despesa_fixa_de_valor_variavel_via_regra_identificacao():
    client = _client_base(
        lancamentos_previstos=[
            {
                "id": "lanc-luz",
                "empresa_id": "emp-1",
                "tipo": "pagar",
                "valor": 100.0,  # provisionado, diferente do real
                "status": "previsto",
                "data_vencimento": "2026-08-10",
                "grupo_id": "grupo-luz",
                "fornecedor_id": "forn-edp",
            },
            {
                # próxima ocorrência já provisionada da mesma recorrência
                "id": "lanc-luz-prox",
                "empresa_id": "emp-1",
                "tipo": "pagar",
                "valor": 100.0,
                "status": "previsto",
                "data_vencimento": "2026-09-10",
                "grupo_id": "grupo-luz",
                "fornecedor_id": "forn-edp",
            },
        ],
        regras_identificacao=[{"padrao_descricao": "edp", "fornecedor_id": "forn-edp"}],
    )
    conciliou = inserir_e_conciliar(
        client,
        ofx_importacao_id="imp-1",
        conta_id="conta-1",
        fit_id="FIT3",
        data="2026-08-12",
        valor=-142.30,  # valor real, diferente do provisionado
        descricao="Débito EDP Energia",
        regras_identificacao=client.table("regras_identificacao").select("*").execute().data,
    )
    assert conciliou is True
    lanc = client.table("lancamentos_previstos").select("*").eq("id", "lanc-luz").execute().data[0]
    assert lanc["status"] == "pago"
    assert lanc["valor"] == 142.30
    # propaga o valor real pra próxima ocorrência ainda prevista
    prox = client.table("lancamentos_previstos").select("*").eq("id", "lanc-luz-prox").execute().data[0]
    assert prox["valor"] == 142.30
    assert prox["status"] == "previsto"  # essa continua prevista, só o valor mudou


def test_nao_concilia_quando_nao_ha_candidato():
    client = _client_base()
    conciliou = inserir_e_conciliar(
        client,
        ofx_importacao_id="imp-1",
        conta_id="conta-1",
        fit_id="FIT4",
        data="2026-08-21",
        valor=50.0,
        descricao="Transferência qualquer",
        regras_identificacao=[],
    )
    assert conciliou is False
    txn = client.table("ofx_transacoes").select("*").execute().data[0]
    # "conciliado" só é setado explicitamente quando concilia (via update);
    # sem conciliar, fica no default da coluna real (false no Postgres) —
    # o fake não simula default de coluna, só o que foi de fato inserido.
    assert txn.get("conciliado", False) is False
