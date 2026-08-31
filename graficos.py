"""Gráficos em SVG (fluxo de caixa, comissões por status) usados no
Dashboard — desenhados à mão (sem biblioteca externa) pra bater exatamente
com o visual aprovado no mockup. Sempre calculados a partir de dados reais
passados pelo chamador — este módulo só desenha, nunca busca ou inventa
valor."""

from __future__ import annotations

import math

from formatacao import moeda
from layout import _compacto


def _passo_bonito(valor_max: float) -> tuple[float, int]:
    """Escolhe um passo 'redondo' (1/2/2.5/5/10 x 10^n) e o número de
    divisões (<=5) pro eixo Y cobrir `valor_max` com marcações limpas."""
    if valor_max <= 0:
        return 10.0, 1
    exp = math.floor(math.log10(valor_max))
    base = 10 ** exp
    for mult in (1, 2, 2.5, 5, 10):
        passo = mult * base
        divisoes = math.ceil(valor_max / passo)
        if divisoes <= 5:
            return passo, divisoes
    return 10 * base, 5


def _fmt_tick(valor: float) -> str:
    if valor >= 1000:
        texto = f"{valor / 1000:g}"
        return f"{texto}k"
    return f"{valor:g}"


def grafico_fluxo_caixa(meses: list[str], receitas: list[float], despesas: list[float]) -> str:
    """Gráfico de linha (Receitas x Despesas) por mês. `meses` são os
    rótulos do eixo X (ex.: ['Mar', 'Abr', ...]), `receitas`/`despesas` os
    valores na mesma ordem. Retorna o HTML/SVG pronto pra st.markdown."""
    n = len(meses)
    if n == 0:
        return '<p style="color:#8592A8;font-size:13px;">Sem dados no período.</p>'

    valor_max = max([*receitas, *despesas, 1])
    passo, divisoes = _passo_bonito(valor_max)
    topo = passo * divisoes

    plot_left, plot_right = 40, 630
    plot_top, plot_bottom = 10, 210
    largura = plot_right - plot_left
    altura = plot_bottom - plot_top

    def xs(i: int) -> float:
        return plot_left if n == 1 else plot_left + i * (largura / (n - 1))

    def ys(v: float) -> float:
        return plot_top + (1 - (v / topo if topo else 0)) * altura

    def pontos(valores: list[float]) -> str:
        return " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(valores))

    gridlines = []
    for d in range(divisoes + 1):
        valor_tick = d * passo
        y = ys(valor_tick)
        cor_linha = "#C7CEDA" if d == 0 else "#EEF1F6"
        gridlines.append(f'<line x1="{plot_left}" y1="{y:.1f}" x2="{plot_right}" y2="{y:.1f}" stroke="{cor_linha}" stroke-width="1"/>')
        gridlines.append(f'<text x="{plot_left - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#98A2B3">{_fmt_tick(valor_tick)}</text>')

    x_labels = "".join(
        f'<text x="{xs(i):.1f}" y="{plot_bottom + 18}" text-anchor="middle" font-size="11" fill="#98A2B3">{m}</text>'
        for i, m in enumerate(meses)
    )

    despesas_area = f'M{pontos(despesas)} L{xs(n-1):.1f},{plot_bottom} L{xs(0):.1f},{plot_bottom} Z'
    receitas_area = f'M{pontos(receitas)} L{xs(n-1):.1f},{plot_bottom} L{xs(0):.1f},{plot_bottom} Z'

    ultimo_receita = ys(receitas[-1])
    ultimo_despesa = ys(despesas[-1])

    html = f"""
    <div style="display:flex;gap:18px;align-items:center;margin-bottom:6px;">
      <div style="display:flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;border-radius:50%;background:#1E5FBF;display:inline-block;"></span><span style="font-size:12px;color:#5B6B85;font-weight:600;">Receitas</span></div>
      <div style="display:flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;border-radius:50%;background:#E07B39;display:inline-block;"></span><span style="font-size:12px;color:#5B6B85;font-weight:600;">Despesas</span></div>
    </div>
    <svg viewBox="0 0 640 240" width="100%" height="240" style="display:block;font-family:'Public Sans',sans-serif;">
      {''.join(gridlines)}
      {x_labels}
      <path d="{despesas_area}" fill="#E07B39" opacity="0.10"/>
      <path d="M{pontos(despesas)}" fill="none" stroke="#E07B39" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="{receitas_area}" fill="#1E5FBF" opacity="0.10"/>
      <path d="M{pontos(receitas)}" fill="none" stroke="#1E5FBF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="{xs(n-1):.1f}" cy="{ultimo_despesa:.1f}" r="6" fill="#FFFFFF"/>
      <circle cx="{xs(n-1):.1f}" cy="{ultimo_despesa:.1f}" r="4" fill="#E07B39"/>
      <circle cx="{xs(n-1):.1f}" cy="{ultimo_receita:.1f}" r="6" fill="#FFFFFF"/>
      <circle cx="{xs(n-1):.1f}" cy="{ultimo_receita:.1f}" r="4" fill="#1E5FBF"/>
      <text x="{xs(n-1)-30:.1f}" y="{ultimo_receita-12:.1f}" text-anchor="end" font-size="12" font-weight="700" fill="#10233F" font-family="Manrope, sans-serif">{moeda(receitas[-1])}</text>
      <text x="{xs(n-1)-30:.1f}" y="{ultimo_despesa+18:.1f}" text-anchor="end" font-size="12" font-weight="700" fill="#10233F" font-family="Manrope, sans-serif">{moeda(despesas[-1])}</text>
    </svg>
    """
    return _compacto(html)


