"""Parser do relatório de comissões da Hapvida (CSV — o HTML que acompanha
é só um resumo por cliente, tudo que precisamos já está no CSV: código do
comissionado, nome do cliente por linha, datas, valores e os sinalizadores
REPIQUE/REAGENCIAMENTO).

Diferenças em relação às outras seguradoras:
- Identifica o corretor por um código de comissionado (ex.: '08LH'), não
  CNPJ nem SUSEP.
- Cada linha já traz o nome do cliente (empresa contratante do plano)
  direto — sem precisar de apolice_clientes.
- Uma linha por BENEFICIÁRIO (pode ser centenas por cliente); agrupamos
  por (cliente, repique, reagenciamento) e somamos — senão a importação
  criaria uma movimentação por beneficiário desnecessariamente.
- REPIQUE='S' já diz que aquela comissão é vitalícia (recorrente);
  REAGENCIAMENTO='S' já diz que é agenciamento (entrada) — a seguradora
  já classifica pra gente, não precisa da regra genérica por parcela.
- Não traz IRRF/ISS/INSS por lote (fica tudo no valor bruto = líquido).
"""

import csv
import re

from parsers.base import LinhaComissao, LoteComissao


def _to_float_br(value: str) -> float:
    texto = (value or "").strip()
    if not texto:
        return 0.0
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def _parse_data_br(data: str) -> str:
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", (data or "").strip())
    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}" if match else ""


def _ler_linhas_csv(caminho: str) -> tuple[list[str], list[list[str]]]:
    with open(caminho, encoding="cp1252") as f:
        reader = csv.reader(f, delimiter=";")
        header = [h.strip() for h in next(reader)]
        linhas = [row for row in reader if row]
    return header, linhas


def detectar_csv(colunas: list[str]) -> bool:
    colunas_upper = {c.strip().upper() for c in colunas}
    return {"CD COMISSIONADO", "NM COMISSIONADO", "VENCIMENTO"} <= colunas_upper


_SEM_ACENTO = str.maketrans("ÃÁÀÂÇÕÔÓÚÍÊÉ", "AAAACOOOUIEE")


def _col(header: list[str], *opcoes: str) -> int:
    """Acha o índice de uma coluna por nome. IMPORTANTE: tenta match EXATO
    primeiro (existem colunas duplicadas que só diferem no acento, ex.:
    'VL COMISSÃO' = total do lote vs 'VL COMISSAO' = valor da linha — uma
    busca tolerante a acento por si só confundiria as duas)."""
    upper = [h.upper() for h in header]
    for opcao in opcoes:
        alvo = opcao.upper()
        if alvo in upper:
            return upper.index(alvo)
    for opcao in opcoes:
        alvo = opcao.upper().translate(_SEM_ACENTO)
        for i, h in enumerate(upper):
            if h.translate(_SEM_ACENTO) == alvo:
                return i
    raise KeyError(f"Nenhuma das colunas {opcoes} encontrada em {header}")


def parse(caminhos: list[str]) -> LoteComissao:
    caminho_csv = next(c for c in caminhos if c.lower().endswith(".csv"))
    header, linhas = _ler_linhas_csv(caminho_csv)

    idx_cd_comissionado = _col(header, "CD COMISSIONADO")
    idx_nm_comissionado = _col(header, "NM COMISSIONADO")
    idx_dt_pagamento = _col(header, "DT PAGAMENTO")
    idx_empresa = _col(header, "EMPRESA")
    idx_obrigacao = _col(header, "OBRIGAÇÃO", "OBRIGACAO")
    idx_comissao_linha = _col(header, "VL COMISSAO")
    idx_base_saude = _col(header, "VL.BASE SAÚDE", "VL.BASE SAUDE")
    idx_repique = _col(header, "REPIQUE")
    idx_reagenciamento = _col(header, "REAGENCIAMENTO")

    def _limpar(valor: str) -> str:
        # campos vêm às vezes como ="215" (formatação de texto do Excel)
        return re.sub(r'^="?|"?$', "", (valor or "").strip())

    corretor = ""
    codigo_comissionado = ""
    data_pagamento = ""
    grupos: dict[tuple, dict] = {}

    for row in linhas:
        if not corretor:
            corretor = _limpar(row[idx_nm_comissionado])
            codigo_comissionado = _limpar(row[idx_cd_comissionado])
            data_pagamento = _parse_data_br(row[idx_dt_pagamento])

        empresa = _limpar(row[idx_empresa])
        repique = _limpar(row[idx_repique]).upper()
        reagenciamento = _limpar(row[idx_reagenciamento]).upper()
        chave = (empresa, repique, reagenciamento)

        grupo = grupos.setdefault(
            chave,
            {
                "apolice": _limpar(row[idx_obrigacao]),
                "valor_comissao": 0.0,
                "valor_base": 0.0,
                "n_linhas": 0,
            },
        )
        grupo["valor_comissao"] += _to_float_br(row[idx_comissao_linha])
        grupo["valor_base"] += _to_float_br(row[idx_base_saude])
        grupo["n_linhas"] += 1

    linhas_comissao = []
    for (empresa, repique, reagenciamento), grupo in grupos.items():
        if repique == "S":
            categoria = "vitalicio"
        elif reagenciamento == "S":
            categoria = "agenciamento"
        else:
            categoria = None

        linhas_comissao.append(
            LinhaComissao(
                cliente=empresa,
                apolice=grupo["apolice"],
                endosso="",
                parcela=str(grupo["n_linhas"]),
                percentual_comissao=0.0,
                tipo_raw=f"REPIQUE={repique};REAGENCIAMENTO={reagenciamento}",
                tipo="cancelamento" if grupo["valor_comissao"] < 0 else "pagamento",
                valor_parcela=round(grupo["valor_base"], 2),
                valor_comissao=round(grupo["valor_comissao"], 2),
                categoria_sugerida=categoria,
            )
        )

    valor_bruto = round(sum(l.valor_comissao for l in linhas_comissao), 2)

    return LoteComissao(
        corretor=corretor,
        cnpj="",
        codigo_comissionado=codigo_comissionado,
        data_pagamento=data_pagamento,
        valor_bruto=valor_bruto,
        irrf=0.0,
        iss=0.0,
        inss=0.0,
        pis_cofins_csll=0.0,
        valor_liquido=valor_bruto,  # relatório não discrimina impostos por lote
        linhas=linhas_comissao,
    )
