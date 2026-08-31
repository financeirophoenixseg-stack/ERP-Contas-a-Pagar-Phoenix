"""Aparência compartilhada entre as telas: logo da empresa no topo do menu
lateral (Streamlit `st.logo`), guardada no Supabase Storage e configurada
uma vez em Configurações → Aparência. Se nenhuma logo foi enviada ainda,
`aplicar_logo()` simplesmente não faz nada — não trava nenhuma tela."""

from __future__ import annotations

import streamlit as st

from db import get_client

BUCKET_ASSETS = "assets"
CAMINHO_LOGO = "logo.png"


def aplicar_logo() -> None:
    """Chamar logo após `st.set_page_config()` em cada página."""
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
