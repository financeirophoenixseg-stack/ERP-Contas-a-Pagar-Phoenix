import uuid
from datetime import date

import streamlit as st

from db import get_client

st.set_page_config(page_title="Anexos", layout="wide")
st.title("Anexos — Boletos e Comprovantes")
st.caption("Guarda os arquivos no Supabase Storage, ligados (opcionalmente) a uma conta a pagar/receber.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

BUCKET = "anexos"

st.subheader("Novo anexo")

lancamentos = (
    client.table("lancamentos_previstos")
    .select("id, descricao, valor, data_vencimento, tipo")
    .order("data_vencimento", desc=True)
    .limit(300)
    .execute()
    .data
    or []
)
opcoes_lancamento = {
    l["id"]: f"{l['data_vencimento']} — {l['descricao']} — R$ {l['valor']:.2f} ({l['tipo']})" for l in lancamentos
}

col1, col2 = st.columns(2)
lancamento_id = col1.selectbox(
    "Vincular a uma conta (opcional)",
    options=["(nenhuma)"] + list(opcoes_lancamento.keys()),
    format_func=lambda i: "(nenhuma)" if i == "(nenhuma)" else opcoes_lancamento[i],
)
tipo_anexo = col2.radio("Tipo", ["Boleto", "Comprovante", "Outro"], horizontal=True)

arquivo = st.file_uploader("Arquivo (PDF, imagem, etc.)")

if arquivo and st.button("Salvar anexo", type="primary"):
    hoje = date.today()
    nome_seguro = f"{uuid.uuid4().hex}_{arquivo.name}"
    caminho_storage = f"{hoje.year}/{hoje.month:02d}/{tipo_anexo.lower()}/{nome_seguro}"
    try:
        client.storage.from_(BUCKET).upload(
            caminho_storage, arquivo.getvalue(), {"content-type": arquivo.type or "application/octet-stream"}
        )
        client.table("anexos").insert(
            {
                "lancamento_previsto_id": None if lancamento_id == "(nenhuma)" else lancamento_id,
                "tipo": tipo_anexo.lower(),
                "nome_arquivo": arquivo.name,
                "storage_path": caminho_storage,
            }
        ).execute()
        st.success(f"Anexo '{arquivo.name}' salvo.")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar anexo: {e}")

st.divider()
st.subheader("Anexos guardados")

filtro_tipo = st.selectbox("Filtrar por tipo", options=["Todos", "Boleto", "Comprovante", "Outro"])

query = client.table("anexos").select(
    "id, tipo, nome_arquivo, storage_path, created_at, lancamentos_previstos(descricao, data_vencimento)"
)
if filtro_tipo != "Todos":
    query = query.eq("tipo", filtro_tipo.lower())
anexos = query.order("created_at", desc=True).execute().data or []

if not anexos:
    st.info("Nenhum anexo guardado ainda.")
else:
    for a in anexos:
        vinculo = a.get("lancamentos_previstos")
        rotulo = f"{vinculo['descricao']} ({vinculo['data_vencimento']})" if vinculo else "sem vínculo"
        with st.expander(f"📎 {a['created_at'][:10]} — {a['tipo']} — {a['nome_arquivo']} — {rotulo}"):
            try:
                conteudo = client.storage.from_(BUCKET).download(a["storage_path"])
                st.download_button(
                    "Baixar",
                    data=conteudo,
                    file_name=a["nome_arquivo"],
                    key=f"baixar_{a['id']}",
                )
            except Exception as e:
                st.error(f"Erro ao carregar arquivo: {e}")
            if st.button("Apagar", key=f"apagar_{a['id']}"):
                client.storage.from_(BUCKET).remove([a["storage_path"]])
                client.table("anexos").delete().eq("id", a["id"]).execute()
                st.success("Anexo apagado.")
                st.rerun()
