"""Aparência compartilhada entre as telas: estilo visual (CSS), ícones e
cartões de indicador (KPI), e logo da empresa no topo do menu lateral.
Chame `aplicar_logo()` logo após `st.set_page_config()` em cada página —
ela injeta o CSS global e, se uma logo já tiver sido enviada em
Configurações → Aparência, mostra ela também (via Supabase Storage). Se
não houver logo ainda, ou der qualquer erro de conexão, a tela segue
normalmente sem travar.

Paleta e tipografia seguem o mockup aprovado (Manrope nos títulos/valores,
Public Sans no texto corrido, azul #1E5FBF como cor de marca) — ver
PLANO.md, item de layout."""

from __future__ import annotations

import streamlit as st

from db import get_client

BUCKET_ASSETS = "assets"
CAMINHO_LOGO = "logo.png"


def _compacto(html: str) -> str:
    """Remove indentação de cada linha de um bloco HTML multi-linha antes de
    passar pro st.markdown — sem isso, o Markdown do Streamlit interpreta
    linhas com 4+ espaços de indentação como bloco de código literal, e o
    HTML aparece cru na tela em vez de renderizar."""
    return "".join(linha.strip() for linha in html.splitlines())

# Ícones em SVG (traço, sem preenchimento) — mesmo estilo do mockup,
# reaproveitados em cartões de indicador nas telas.
ICONES = {
    "pagar": '<path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2h-5a3 3 0 0 0 0 6h5v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    "alerta": '<path d="M4 8l6 6 3-3 7 8"/><path d="M15 19h5v-5"/>',
    "receber": '<path d="M4 16l6-6 3 3 7-8"/><path d="M15 5h5v5"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "relogio": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    "triangulo": '<path d="M12 3 2 20h20L12 3z"/><path d="M12 9v5"/><circle cx="12" cy="17" r="0.7" fill="currentColor" stroke="none"/>',
    "maleta": '<rect x="3" y="7" width="18" height="12" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "banco": '<path d="M3 21h18"/><path d="M5 21V10"/><path d="M19 21V10"/><path d="M3 10l9-6 9 6"/><path d="M9 21v-7"/><path d="M15 21v-7"/>',
    "usuarios": '<circle cx="9" cy="8" r="3"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="9" r="2.5"/><path d="M14.5 20a4.5 4.5 0 0 1 6.5-4"/>',
}

# CSS só com seletores estáveis do Streamlit (data-testid, aria-*) — evita as
# classes "st-emotion-cache-*" (hash gerado a cada build, muda de versão pra
# versão e quebraria o estilo silenciosamente).
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600;700;800&family=Public+Sans:wght@400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] { font-family: 'Public Sans', system-ui, sans-serif; }

/* Conteúdo principal: um pouco mais respiro, largura confortável de leitura */
[data-testid="stMain"] .block-container {
    padding-top: 2.5rem;
    max-width: 1240px;
}

h1, h2, h3 { font-family: 'Manrope', sans-serif; letter-spacing: -0.01em; }

/* Métricas nativas (st.metric) viram cartões — usado onde ainda não migrou
   pro cartão customizado (cartoes_kpi) */
