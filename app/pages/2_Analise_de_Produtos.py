"""Análise de Produtos — seus produtos vs. mercado + velocidade de vendas."""
import _shared  # noqa: F401
from _shared import brl, num, marketplace_picker, show_status

import pandas as pd
import plotly.express as px
import streamlit as st

from marketradar.service import run_search
from marketradar.analysis import metrics
from marketradar.storage import db

st.set_page_config(page_title="Análise de Produtos", page_icon="📦", layout="wide")
_shared.login_gate()
st.title("📦 Análise de Produtos")
st.caption("Posicione seu produto no mercado e estime a velocidade de vendas.")

tab1, tab2 = st.tabs(["Meu produto vs. mercado", "Velocidade de vendas"])

with tab1:
    with st.form("prod"):
        c1, c2, c3 = st.columns([3, 2, 2])
        with c1:
            query = st.text_input("Produto / termo", placeholder="ex: mochila notebook")
        with c2:
            meu_preco = st.number_input("Meu preço (R$)", 0.0, step=1.0)
        with c3:
            mps = marketplace_picker(default=("mercadolivre",), key="mp_prod")
        go = st.form_submit_button("Analisar", type="primary")

    if go and query and mps:
        with st.spinner("Coletando..."):
            df, status = run_search(query, mps, limit=50)
        show_status(status)
        if not df.empty:
            s = metrics.market_summary(df)
            price = df["price"].replace(0, pd.NA).dropna()
            posicao = (price < meu_preco).mean() * 100 if meu_preco else None

            k = st.columns(4)
            k[0].metric("Preço mediano do mercado", brl(s["preco_mediano"]))
            k[1].metric("Seu preço", brl(meu_preco) if meu_preco else "—")
            if posicao is not None:
                k[2].metric("Mais barato que você", f"{posicao:.0f}% dos anúncios")
                delta = meu_preco - s["preco_mediano"]
                k[3].metric("vs. mediana", brl(delta),
                            delta=f"{'acima' if delta>0 else 'abaixo'}")

            fig = px.histogram(price, nbins=20, labels={"value": "Preço"})
            if meu_preco:
                fig.add_vline(x=meu_preco, line_color="red",
                              annotation_text="Seu preço")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**Concorrentes diretos** (ordenados por vendas)")
            comp = df.sort_values("sold_quantity", ascending=False)[
                ["title", "price", "sold_quantity", "seller_name", "rating",
                 "permalink"]].head(20)
            st.dataframe(comp, use_container_width=True, hide_index=True,
                         column_config={
                             "price": st.column_config.NumberColumn(
                                 "Preço", format="R$ %.2f"),
                             "permalink": st.column_config.LinkColumn(
                                 "Link", display_text="abrir")})

with tab2:
    st.markdown("Estimativa de **vendas/dia** e **faturamento mensal** a partir de "
                "múltiplos snapshots do mesmo anúncio (rode buscas em dias diferentes).")
    hist_q = db.list_queries()
    if hist_q.empty:
        st.info("Ainda não há coletas. Rode buscas na Pesquisa de Mercado primeiro.")
    else:
        termo = st.selectbox("Busca coletada", hist_q["query"].unique())
        d = db.load_query(termo)
        if not d.empty:
            rows = []
            for lid, title in d[["listing_id", "title"]].drop_duplicates().values:
                v = metrics.estimate_velocity(db.listing_history(lid))
                if v["vendas_por_dia"] is not None:
                    rows.append({"Anúncio": title[:60],
                                 "Vendas/dia": v["vendas_por_dia"],
                                 "Vendas/mês (proj.)": v["vendas_mes"],
                                 "Faturamento/mês (proj.)": v["faturamento_mes"],
                                 "Período (dias)": v["periodo_dias"]})
            if rows:
                res = pd.DataFrame(rows).sort_values(
                    "Faturamento/mês (proj.)", ascending=False)
                st.dataframe(res, use_container_width=True, hide_index=True,
                             column_config={"Faturamento/mês (proj.)":
                                 st.column_config.NumberColumn(format="R$ %.2f")})
                st.metric("Faturamento mensal estimado do nicho (top anúncios)",
                          brl(res["Faturamento/mês (proj.)"].sum()))
            else:
                st.warning("Ainda não há 2+ snapshots por anúncio. Rode a mesma "
                           "busca novamente amanhã para gerar a série temporal.")
