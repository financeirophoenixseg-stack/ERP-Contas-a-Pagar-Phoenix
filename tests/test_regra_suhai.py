from regra_suhai import bate_com_formula, comissao_esperada, parcelas_enquadradas

# Casos extraídos da planilha real do usuário ("Cálculo Comissão - Novo Suhai.xlsx")


def test_parcelas_enquadradas_exemplo_da_planilha():
    # C10 = 0.104 (10.4%) -> I10 = 0.73/0.104 = 7.019... -> J10 = 7
    assert parcelas_enquadradas(10.4) == 7


def test_parcelas_enquadradas_tab1():
    # tab 1 PJ = 10% -> 0.73/0.10 = 7.3 -> 7 (bate com L8 da planilha)
    assert parcelas_enquadradas(10.0) == 7


def test_parcelas_enquadradas_tab2_pj():
    # tab 2 PJ = 13% -> 0.73/0.13 = 5.615 -> 5 (bate com L9)
    assert parcelas_enquadradas(13.0) == 5


def test_parcelas_enquadradas_zero_ou_negativo():
    assert parcelas_enquadradas(0) == 0
    assert parcelas_enquadradas(None) == 0


def test_comissao_esperada_bate_com_caso_real_do_demonstrativo():
    # FERNANDO FRANCO NETO, parcela 001, 20%, valor_parcela 2.180,21 -> comissão 436,04
    assert comissao_esperada(2180.21, 20.0) == 436.04


def test_bate_com_formula_caso_real():
    assert bate_com_formula(436.04, 2180.21, 20.0)


def test_bate_com_formula_nao_bate_para_adiantamento():
    # Pagamento de Adiantamento: SIDNEI ROBERTO RODRIGUES, 25%, valor_parcela
    # 102,20, valor_comissao 102,20 (100%, nao segue a formula de vigencia)
    assert not bate_com_formula(102.20, 102.20, 25.0)
