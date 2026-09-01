from datetime import date, timedelta

from conftest import FakeSupabaseClient
from relatorios import (
    LinhaDRE,
    calcular_aging,
    calcular_balanco,
    calcular_comissoes_por_cliente,
    calcular_comissoes_por_seguradora,
    calcular_dre,
    calcular_evolucao_mensal,
    calcular_fluxo_projetado,
    calcular_impostos_retidos,
    montar_balanco,
    montar_dre,
)


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


# ---------------------------------------------------------------------------
# Relatórios gerenciais
# ---------------------------------------------------------------------------

HOJE = date.today()


def _iso(dias_a_partir_de_hoje: int) -> str:
    return (HOJE + timedelta(days=dias_a_partir_de_hoje)).isoformat()


def test_calcular_fluxo_projetado_agrupa_por_faixa_de_dias():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {"tipo": "pagar", "valor": 100.0, "data_vencimento": _iso(-5), "empresa_id": "emp-1", "status": "previsto"},  # atrasado
                {"tipo": "receber", "valor": 500.0, "data_vencimento": _iso(10), "empresa_id": "emp-1", "status": "previsto"},  # 0-30
                {"tipo": "pagar", "valor": 200.0, "data_vencimento": _iso(45), "empresa_id": "emp-1", "status": "previsto"},  # 31-60
                {"tipo": "receber", "valor": 50.0, "data_vencimento": _iso(120), "empresa_id": "emp-1", "status": "previsto"},  # >90
            ],
            "ofx_transacoes": [],
        }
    )
    resultado = calcular_fluxo_projetado(client)
    buckets_por_nome = {b["periodo"]: b for b in resultado["buckets"]}
    assert buckets_por_nome["Atrasado"]["saidas"] == 100.0
    assert buckets_por_nome["Hoje a 30 dias"]["entradas"] == 500.0
    assert buckets_por_nome["31 a 60 dias"]["saidas"] == 200.0
    assert buckets_por_nome["Mais de 90 dias"]["entradas"] == 50.0
    assert buckets_por_nome["61 a 90 dias"]["entradas"] == 0.0
    assert buckets_por_nome["61 a 90 dias"]["saidas"] == 0.0


def test_calcular_fluxo_projetado_soma_saldo_acumulado_a_partir_do_caixa():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {"tipo": "receber", "valor": 1000.0, "data_vencimento": _iso(10), "empresa_id": "emp-1", "status": "previsto"},
            ],
            "ofx_transacoes": [{"valor": 500.0, "contas_bancarias": {"empresa_id": "emp-1"}}],
        }
    )
    resultado = calcular_fluxo_projetado(client)
    assert resultado["caixa_atual"] == 500.0
    bucket_30 = next(b for b in resultado["buckets"] if b["periodo"] == "Hoje a 30 dias")
    assert bucket_30["saldo_projetado_acumulado"] == 1500.0


def test_calcular_aging_agrupa_por_faixa_de_atraso():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {
                    "descricao": "Aluguel",
                    "valor": 100.0,
                    "data_vencimento": _iso(-10),
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "Imobiliária X"},
                },
                {
                    "descricao": "Luz",
                    "valor": 50.0,
                    "data_vencimento": _iso(-45),
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "EDP"},
                },
                {
                    "descricao": "Água",
                    "valor": 30.0,
                    "data_vencimento": _iso(-100),
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "Sabesp"},
                },
            ],
        }
    )
    resultado = calcular_aging(client, tipo="pagar")
    faixas = {f["faixa"]: f["valor"] for f in resultado["por_faixa"]}
    assert faixas["0-30 dias"] == 100.0
    assert faixas["31-60 dias"] == 50.0
    assert faixas["Mais de 90 dias"] == 30.0
    assert resultado["total"] == 180.0
    assert resultado["itens"][0]["descricao"] == "Água"  # mais atrasado primeiro


def test_calcular_aging_vazio_nao_quebra():
    resultado = calcular_aging(FakeSupabaseClient({}), tipo="receber")
    assert resultado["total"] == 0.0
    assert resultado["itens"] == []


