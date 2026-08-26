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
st.subheader("Lançamentos previstos vencidos")
hoje = date.today().isoformat()
vencidos = (
    client.table("lancamentos_previstos")
    .select("tipo, descricao, valor, data_vencimento, empresas(nome)")
    .eq("status", "previsto")
    .lt("data_vencimento", hoje)
    .order("data_vencimento")
    .execute()
    .data
    or []
)
if vencidos:
    st.dataframe(
        [
            {
                "Vencimento": v["data_vencimento"],
                "Empresa": (v.get("empresas") or {}).get("nome"),
                "Tipo": v["tipo"],
                "Descrição": v["descricao"],
                "Valor": v["valor"],
            }
            for v in vencidos
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Resolva em **Contas a Pagar e Receber** (marcar como pago ou cancelar).")
else:
    st.info("Nenhum lançamento vencido.")
