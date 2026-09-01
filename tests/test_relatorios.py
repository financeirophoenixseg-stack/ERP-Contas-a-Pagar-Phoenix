from conftest import FakeSupabaseClient
from relatorios import LinhaDRE, calcular_balanco, calcular_dre, montar_balanco, montar_dre


def test_montar_dre_agrupa_por_categoria_e_soma():
    linhas = [
        LinhaDRE("receita", "Comissões", 1000.0),
        LinhaDRE("receita", "Comissões", 500.0),
        LinhaDRE("despesa", "Aluguel", 300.0),
    ]
    dre = montar_dre(linhas)
    assert dre["receitas"] == {"Comissões": 1500.0}
    assert dre["despesas"] == {"Aluguel": 300.0}
    assert dre["total_receitas"] == 1500.0
    assert dre["total_despesas"] == 300.0
    assert dre["resultado"] == 1200.0


def test_montar_dre_vazio():
    dre = montar_dre([])
    assert dre["total_receitas"] == 0.0
    assert dre["total_despesas"] == 0.0
    assert dre["resultado"] == 0.0


def test_montar_dre_prejuizo():
    linhas = [LinhaDRE("receita", "X", 100.0), LinhaDRE("despesa", "Y", 400.0)]
    assert montar_dre(linhas)["resultado"] == -300.0


def test_montar_balanco():
    balanco = montar_balanco(caixa=1000.0, contas_a_receber=200.0, contas_a_pagar=150.0)
    assert balanco["total_ativo"] == 1200.0
    assert balanco["total_passivo"] == 150.0
    assert balanco["patrimonio_liquido"] == 1050.0


def test_calcular_dre_soma_comissoes_impostos_e_lancamentos_pagos():
    client = FakeSupabaseClient(
        {
            "lotes_comissao": [
                {
                    "id": "lote-1",
                    "empresa_id": "emp-1",
                    "data_pagamento": "2026-08-10",
                    "valor_irrf": 10.0,
                    "valor_iss": 5.0,
                    "valor_inss": 0.0,
                    "valor_pis_cofins_csll": 2.0,
                }
            ],
            "movimentacoes_comissao": [
                {"valor_comissao": 1000.0, "lote_id": "lote-1"},
                {"valor_comissao": 500.0, "lote_id": "lote-1"},
            ],
            "lancamentos_previstos": [
                {
                    "tipo": "pagar",
                    "valor": 300.0,
                    "descricao": "Aluguel",
                    "status": "pago",
                    "data_pagamento": "2026-08-15",
                    "plano_contas": {"nome": "Aluguel"},
                },
            ],
            "ofx_transacoes": [
                {
                    "valor": -150.0,
                    "data": "2026-08-20",
                    "plano_conta_id": "conta-tarifas",
                    "plano_contas": {"nome": "Tarifas Bancárias", "tipo": "despesa"},
                    "contas_bancarias": {"empresa_id": "emp-1"},
                }
            ],
        }
    )
    dre = calcular_dre(client, "2026-08-01", "2026-08-31")
    assert dre["receitas"] == {"Receita de Comissões (bruto)": 1500.0}
    assert dre["despesas"] == {
        "Impostos sobre Comissões (IRRF/ISS/INSS/PIS-COFINS-CSLL)": 17.0,
        "Aluguel": 300.0,
        "Tarifas Bancárias": 150.0,
    }
    assert dre["total_receitas"] == 1500.0
    assert dre["total_despesas"] == 467.0
    assert dre["resultado"] == 1033.0


def test_calcular_dre_periodo_vazio():
    client = FakeSupabaseClient({})
    dre = calcular_dre(client, "2026-08-01", "2026-08-31")
    assert dre["total_receitas"] == 0.0
    assert dre["total_despesas"] == 0.0
    assert dre["resultado"] == 0.0


def test_calcular_dre_filtra_ofx_por_empresa():
    client = FakeSupabaseClient(
        {
            "ofx_transacoes": [
                {
                    "valor": -100.0,
                    "data": "2026-08-20",
                    "plano_conta_id": "conta-aluguel",
                    "plano_contas": {"nome": "Aluguel", "tipo": "despesa"},
                    "contas_bancarias": {"empresa_id": "emp-outra"},
                }
            ],
        }
    )
    # o filtro por empresa da transação OFX é feito em Python (não dá pra
    # filtrar via .eq() porque empresa_id vem de uma tabela relacionada) —
    # precisa continuar funcionando mesmo com o fake aplicando os outros
    # filtros de verdade.
    dre = calcular_dre(client, "2026-08-01", "2026-08-31", empresa_id="emp-1")
    assert dre["total_despesas"] == 0.0


def test_calcular_balanco():
    client = FakeSupabaseClient(
        {
            "ofx_transacoes": [
                {"valor": 1000.0, "contas_bancarias": {"empresa_id": "emp-1"}},
                {"valor": -200.0, "contas_bancarias": {"empresa_id": "emp-1"}},
            ],
            "lancamentos_previstos": [
                {"valor": 300.0, "empresa_id": "emp-1", "status": "previsto", "tipo": "receber"},
                {"valor": 120.0, "empresa_id": "emp-1", "status": "previsto", "tipo": "pagar"},
                {"valor": 999.0, "empresa_id": "emp-1", "status": "pago", "tipo": "receber"},  # já pago, não conta
            ],
        }
    )
    balanco = calcular_balanco(client, empresa_id="emp-1")
    assert balanco["ativo"]["Caixa e Bancos"] == 800.0
    assert balanco["ativo"]["Contas a Receber"] == 300.0
    assert balanco["passivo"]["Contas a Pagar"] == 120.0
    assert balanco["total_ativo"] == 1100.0
    assert balanco["patrimonio_liquido"] == 980.0