def grafico_donut_status(itens: list[tuple[str, int, str]], total_label: str = "lotes") -> str:
    """Rosca (donut) — `itens` é uma lista de (rótulo, valor, cor-hex). Ex.:
    [("Conciliadas", 18, "#0ca30c"), ("Pendentes", 5, "#fab219"), ("Divergentes", 0, "#d03b3b")].
    Cor de cada fatia já deve vir do chamador (status é sempre fixo: verde
    pra conciliada, âmbar pra pendente, vermelho pra divergente)."""
    total = sum(v for _, v, _ in itens)
    raio = 70
    circunferencia = 2 * math.pi * raio

    fatias = []
    offset_acumulado = 0.0
    if total > 0:
        for _, valor, cor in itens:
            if valor <= 0:
                continue
            comprimento = circunferencia * (valor / total)
            fatias.append(
                f'<circle cx="90" cy="90" r="{raio}" fill="none" stroke="{cor}" stroke-width="24" '
                f'stroke-dasharray="{comprimento:.2f} {circunferencia:.2f}" stroke-dashoffset="{-offset_acumulado:.2f}" '
                f'transform="rotate(-90 90 90)"/>'
            )
            offset_acumulado += comprimento

    legenda = []
    for label, valor, cor in itens:
        legenda.append(
            f"""
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="width:10px;height:10px;border-radius:50%;background:{cor};display:inline-block;flex-shrink:0;"></span>
                <span style="font-size:12.5px;color:#5B6B85;font-weight:500;flex:1;">{label}</span>
                <span style="font-size:12.5px;color:#10233F;font-weight:700;">{valor}</span>
            </div>
            """
        )

    html = f"""
    <div style="display:flex;align-items:center;justify-content:center;">
      <svg viewBox="0 0 180 180" width="152" height="152">
        <circle cx="90" cy="90" r="{raio}" fill="none" stroke="#EEF1F6" stroke-width="24"/>
        {''.join(fatias)}
        <text x="90" y="86" text-anchor="middle" font-size="26" font-weight="700" fill="#10233F" font-family="Manrope, sans-serif">{total}</text>
        <text x="90" y="106" text-anchor="middle" font-size="12" fill="#8592A8" font-family="Public Sans, sans-serif">{total_label}</text>
      </svg>
    </div>
    <div style="display:flex;flex-direction:column;gap:9px;margin-top:14px;">
      {''.join(legenda)}
    </div>
    """
    return _compacto(html)
