from relatorios import LinhaDRE, montar_balanco, montar_dre


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
