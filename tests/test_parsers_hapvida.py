import csv
import os
import uuid

from parsers.hapvida import _col, _to_float_br, detectar_csv, parse

HEADER = [
    "CD FILIAL", "FILIAL", "CD COMISSIONADO", "NM COMISSIONADO", "OBRIGAÇÃO",
    "VENCIMENTO", "DT PAGAMENTO", "CD ORIGEM", "CD EMPRESA", "EMPRESA",
    "VL COMISSÃO", "BAIXA_PARCIAL", "CD USUARIO", "NM USUARIO", "DT. CADAST.",
    "DT.CAD.EMP.", "PARCELA", "VL.BASE SAÚDE", "VL.LIQUIDO", "VL.BASE ODONTO",
    "VL.LIQUIDO", "%", "VL COMISSAO", "VL FIXO/VIDA", "VL DESC", "VL ADIC",
    "VL RECEBER", "VENDEDOR", "REPIQUE", "REAGENCIAMENTO",
]


def _linha(**over):
    base = {
        "CD FILIAL": '="215"', "FILIAL": "MOGI DAS CRUZES - NDI SP",
        "CD COMISSIONADO": '="08LH"', "NM COMISSIONADO": "PHOENIX I C E A CORRETAGEM SEGUROS",
        "OBRIGAÇÃO": "3434089386", "VENCIMENTO": "05/08/2026", "DT PAGAMENTO": "06/08/2026",
        "CD ORIGEM": '="97017423"', "CD EMPRESA": '="1Q57U"', "EMPRESA": "NEWFIX INDUSTRIA E COMERCIO LTDA",
        "VL COMISSÃO": "6595,31", "BAIXA_PARCIAL": "N", "CD USUARIO": '="1Q57U001061003"',
        "NM USUARIO": "ABEL SOARES DE AZEVEDO", "DT. CADAST.": "01/08/26", "DT.CAD.EMP.": "01/06/19",
        "PARCELA": "1", "VL.BASE SAÚDE": "260,98", "VL.LIQUIDO": "243,62", "VL.BASE ODONTO": "0",
        "%": "5", "VL COMISSAO": "12,1812415", "VL FIXO/VIDA": "0", "VL DESC": "0", "VL ADIC": "0",
        "VL RECEBER": "12,1812415", "VENDEDOR": "KELLY CRISTINA SILVA", "REPIQUE": "N", "REAGENCIAMENTO": "N",
    }
    base.update(over)
    return [base[h] if h != "VL.LIQUIDO" else base["VL.LIQUIDO"] for h in HEADER]


def _escrever_csv(linhas):
    caminho = os.path.join(os.path.dirname(__file__), f"_scratch_hapvida_{uuid.uuid4().hex}.csv")
    with open(caminho, "w", encoding="cp1252", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(HEADER)
        writer.writerows(linhas)
    return caminho


def test_detectar_csv():
    assert detectar_csv(HEADER)
    assert not detectar_csv(["Cliente", "Apólice-Endosso\\Proposta"])


def test_to_float_br():
    assert _to_float_br("12,1812415") == 12.1812415
    assert _to_float_br("6.595,31") == 6595.31
    assert _to_float_br("") == 0.0


def test_col_nao_confunde_vl_comissao_com_vl_comissao_do_lote():
    # bug real: 'VL COMISSÃO' (lote) e 'VL COMISSAO' (linha) só diferem no acento
    assert HEADER[_col(HEADER, "VL COMISSAO")] == "VL COMISSAO"
    assert HEADER[_col(HEADER, "VL COMISSÃO")] == "VL COMISSÃO"


def test_parse_agrupa_por_cliente_e_soma():
    linhas = [
        _linha(NM_USUARIO="BENEF 1"),
        _linha(**{"NM USUARIO": "BENEF 2", "VL COMISSAO": "10,00"}),
        _linha(**{"EMPRESA": "OUTRA EMPRESA LTDA", "VL COMISSÃO": "219,26", "VL COMISSAO": "219,26"}),
    ]
    caminho = _escrever_csv(linhas)
    try:
        lote = parse([caminho])
    finally:
        os.remove(caminho)

    assert lote.corretor == "PHOENIX I C E A CORRETAGEM SEGUROS"
    assert lote.codigo_comissionado == "08LH"
    assert lote.data_pagamento == "2026-08-06"
    assert len(lote.linhas) == 2
    newfix = next(l for l in lote.linhas if l.cliente == "NEWFIX INDUSTRIA E COMERCIO LTDA")
    assert newfix.parcela == "2"
    assert round(newfix.valor_comissao, 2) == 22.18  # 12.18 + 10.00
    assert round(lote.valor_bruto, 2) == round(22.18 + 219.26, 2)


def test_parse_repique_vira_categoria_vitalicio():
    linhas = [_linha(REPIQUE="S")]
    caminho = _escrever_csv(linhas)
    try:
        lote = parse([caminho])
    finally:
        os.remove(caminho)
    assert lote.linhas[0].categoria_sugerida == "vitalicio"


def test_parse_reagenciamento_vira_categoria_agenciamento():
    linhas = [_linha(REAGENCIAMENTO="S")]
    caminho = _escrever_csv(linhas)
    try:
        lote = parse([caminho])
    finally:
        os.remove(caminho)
    assert lote.linhas[0].categoria_sugerida == "agenciamento"


def test_parse_sem_flags_categoria_none():
    linhas = [_linha()]
    caminho = _escrever_csv(linhas)
    try:
        lote = parse([caminho])
    finally:
        os.remove(caminho)
    assert lote.linhas[0].categoria_sugerida is None
