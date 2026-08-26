import hashlib

import streamlit as st

from db import get_client
from ofx_parser import decode_ofx_bytes, parse_ofx

st.set_page_config(page_title="Importar OFX", layout="wide")
st.title("Importar extrato OFX")
st.caption(
    "A empresa é identificada automaticamente pela combinação banco + agência + conta."
)

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()


@st.cache_data(ttl=30)
def carregar_contas():
    rows = (
        client.table("contas_bancarias")
        .select("id, banco, agencia, conta, empresas(nome)")
        .execute()
        .data
        or []
    )
    return {(r["banco"], r["agencia"], r["conta"]): r for r in rows}


contas_por_chave = carregar_contas()

arquivo = st.file_uploader("Selecione o arquivo .ofx", type=["ofx"])
if not arquivo:
    st.stop()

raw = arquivo.getvalue()
hash_arquivo = hashlib.sha256(raw).hexdigest()

ja_importado = (
    client.table("ofx_importacoes").select("id").eq("hash_arquivo", hash_arquivo).execute().data
)
if ja_importado:
    st.warning("Este arquivo já foi importado anteriormente. Nenhuma ação será feita.")
    st.stop()

texto = decode_ofx_bytes(raw)
transacoes = parse_ofx(texto)

if not transacoes:
    st.error("Nenhuma movimentação encontrada neste arquivo.")
    st.stop()

st.subheader(f"{len(transacoes)} movimentações encontradas")

linhas = []
sem_conta_cadastrada = set()
for t in transacoes:
    chave = (t.account.bank_id, t.account.branch_id, t.account.acct_id)
    conta = contas_por_chave.get(chave)
    empresa = conta["empresas"]["nome"] if conta and conta.get("empresas") else None
    if not conta:
        sem_conta_cadastrada.add(chave)
    linhas.append(
        {
            "Empresa": empresa or "⚠️ conta não cadastrada",
            "Banco/Agência/Conta": f"{t.account.bank_id}/{t.account.branch_id}/{t.account.acct_id}",
            "Data": t.date,
            "Descrição": t.description,
            "Valor": t.amount,
            "_conta_id": conta["id"] if conta else None,
            "_fit_id": t.fit_id,
        }
    )

if sem_conta_cadastrada:
    st.warning(
        "Contas não cadastradas encontradas no arquivo: "
        + ", ".join(f"{b}/{ag}/{c}" for b, ag, c in sem_conta_cadastrada)
        + ". Cadastre-as em **Contas Bancárias** antes de importar, para que a empresa "
        "seja identificada automaticamente."
    )

st.dataframe(
    [{k: v for k, v in linha.items() if not k.startswith("_")} for linha in linhas],
    use_container_width=True,
    hide_index=True,
)

pode_importar = all(linha["_conta_id"] for linha in linhas)
if not pode_importar:
    st.info("Cadastre as contas faltantes e reenvie o arquivo para importar.")
    st.stop()

if st.button("Confirmar importação", type="primary"):
    inseridas, duplicadas = 0, 0
    conta_ids_no_arquivo = {linha["_conta_id"] for linha in linhas}
    importacao_ids = {}
    for conta_id in conta_ids_no_arquivo:
        resp = (
            client.table("ofx_importacoes")
            .insert(
                {
                    "conta_bancaria_id": conta_id,
                    "arquivo_nome": arquivo.name,
                    "hash_arquivo": hash_arquivo,
                }
            )
            .execute()
        )
        importacao_ids[conta_id] = resp.data[0]["id"]

    for linha in linhas:
        try:
            client.table("ofx_transacoes").insert(
                {
                    "ofx_importacao_id": importacao_ids[linha["_conta_id"]],
                    "conta_bancaria_id": linha["_conta_id"],
                    "fit_id": linha["_fit_id"] or None,
                    "data": linha["Data"],
                    "valor": linha["Valor"],
                    "descricao": linha["Descrição"],
                }
            ).execute()
            inseridas += 1
        except Exception:
            duplicadas += 1  # violação do unique (conta_bancaria_id, fit_id)

    st.success(f"Importação concluída: {inseridas} novas movimentações, {duplicadas} já existiam.")
