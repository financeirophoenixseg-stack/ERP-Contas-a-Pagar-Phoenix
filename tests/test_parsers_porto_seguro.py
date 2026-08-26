from parsers.porto_seguro import (
    _linhas_producao,
    _parse_data_br,
    _to_float_br,
    detectar_html,
    detectar_pdf,
)


def test_to_float_br():
    assert _to_float_br("785,51") == 785.51
    assert _to_float_br("1.375,43") == 1375.43
    assert _to_float_br("-159,77") == -159.77


def test_parse_data_br():
    assert _parse_data_br("11/08/2026") == "2026-08-11"


def test_detectar_pdf():
    assert detectar_pdf("ANALÍTICO DE PAGAMENTOS DE COMISSÕES ... Susep Favorecida: 57557J")
    assert not detectar_pdf("Demonstrativo de Comissão da Suhai")


def test_detectar_html():
    assert detectar_html("<td>Analítico dos Pagamentos de Comissões</td> Susep Favorecida:")
    assert not detectar_html("<html>outra coisa qualquer</html>")


def test_linhas_producao_ignora_debito_credito_sem_apolice():
    linhas_tabela = [
        ["Histórico", "Marca", "Suc.", "Ramo", "Apl/Prop.", "Fat/Eds", "Parc.", "Carne", "Data", "Ordem", "Prêmio", "Taxa", "Comissão", "Tipo"],
        ["AUDIT CONSULT AUDITORIA", "Porto", "59", "929", "501444", "1042476", "1", "0", "2026-08-07", "", "47,97", "25,00", "11,99", "45 - COMISSAO FRACIONADA"],
        ["CUSTO MANUT. ONCORRETOR 2 DOMINIOS-JULHO/2026", "-105,00", "100,00", "-105,00", "113 - ONCORRETOR"],
        ["Total Comissão Bruta - Susep Produção: 57557J", None, None, None, None, None, None, None, None, "785,51", None, None, ""],
    ]
    linhas = _linhas_producao(linhas_tabela)
    assert len(linhas) == 1
    assert linhas[0].cliente == "AUDIT CONSULT AUDITORIA"
    assert linhas[0].apolice == "501444"
    assert linhas[0].endosso == "1042476"
    assert linhas[0].valor_comissao == 11.99


def test_linhas_producao_agenciamento_sem_cliente_e_sem_marca():
    linhas_tabela = [
        ["Histórico", "Suc.", "Ramo", "Apl/Prop.", "Fat/Eds", "Parc.", "Carne", "Data", "Ordem", "Prêmio", "Taxa", "Comissão", "Tipo"],
        ["Agenciamento Sub: 123 Compet: 2026-07", "59", "929", "999888", "111222", "1", "0", "2026-08-07", "", "10,00", "20,00", "2,00", "44-AGENCIAMENTO"],
    ]
    linhas = _linhas_producao(linhas_tabela)
    assert len(linhas) == 1
    assert linhas[0].cliente == ""
    assert linhas[0].apolice == "999888"
    assert linhas[0].endosso == "111222"
