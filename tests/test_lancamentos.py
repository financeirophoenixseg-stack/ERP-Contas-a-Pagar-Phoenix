from datetime import date

from lancamentos import gerar_parcelas, gerar_recorrencia, somar_meses


def test_somar_meses_simples():
    assert somar_meses(date(2026, 1, 15), 1) == date(2026, 2, 15)


def test_somar_meses_ajusta_dia_curto():
    assert somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_somar_meses_vira_ano():
    assert somar_meses(date(2026, 12, 5), 1) == date(2027, 1, 5)


def test_gerar_parcelas_soma_bate_com_total():
    parcelas = gerar_parcelas(1000.0, 3, date(2026, 1, 10))
    assert len(parcelas) == 3
    assert round(sum(p.valor for p in parcelas), 2) == 1000.0
    assert [p.data_vencimento for p in parcelas] == [
        date(2026, 1, 10),
        date(2026, 2, 10),
        date(2026, 3, 10),
    ]
    assert [p.parcela_atual for p in parcelas] == [1, 2, 3]


def test_gerar_parcelas_ultima_absorve_arredondamento():
    parcelas = gerar_parcelas(100.0, 3, date(2026, 1, 1))
    valores = [p.valor for p in parcelas]
    assert valores[0] == valores[1] == 33.33
    assert valores[2] == 33.34  # 100 - 33.33 - 33.33


def test_gerar_recorrencia_mesmo_valor_todo_mes():
    ocorrencias = gerar_recorrencia(500.0, date(2026, 1, 5), quantidade_meses=4)
    assert len(ocorrencias) == 4
    assert all(o.valor == 500.0 for o in ocorrencias)
    assert all(o.recorrente for o in ocorrencias)
    assert [o.data_vencimento for o in ocorrencias] == [
        date(2026, 1, 5),
        date(2026, 2, 5),
        date(2026, 3, 5),
        date(2026, 4, 5),
    ]
