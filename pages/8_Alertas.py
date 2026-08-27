from datetime import date

import streamlit as st

from db import get_client

st.set_page_config(page_title="Alertas", layout="wide")
st.title("Alertas")
st.caption("Auditoria (ex.: comissão em conta de outra empresa) e lançamentos vencidos.")

try:
    client = get_client()
except RuntimeError as e:
    st.error(str(e))
    st.stop()

st.subheader("Alertas de auditoria")
alertas = (
    client.table("auditoria_alertas")
    .select("id, tipo, descricao, created_at, resolvido")
    .order("resolvido")
    .order("created_at", desc=True)
    .execute()
    .data
    or []
)
nao_resolvidos = [a for a in alertas if not a["resolvido"]]

if not alertas:
    st.info("Nenhum alerta de auditoria registrado.")
else:
    for a in alertas:
        icone = "✅" if a["resolvido"] else "⚠️"
        with st.expander(f"{icone} {a['created_at'][:10]} — {a['tipo']} — {a['descricao'][:80]}"):
            st.write(a["descricao"])
            if not a["resolvido"] and st.button("Marcar como resolvido", key=f"resolver_{a['id']}"):
                client.table("auditoria_alertas").update({"resolvido": True}).eq("id", a["id"]).execute()
                st.success("Marcado como resolvido.")
                st.rerun()

st.divider()
st.header("Contas atrasadas")
hoje_data = date.today()
hoje = hoje_data.isoformat()
vencidos = (
    client.table("lancamentos_previstos")
    .select("tipo, descricao, valor, data_vencimento, empresas(nome), clientes(nome), fornecedores(nome)")
    .eq("status", "previsto")
    .lt("data_vencimento", hoje)
    .order("data_vencimento")
    .execute()
    .data
    or []
)


def _linha_atrasada(v: dict) -> dict:
    dias = (hoje_data - date.fromisoformat(v["data_vencimento"])).days
    terceiro = (v.get("clientes") or {}).get("nome") or (v.get("fornecedores") or {}).get("nome") or "-"
    return {
        "Vencimento": v["data_vencimento"],
        "Dias em atraso": dias,
        "Empresa": (v.get("empresas") or {}).get("nome"),
        "Cliente/Fornecedor": terceiro,
        "Descrição": v["descricao"],
        "Valor": v["valor"],
    }


atrasadas_pagar = [_linha_atrasada(v) for v in vencidos if v["tipo"] == "pagar"]
atrasadas_receber = [_linha_atrasada(v) for v in vencidos if v["tipo"] == "receber"]

col1, col2 = st.columns(2)
col1.metric("Total atrasado a pagar", f"R$ {sum(l['Valor'] for l in atrasadas_pagar):,.2f}", f"{len(atrasadas_pagar)} conta(s)")
col2.metric("Total atrasado a receber", f"R$ {sum(l['Valor'] for l in atrasadas_receber):,.2f}", f"{len(atrasadas_receber)} conta(s)")

st.subheader("A pagar — atrasadas")
if atrasadas_pagar:
    st.dataframe(atrasadas_pagar, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma conta a pagar atrasada.")

st.subheader("A receber — atrasadas")
if atrasadas_receber:
    st.dataframe(atrasadas_receber, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma conta a receber atrasada.")

if vencidos:
    st.caption("Resolva em **Contas a Pagar e Receber** (marcar como pago ou cancelar).")
