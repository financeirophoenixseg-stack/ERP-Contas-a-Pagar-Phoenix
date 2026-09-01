"""Ponto de entrada do app (chamado por `streamlit run Dashboard.py`) — só
define a navegação agrupada em seções (Principal / Financeiro / Análise) e
delega pra página escolhida. O conteúdo de cada tela mora em `telas/` —
a pasta NÃO pode se chamar `pages/`: o Streamlit ativa o modo antigo de
auto-descoberta de páginas assim que existe uma pasta com esse nome ao
lado do script de entrada, o que conflita com o st.navigation() explícito
usado aqui."""

import streamlit as st

pg = st.navigation(
    {
        "Principal": [
            st.Page("telas/0_Dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
            st.Page("telas/3_Importar_OFX.py", title="Importar OFX", icon=":material/upload_file:"),
            st.Page("telas/4_Importar_Comissao.py", title="Importar Comissão", icon=":material/receipt_long:"),
            st.Page("telas/5_Classificar_Lancamentos.py", title="Classificar Lançamentos", icon=":material/sell:"),
        ],
        "Financeiro": [
            st.Page(
                "telas/6_Contas_a_Pagar_e_Receber.py",
                title="Contas a Pagar e Receber",
                icon=":material/account_balance_wallet:",
            ),
            st.Page("telas/7_Pesquisa_Cliente.py", title="Pesquisa Cliente", icon=":material/person_search:"),
            st.Page("telas/8_Alertas.py", title="Alertas", icon=":material/notifications:"),
        ],
        "Análise": [
            st.Page("telas/9_DRE_e_Balanco.py", title="DRE e Balanço", icon=":material/balance:"),
            st.Page("telas/10_Relatorios.py", title="Relatórios", icon=":material/bar_chart:"),
            st.Page("telas/11_Configuracoes.py", title="Configurações", icon=":material/settings:"),
        ],
    }
)
pg.run()
