import streamlit as st

from db import get_client

st.set_page_config(page_title="Regras de Comissão", layout="wide")
st.title("Regras de Comissão Vitalícia")
st.caption(
    "Define, por cliente, quantas das primeiras parcelas são agenciamento (comissão de "
    "entrada, % alto) — da parcela seguinte em diante, o sistema classifica como vitalícia "
    "(recorrente) e já provisiona receita futura esperada em Contas a Pagar e Receber."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

clientes = client.table("clientes").select("id, nome").order("nome").execute().data or []
if not clientes:
    st.info("Nenhum cliente cadastrado ainda.")
    st.stop()
nomes_por_id = {c["id"]: c["nome"] for c in clientes}

regras = client.table("regras_classificacao_comissao").select("*").execute().data or []
regra_por_cliente = {r["cliente_id"]: r for r in regras}

st.subheader("Cadastrar / atualizar regra")
cliente_id = st.selectbox("Cliente", options=list(nomes_por_id.keys()), format_func=lambda i: nomes_por_id[i])
existente = regra_por_cliente.get(cliente_id)

col1, col2 = st.columns(2)
parcelas_agenciamento = col1.number_input(
    "Quantas primeiras parcelas são agenciamento",
    min_value=0, step=1,
    value=existente["parcelas_agenciamento"] if existente else 3,
)
meses_provisionar = col2.number_input(
    "Provisionar quantos meses à frente quando for vitalício",
    min_value=1, max_value=200, step=1,
    value=existente["meses_provisionar"] if existente else 24,
    help="Saúde costuma ficar por volta de 24; vida (renovação anual) pode passar de 100.",
)
col3, col4 = st.columns(2)
percentual_agenciamento = col3.number_input(
    "% comissão no agenciamento (referência)", min_value=0.0, max_value=100.0, step=0.01,
    value=float(existente["percentual_agenciamento"]) if existente and existente.get("percentual_agenciamento") else 0.0,
)
percentual_vitalicio = col4.number_input(
    "% comissão vitalícia (referência)", min_value=0.0, max_value=100.0, step=0.01,
    value=float(existente["percentual_vitalicio"]) if existente and existente.get("percentual_vitalicio") else 0.0,
)

if st.button("Salvar regra", type="primary"):
    dados = {
        "cliente_id": cliente_id,
        "parcelas_agenciamento": int(parcelas_agenciamento),
        "percentual_agenciamento": percentual_agenciamento or None,
        "percentual_vitalicio": percentual_vitalicio or None,
        "meses_provisionar": int(meses_provisionar),
    }
    if existente:
        client.table("regras_classificacao_comissao").update(dados).eq("id", existente["id"]).execute()
    else:
        client.table("regras_classificacao_comissao").insert(dados).execute()
    st.success("Regra salva.")
    st.rerun()

st.divider()
st.subheader("Regras cadastradas")
if regras:
    st.dataframe(
        [
            {
                "Cliente": nomes_por_id.get(r["cliente_id"], "?"),
                "Parcelas agenciamento": r["parcelas_agenciamento"],
                "% agenciamento": r.get("percentual_agenciamento"),
                "% vitalício": r.get("percentual_vitalicio"),
                "Meses a provisionar": r["meses_provisionar"],
            }
            for r in regras
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Nenhuma regra cadastrada ainda.")