def test_calcular_comissoes_por_seguradora_agrupa_e_ordena():
    client = FakeSupabaseClient(
        {
            "lotes_comissao": [
                {
                    "valor_bruto": 1000.0,
                    "valor_liquido": 900.0,
                    "status": "conciliado",
                    "data_pagamento": "2026-08-10",
                    "seguradoras": {"nome": "Suhai"},
                },
                {
                    "valor_bruto": 2000.0,
                    "valor_liquido": 1800.0,
                    "status": "pendente",
                    "data_pagamento": "2026-08-11",
                    "seguradoras": {"nome": "Porto Seguro"},
                },
                {
                    "valor_bruto": 500.0,
                    "valor_liquido": 450.0,
                    "status": "conciliado",
                    "data_pagamento": "2026-08-12",
                    "seguradoras": {"nome": "Suhai"},
                },
            ],
        }
    )
    resultado = calcular_comissoes_por_seguradora(client, "2026-08-01", "2026-08-31")
    assert resultado[0]["seguradora"] == "Porto Seguro"
    assert resultado[0]["valor_liquido"] == 1800.0
    assert resultado[0]["pendente"] == 1
    suhai = next(r for r in resultado if r["seguradora"] == "Suhai")
    assert suhai["valor_liquido"] == 1350.0
    assert suhai["qtd_lotes"] == 2


def test_calcular_comissoes_por_cliente_ranking():
    client = FakeSupabaseClient(
        {
            "lotes_comissao": [{"id": "lote-1", "empresa_id": "emp-1", "data_pagamento": "2026-08-10"}],
            "movimentacoes_comissao": [
                {"valor_comissao": 100.0, "lote_id": "lote-1", "clientes": {"nome": "Cliente A"}},
                {"valor_comissao": 50.0, "lote_id": "lote-1", "clientes": {"nome": "Cliente A"}},
                {"valor_comissao": 300.0, "lote_id": "lote-1", "clientes": {"nome": "Cliente B"}},
            ],
        }
    )
    resultado = calcular_comissoes_por_cliente(client, "2026-08-01", "2026-08-31")
    assert resultado[0] == {"cliente": "Cliente B", "valor_comissao": 300.0}
    assert resultado[1] == {"cliente": "Cliente A", "valor_comissao": 150.0}


def test_calcular_comissoes_por_cliente_sem_lotes_retorna_vazio():
    assert calcular_comissoes_por_cliente(FakeSupabaseClient({}), "2026-08-01", "2026-08-31") == []


def test_calcular_impostos_retidos_soma_todos_os_tipos():
    client = FakeSupabaseClient(
        {
            "lotes_comissao": [
                {"valor_irrf": 10.0, "valor_iss": 5.0, "valor_inss": 2.0, "valor_pis_cofins_csll": 3.0, "data_pagamento": "2026-08-10"},
                {"valor_irrf": 20.0, "valor_iss": 0.0, "valor_inss": 0.0, "valor_pis_cofins_csll": 1.0, "data_pagamento": "2026-08-11"},
            ],
        }
    )
    resultado = calcular_impostos_retidos(client, "2026-08-01", "2026-08-31")
    assert resultado == {"irrf": 30.0, "iss": 5.0, "inss": 2.0, "pis_cofins_csll": 4.0, "total": 41.0}


def test_calcular_evolucao_mensal_agrupa_por_mes():
    hoje_iso = HOJE.isoformat()
    client = FakeSupabaseClient(
        {
            "ofx_transacoes": [
                {"data": hoje_iso, "valor": 1000.0, "contas_bancarias": {"empresa_id": "emp-1"}},
                {"data": hoje_iso, "valor": -300.0, "contas_bancarias": {"empresa_id": "emp-1"}},
            ]
        }
    )
    resultado = calcular_evolucao_mensal(client, meses=1)
    assert len(resultado) == 1
    assert resultado[0]["receitas"] == 1000.0
    assert resultado[0]["despesas"] == 300.0
    assert resultado[0]["resultado"] == 700.0
