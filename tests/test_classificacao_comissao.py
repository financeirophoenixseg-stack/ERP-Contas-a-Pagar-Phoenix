from classificacao_comissao import classificar

REGRA = {"parcelas_agenciamento": 3}


def test_classificar_parcela_dentro_do_agenciamento():
    assert classificar("1", REGRA) == "agenciamento"
    assert classificar("3", REGRA) == "agenciamento"


def test_classificar_parcela_apos_agenciamento_e_vitalicia():
    assert classificar("4", REGRA) == "vitalicio"
    assert classificar("24", REGRA) == "vitalicio"


def test_classificar_sem_regra_nao_classifica():
    assert classificar("1", None) is None


def test_classificar_parcela_nao_numerica_nao_classifica():
    assert classificar("N/A", REGRA) is None


def test_classificar_zero_parcelas_agenciamento_tudo_vitalicio():
    assert classificar("1", {"parcelas_agenciamento": 0}) == "vitalicio"
