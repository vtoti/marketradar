"""Pesquisa de Mercado — análise de um termo/nicho."""
import _shared  # noqa: F401
from _shared import (brl, num, marketplace_picker, show_status, listings_table)

import plotly.express as px
import streamlit as st

from marketradar.service import run_search
from marketradar.analysis import metrics

st.set_page_config(page_title="Pesquisa de Mercado", page_icon="🔎", layout="wide")
_shared.login_gate()
st.title("🔎 Pesquisa de Mercado")
st.caption("Analise um nicho: preços, concorrência, líderes e faturamento estimado.")

with st.form("busca"):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        query = st.text_input("Termo de busca", placeholder="ex: fone bluetooth")
    with c2:
        mps = marketplace_picker(default=("mercadolivre",))
    with c3:
        limit = st.number_input("Nº de anúncios", 10, 200, 50, step=10)
    go = st.form_submit_button("Analisar mercado", type="primary")

if go and query and mps:
    with st.spinner("Coletando anúncios..."):
        df, status = run_search(query, mps, limit=int(limit))
    show_status(status)
    st.session_state["last_df"] = df
    st.session_state["last_query"] = query

df = st.session_state.get("last_df")
if df is not None and not df.empty:
    s = metrics.market_summary(df)
    st.subheader(f"Panorama · “{st.session_state.get('last_query','')}”")

    k = st.columns(4)
    k[0].metric("Anúncios", num(s["anuncios"]))
    k[1].metric("Vendedores", num(s["vendedores"]))
    k[2].metric("Vendas acumuladas", num(s["vendas_totais"]))
    k[3].metric("Faturamento estimado", brl(s["gmv_total"]))
    k = st.columns(4)
    k[0].metric("Preço mediano", brl(s["preco_mediano"]))
    k[1].metric("Faixa de preço", f"{brl(s['preco_min'])} – {brl(s['preco_max'])}")
    k[2].metric("Frete grátis", f"{s['pct_frete_gratis']:.0f}%")
    k[3].metric("Concentração (líder)", f"{s['share_lider_pct']:.0f}%")

    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Distribuição de preços**")
        hist = metrics.price_histogram(df)
        if not hist.empty:
            st.plotly_chart(px.bar(hist, x="faixa", y="anuncios"),
                            use_container_width=True)
    with g2:
        st.markdown("**Preço x Vendas** (onde está o volume)")
        pv = metrics.price_vs_sales(df)
        if not pv.empty:
            fig = px.scatter(pv, x="price", y="sold_quantity",
                             size="gmv", hover_name="title",
                             labels={"price": "Preço", "sold_quantity": "Vendas"})
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("**🏆 Vendedores líderes** (por faturamento estimado)")
    st.dataframe(metrics.seller_ranking(df), use_container_width=True, hide_index=True,
                 column_config={"gmv": st.column_config.NumberColumn(
                     "Faturamento", format="R$ %.2f"),
                     "preco_medio": st.column_config.NumberColumn(
                         "Preço médio", format="R$ %.2f")})

    st.divider()
    st.markdown("**Todos os anúncios**")
    listings_table(df)
elif go:
    st.info("Sem resultados. Verifique o termo e a configuração dos marketplaces.")
