"""Descoberta de Produtos — ranqueia nichos por score de oportunidade."""
import _shared  # noqa: F401
from _shared import brl, num, marketplace_picker

import plotly.express as px
import streamlit as st

from marketradar.service import evaluate_niches
from marketradar.analysis.opportunity import rank_niches

st.set_page_config(page_title="Descoberta de Produtos", page_icon="💡", layout="wide")
_shared.login_gate()
st.title("💡 Descoberta de Produtos")
st.caption("Compare nichos e encontre onde vale entrar: alta demanda + baixa concorrência.")

with st.form("descoberta"):
    termos = st.text_area(
        "Termos/nichos a avaliar (um por linha)",
        placeholder="fone bluetooth\ngarrafa térmica\nsuporte celular carro\n"
                    "luminária led\norganizador de gaveta")
    c1, c2 = st.columns(2)
    with c1:
        mps = marketplace_picker(default=("mercadolivre",), key="mp_desc")
    with c2:
        limit = st.number_input("Anúncios por nicho", 10, 100, 40, step=10)
    go = st.form_submit_button("Avaliar oportunidades", type="primary")

if go and termos.strip() and mps:
    lista = [t.strip() for t in termos.splitlines() if t.strip()]
    prog = st.progress(0.0, "Avaliando nichos...")
    scored = []
    for i, term in enumerate(lista, 1):
        scored += evaluate_niches([term], mps, limit=int(limit))
        prog.progress(i / len(lista), f"Avaliado: {term}")
    prog.empty()
    st.session_state["scored"] = scored

scored = st.session_state.get("scored")
if scored:
    rank = rank_niches(scored)
    st.subheader("🏅 Ranking de oportunidades")
    st.dataframe(
        rank, use_container_width=True, hide_index=True,
        column_config={
            "score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"),
            "ticket_medio": st.column_config.NumberColumn("Ticket médio",
                                                          format="R$ %.2f"),
            "gmv_total": st.column_config.NumberColumn("Faturamento", format="R$ %.2f")})

    fig = px.bar(rank, x="termo", y="score", color="score",
                 color_continuous_scale="RdYlGn", range_color=(0, 100),
                 labels={"termo": "Nicho", "score": "Score de oportunidade"})
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Detalhe por nicho")
    for item in sorted(scored, key=lambda x: x["score"], reverse=True):
        with st.expander(f"{item['termo']} — {item['score']} "
                         f"({item.get('classificacao','')})"):
            comp = item.get("componentes", {})
            if comp:
                radar = px.line_polar(
                    r=list(comp.values()), theta=list(comp.keys()),
                    line_close=True, range_r=[0, 100])
                st.plotly_chart(radar, use_container_width=True)
            s = item.get("resumo", {})
            cols = st.columns(4)
            cols[0].metric("Vendas totais", num(s.get("vendas_totais", 0)))
            cols[1].metric("Vendedores", num(s.get("vendedores", 0)))
            cols[2].metric("Ticket médio", brl(s.get("ticket_medio", 0)))
            cols[3].metric("Faturamento", brl(s.get("gmv_total", 0)))
else:
    st.info("Informe alguns termos e clique em **Avaliar oportunidades**. "
            "O score premia nichos com muita venda, poucos vendedores e mercado "
            "pulverizado.")
