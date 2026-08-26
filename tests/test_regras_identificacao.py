from regras_identificacao import sugerir

REGRAS = [
    {"padrao_descricao": "ALUGUEL", "fornecedor_id": "f1", "cliente_id": None, "plano_conta_id": "c1"},
    {"padrao_descricao": "SUHAI SEGURADORA", "fornecedor_id": None, "cliente_id": None, "plano_conta_id": "c2"},
]


def test_sugerir_encontra_por_substring_case_insensitive():
    match = sugerir(REGRAS, "pagamento aluguel escritorio setembro")
    assert match["fornecedor_id"] == "f1"


def test_sugerir_sem_match_retorna_none():
    assert sugerir(REGRAS, "TRANSFERENCIA DESCONHECIDA") is None


def test_sugerir_com_descricao_vazia():
    assert sugerir(REGRAS, "") is None
    assert sugerir(REGRAS, None) is None
