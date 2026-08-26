import streamlit as st

from db import get_client

st.set_page_config(page_title="Regras de Comissão", layout="wide")
st.title("Regras de Comissão")

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

st.header("Vitalício (Saúde/Vida)")
st.caption(
    "Define, por cliente, quantas das primeiras parcelas são agenciamento (comissão de "
    "entrada, % alto) — da parcela seguinte em diante, o sistema classifica como vitalícia "
    "(recorrente) e já provisiona receita futura esperada em Contas a Pagar e Receber."
)
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

st.divider()
st.header("Parcelamento (Auto/RE)")
st.caption(
    "Define, por apólice, o número total de parcelas esperadas. Ao chegar uma comissão de "
    "uma parcela, se ainda faltam parcelas, o sistema provisiona as restantes como receita "
    "futura (mesmo valor da última observada), atualizando sozinho quando a próxima chegar de verdade."
)

regras_parc = client.table("regras_parcelamento").select("*, clientes(nome)").execute().data or []

st.subheader("Cadastrar / atualizar regra")
col1, col2, col3 = st.columns(3)
apolice_parc = col1.text_input("Número da apólice")
cliente_parc_id = col2.selectbox(
    "Cliente (opcional, só referência)",
    options=["(nenhum)"] + list(nomes_por_id.keys()),
    format_func=lambda i: "(nenhum)" if i == "(nenhum)" else nomes_por_id[i],
)
total_parcelas = col3.number_input("Total de parcelas da apólice", min_value=1, step=1, value=12)

if st.button("Salvar regra de parcelamento", type="primary", disabled=not apolice_parc.strip()):
    dados = {
        "apolice": apolice_parc.strip(),
        "cliente_id": None if cliente_parc_id == "(nenhum)" else cliente_parc_id,
        "total_parcelas": int(total_parcelas),
    }
    existente_parc = next((r for r in regras_parc if r["apolice"] == apolice_parc.strip()), None)
    if existente_parc:
        client.table("regras_parcelamento").update(dados).eq("id", existente_parc["id"]).execute()
    else:
        client.table("regras_parcelamento").insert(dados).execute()
    st.success("Regra de parcelamento salva.")
    st.rerun()

st.divider()
st.subheader("Regras de parcelamento cadastradas")
if regras_parc:
    st.dataframe(
        [
            {
                "Apólice": r["apolice"],
                "Cliente": (r.get("clientes") or {}).get("nome", "-"),
                "Total de parcelas": r["total_parcelas"],
            }
            for r in regras_parc
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Nenhuma regra de parcelamento cadastrada ainda.")