[data-testid="stMetric"] {
    background: #F7F9FC;
    border: 1px solid #E3E8F0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
}
[data-testid="stMetricLabel"] { font-weight: 500; color: #55607A; }
[data-testid="stMetricValue"] { font-family: 'Manrope', sans-serif; }

/* Expansores (seções recolhíveis) com cara de cartão, não de caixa crua */
[data-testid="stExpander"] {
    border: 1px solid #E3E8F0 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}

/* Tabelas com cantos arredondados e borda consistente com o resto */
[data-testid="stDataFrame"] {
    border: 1px solid #E3E8F0;
    border-radius: 10px;
    overflow: hidden;
}

/* Botões e inputs com cantos levemente arredondados (padrão mais "SaaS",
   menos quadrado que o visual cru padrão do Streamlit) */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {
    border-radius: 8px;
    font-weight: 500;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 8px;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    border-radius: 8px;
}

/* Divisores mais discretos que a linha cinza padrão */
[data-testid="stDivider"] hr, hr {
    margin: 1.75rem 0;
    border-color: #E3E8F0;
}

/* Menu lateral: separa visualmente do conteúdo, destaca a página atual */
[data-testid="stSidebar"] {
    border-right: 1px solid #E3E8F0;
}
[data-testid="stSidebarNavLink"] {
    border-radius: 8px;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background-color: rgba(30, 95, 191, 0.10);
    font-weight: 600;
}

/* Cartão genérico (perfil, resumo, etc.) e cartões de indicador
   customizados (cartoes_kpi) — classes usadas via
   st.markdown(unsafe_allow_html=True) em várias telas */
.card {
    background: #FFFFFF; border: 1px solid #E7ECF3; border-radius: 14px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.kpi-grid { display: grid; gap: 16px; margin: 4px 0 4px 0; }
.kpi-card {
    background: #FFFFFF; border: 1px solid #E7ECF3; border-radius: 14px;
    padding: 16px 18px; display: flex; flex-direction: column; gap: 10px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
.kpi-icon {
    width: 32px; height: 32px; border-radius: 9px; display: flex;
    align-items: center; justify-content: center; flex-shrink: 0;
}
.kpi-label { font-size: 12.5px; font-weight: 600; color: #5B6B85; }
.kpi-value { font-family: 'Manrope', sans-serif; font-weight: 700; font-size: 21px; color: #10233F; letter-spacing: -0.01em; }
.pill { display: inline-flex; align-items: center; gap: 4px; width: fit-content; padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.pill-neutral { background: #F1F4F9; color: #5B6B85; }
.pill-red { background: rgba(208,59,59,0.12); color: #B23A3A; }
.pill-green { background: rgba(12,163,12,0.12); color: #0ca30c; }
.pill-amber { background: rgba(250,178,25,0.16); color: #96650b; }
.pill-blue { background: rgba(30,95,191,0.10); color: #1E5FBF; }

.day-head { display: flex; align-items: center; justify-content: space-between; padding: 9px 4px; margin-top: 6px; }
.day-head-label { font-size: 12px; font-weight: 700; color: #8592A8; letter-spacing: 0.03em; }
.day-head.atrasado { background: rgba(208,59,59,0.07); border-radius: 8px; padding: 9px 10px; margin: 6px 0 0 0; }
.day-head.atrasado .day-head-label { color: #B23A3A; }
.extrato-row { display: flex; align-items: center; gap: 12px; padding: 11px 4px; border-top: 1px solid #F0F2F6; }
.extrato-avatar { width: 30px; height: 30px; border-radius: 9px; background: #F1F4F9; display: flex; align-items: center; justify-content: center; color: #7C8AA0; flex-shrink: 0; }
.extrato-desc { font-size: 13.5px; font-weight: 600; color: #10233F; }
.extrato-sub { font-size: 12px; color: #8592A8; margin-top: 1px; }
.extrato-value { font-family: 'Manrope', sans-serif; font-weight: 700; font-size: 13.5px; color: #10233F; }

/* Tabela customizada (quando precisa de cor por célula, coisa que o
   st.dataframe nativo não permite) */
.tabela-custom { width: 100%; border-collapse: collapse; }
.tabela-custom th {
    font-size: 11.5px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
    color: #8592A8; padding: 0 4px 10px 4px; text-align: left;
}
.tabela-custom td { font-size: 13.5px; color: #10233F; padding: 11px 4px; border-top: 1px solid #F0F2F6; }
</style>
"""


def aplicar_logo() -> None:
    """Chamar logo após `st.set_page_config()` em cada página — aplica o CSS
    global e, se houver, a logo do sistema no menu lateral."""
    st.markdown(_CSS, unsafe_allow_html=True)
    try:
        client = get_client()
        arquivos = client.storage.from_(BUCKET_ASSETS).list()
        if any(a["name"] == CAMINHO_LOGO for a in (arquivos or [])):
            url = client.storage.from_(BUCKET_ASSETS).get_public_url(CAMINHO_LOGO)
            st.logo(url)
    except Exception:
        # sem logo configurada ainda, bucket não existe, ou erro de conexão
        # — a tela segue normalmente sem logo, isso nunca deve travar a página.
        pass


def cartoes_kpi(itens: list[dict], colunas: int | None = None) -> None:
    """Renderiza uma linha de cartões de indicador customizados (ícone +
    rótulo + valor + selo opcional), no lugar do st.metric nativo.

    Cada item em `itens` é um dict com:
      - "icone": chave de ICONES (ex.: "pagar")
      - "cor": cor do ícone/selo de fundo em hex (ex.: "#1E5FBF"); opcional,
        default azul da marca
      - "label": rótulo do cartão
      - "valor": valor já formatado (string) a mostrar em destaque
      - "pill_texto" / "pill_classe": selo opcional embaixo (ex.: "3 atrasados", "pill-red")
    """
    colunas = colunas or len(itens)
    partes = [f'<div class="kpi-grid" style="grid-template-columns:repeat({colunas}, minmax(0,1fr));">']
    for item in itens:
        cor = item.get("cor", "#1E5FBF")
        icone_svg = ICONES.get(item.get("icone", ""), ICONES["check"])
        pill_html = ""
        if item.get("pill_texto"):
            classe_pill = item.get("pill_classe", "pill-neutral")
            pill_html = f'<span class="pill {classe_pill}">{item["pill_texto"]}</span>'
        partes.append(
            f"""
            <div class="kpi-card">
                <div style="display:flex;align-items:center;gap:9px;">
                    <div class="kpi-icon" style="background:{cor}18;color:{cor};">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{icone_svg}</svg>
                    </div>
                    <span class="kpi-label">{item['label']}</span>
                </div>
                <span class="kpi-value" style="{'color:' + item['valor_cor'] + ';' if item.get('valor_cor') else ''}">{item['valor']}</span>
                {pill_html}
            </div>
            """
        )
    partes.append("</div>")
    st.markdown(_compacto("".join(partes)), unsafe_allow_html=True)
