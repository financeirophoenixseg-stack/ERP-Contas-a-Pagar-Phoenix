from graficos import _passo_bonito, grafico_donut_status, grafico_fluxo_caixa


def test_passo_bonito_valores_tipicos():
    assert _passo_bonito(0) == (10.0, 1)
    passo, divisoes = _passo_bonito(41500)
    assert passo * divisoes >= 41500
    assert divisoes <= 5


def test_passo_bonito_cobre_o_maximo():
    for valor in [1, 7, 42, 199, 999, 12345, 987654]:
        passo, divisoes = _passo_bonito(valor)
        assert passo * divisoes >= valor


def test_grafico_fluxo_caixa_nao_quebra_com_dados_reais():
    html = grafico_fluxo_caixa(["Mar", "Abr", "Mai"], [1000.0, 1200.0, 900.0], [500.0, 600.0, 550.0])
    assert "<svg" in html
    assert "R$ 900,00" in html or "R$ 1.200,00" in html


def test_grafico_fluxo_caixa_lista_vazia_nao_quebra():
    html = grafico_fluxo_caixa([], [], [])
    assert "svg" not in html  # cai no caminho "sem dados"


def test_grafico_donut_status_soma_correta():
    html = grafico_donut_status([("Conciliadas", 18, "#0ca30c"), ("Pendentes", 5, "#fab219"), ("Divergentes", 0, "#d03b3b")])
    assert ">23<" in html
    assert "Conciliadas" in html


def test_grafico_donut_status_total_zero_nao_quebra():
    html = grafico_donut_status([("Conciliadas", 0, "#0ca30c"), ("Pendentes", 0, "#fab219")])
    assert ">0<" in html
