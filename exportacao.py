"""Geração de Excel e PDF do extrato de Contas a Pagar/Receber, usados pelos
botões "Exportar Excel" / "Exportar PDF" da tela. Recebem sempre uma lista de
dicts já formatados para exibição (mesmas colunas que aparecem na tela) —
nada de lógica de negócio aqui, só formatação do arquivo."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

AZUL_MARCA = colors.HexColor("#0F3E7A")


def gerar_excel(linhas: list[dict], titulo: str) -> bytes:
    """Gera um .xlsx em memória a partir das linhas (list of dict) já
    formatadas para exibição na tela."""
    buffer = BytesIO()
    df = pd.DataFrame(linhas)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=titulo[:31] or "Extrato")
        planilha = writer.sheets[titulo[:31] or "Extrato"]
        for coluna in planilha.columns:
            largura = max(len(str(c.value)) for c in coluna if c.value is not None)
            planilha.column_dimensions[coluna[0].column_letter].width = min(largura + 2, 45)
    return buffer.getvalue()


def gerar_pdf(linhas: list[dict], titulo: str) -> bytes:
    """Gera um PDF simples (tabela) em memória a partir das linhas (list of
    dict) já formatadas para exibição na tela."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(titulo, estilos["Title"]), Spacer(1, 0.5 * cm)]

    if not linhas:
        elementos.append(Paragraph("Nenhum lançamento neste filtro.", estilos["Normal"]))
    else:
        cabecalho = list(linhas[0].keys())
        dados = [cabecalho] + [[str(l.get(c, "")) for c in cabecalho] for l in linhas]
        tabela = Table(dados, repeatRows=1)
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL_MARCA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E3E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elementos.append(tabela)

    doc.build(elementos)
    return buffer.getvalue()
