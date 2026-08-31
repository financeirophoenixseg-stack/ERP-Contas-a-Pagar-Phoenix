"""Aparência compartilhada entre as telas: estilo visual (CSS) e logo da
empresa no topo do menu lateral. Chame `aplicar_logo()` logo após
`st.set_page_config()` em cada página — ela injeta o CSS global e, se uma
logo já tiver sido enviada em Configurações → Aparência, mostra ela também
(via Supabase Storage). Se não houver logo ainda, ou der qualquer erro de
conexão, a tela segue normalmente sem travar."""

from __future__ import annotations

import streamlit as st

from db import get_client

BUCKET_ASSETS = "assets"
CAMINHO_LOGO = "logo.png"

# CSS só com seletores estáveis do Streamlit (data-testid, aria-*) — evita as
# classes "st-emotion-cache-*" (hash gerado a cada build, muda de versão pra
# versão e quebraria o estilo silenciosamente).
_CSS = """
<style>
/* Conteúdo principal: um pouco mais respiro, largura confortável de leitura */
[data-testid="stMain"] .block-container {
    padding-top: 2.5rem;
    max-width: 1200px;
}

h1, h2, h3 { letter-spacing: -0.01em; }

/* Métricas viram cartões — em vez de números soltos no fundo branco */
[data-testid="stMetric"] {
    background: #F7F9FC;
    border: 1px solid #E3E8F0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
}
[data-testid="stMetricLabel"] { font-weight: 500; color: #55607A; }

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
