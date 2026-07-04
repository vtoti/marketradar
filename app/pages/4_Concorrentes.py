"""Concorrentes — monitoramento de vendedores e termos ao longo do tempo."""
import _shared  # noqa: F401
from _shared import brl, num, marketplace_picker, show_status

import plotly.express as px
import streamlit as st

from marketradar.service import run_search
from marketradar.analysis import metrics
from marketradar.storage import db

st.set_page_config(page_title="Concorrentes", page_icon="🏪", layout="wide")
_shared.login_gate()
st.title("🏪 Monitoramento de Concorrentes")
st.caption("Acompanhe vendedores líderes e a evolução de preços/estoque.")

tab1, tab2 = st.tabs(["Vendedores de um nicho", "Watchlist & evolução"])

with tab1:
    with st.form("conc"):
        c1, c2 = st.columns([3, 2])
        with c1:
            query = st.text_input("Termo de busca", placeholder="ex: cafeteira")
        with c2:
            mps = marketplace_picker(default=("mercadolivre",), key="mp_conc")
        go = st.form_submit_button("Buscar concorrentes", type="primary")

    if go and query and mps:
        with st.spinner("Coletando..."):
            df, status = run_search(query, mps, limit=60)
        show_status(status)
        if not df.empty:
            rank = metrics.seller_ranking(df, top=15)
            st.markdown("**Ranking de vendedores**")
            st.dataframe(rank, use_container_width=True, hide_index=True,
                         column_config={
                             "gmv": st.column_config.NumberColumn(
                                 "Faturamento", format="R$ %.2f"),
                             "share_pct": st.column_config.ProgressColumn(
                                 "Share %", min_value=0, max_value=100, format="%.1f")})
            fig = px.pie(rank, names="seller_name", values="gmv",
                         title="Participação de mercado (faturamento estimado)")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("Adicionar vendedor à watchlist:")
            sel = st.selectbox("Vendedor", rank["seller_name"].tolist())
            if st.button("➕ Monitorar vendedor"):
                row = rank[rank["seller_name"] == sel].iloc[0]
                db.add_watch("concorrente", mps[0], str(row["seller_id"]), sel)
                st.success(f"'{sel}' adicionado à watchlist.")

with tab2:
    st.markdown("**Watchlist**")
    wl = db.get_watchlist()
    if wl.empty:
        st.info("Nenhum item monitorado ainda.")
    else:
        st.dataframe(wl[["kind", "marketplace", "label", "ref", "created_at"]],
                     use_container_width=True, hide_index=True)
        rid = st.number_input("Remover item (id)", 0, step=1)
        if st.button("Remover") and rid:
            db.remove_watch(int(rid))
            st.rerun()

    st.divider()
    st.markdown("**Evolução de um anúncio** (preço, vendas e estoque)")
    hist_q = db.list_queries()
    if not hist_q.empty:
        termo = st.selectbox("Busca", hist_q["query"].unique(), key="evo_q")
        d = db.load_query(termo)
        if not d.empty:
            opt = d[["listing_id", "title"]].drop_duplicates()
            alvo = st.selectbox("Anúncio", opt["title"].tolist())
            lid = opt[opt["title"] == alvo]["listing_id"].iloc[0]
            h = db.listing_history(lid)
            if len(h) >= 2:
                fig = px.line(h, x="collected_at", y=["price", "sold_quantity"],
                              markers=True)
                st.plotly_chart(fig, use_container_width=True)
                v = metrics.estimate_velocity(h)
                cols = st.columns(3)
                cols[0].metric("Vendas/dia", v["vendas_por_dia"])
                cols[1].metric("Vendas/mês (proj.)", v["vendas_mes"])
                cols[2].metric("Faturamento/mês", brl(v["faturamento_mes"]))
            else:
                st.info("Só há 1 snapshot deste anúncio. Rode a busca de novo em "
                        "outro dia para ver a evolução.")
