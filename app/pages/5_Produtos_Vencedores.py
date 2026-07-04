"""Produtos Vencedores — detector com critérios validados de seleção."""
import _shared  # noqa: F401
from _shared import brl, num, marketplace_picker, show_status

import pandas as pd
import plotly.express as px
import streamlit as st

from marketradar.service import run_search
from marketradar.analysis import metrics
from marketradar.analysis.winning import (
    WinningCriteria, rank_products, evaluate_product,
    demand_supply_ratio, classify_trend)
from marketradar.storage import db

st.set_page_config(page_title="Produtos Vencedores", page_icon="🏆", layout="wide")
_shared.login_gate()
st.title("🏆 Detector de Produtos Vencedores")
st.caption("Aplica critérios validados (demanda × oferta, preço, concorrência, "
           "brecha de qualidade, momentum, margem) a cada anúncio.")

# --- critérios configuráveis (limiares validados como padrão) ---
with st.sidebar:
    st.header("⚙️ Critérios")
    crit = WinningCriteria(
        min_vendas=st.number_input("Demanda mínima (vendas acum.)", 0, 100000, 100, 50),
        preco_ideal_min=st.number_input("Preço ideal — mín (R$)", 0.0, 100000.0, 50.0, 10.0),
        preco_ideal_max=st.number_input("Preço ideal — máx (R$)", 0.0, 100000.0, 150.0, 10.0),
        max_reviews_bativel=st.number_input("Máx. avaliações do concorrente", 0, 100000, 500, 50),
    )
    st.divider()
    usar_custo = st.checkbox("Tenho o custo do produto (avaliar margem)")
    custo = st.number_input("Custo do fornecedor (R$)", 0.0, step=1.0) if usar_custo else None
    st.caption("Padrões baseados em Nubimetric, Jungle Scout/Helium 10 e algoritmo do ML.")

with st.form("vencedores"):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        query = st.text_input("Termo / nicho", placeholder="ex: organizador de gaveta")
    with c2:
        mps = marketplace_picker(default=("mercadolivre",), key="mp_win")
    with c3:
        limit = st.number_input("Anúncios", 10, 200, 60, step=10)
    go = st.form_submit_button("Detectar vencedores", type="primary")

if go and query and mps:
    with st.spinner("Coletando e avaliando..."):
        df, status = run_search(query, mps, limit=int(limit))
    show_status(status)
    st.session_state["win_df"] = df
    st.session_state["win_query"] = query

df = st.session_state.get("win_df")
if df is not None and not df.empty:
    q = st.session_state.get("win_query", "")
    s = metrics.market_summary(df)

    # momentum a partir do histórico armazenado (vendas/dia normalizadas)
    momentum_map = {}
    velocities = {}
    for lid in df["listing_id"].unique():
        v = metrics.estimate_velocity(db.listing_history(lid))
        if v["vendas_por_dia"] is not None:
            velocities[lid] = v["vendas_por_dia"]
    if velocities:
        vmax = max(velocities.values()) or 1
        momentum_map = {lid: min(100, vd / vmax * 100) for lid, vd in velocities.items()}

    # --- painel do nicho ---
    trend = classify_trend(db.load_query(q, latest_only=False)) if q else \
        {"tendencia": "desconhecida", "variacao_pct": None}
    st.subheader(f"Nicho · “{q}”")
    k = st.columns(4)
    k[0].metric("Demanda × oferta", f"{demand_supply_ratio(s)} vendas/vendedor",
                help="Vendas acumuladas por vendedor. Maior = demanda menos atendida.")
    k[1].metric("Vendedores", num(s["vendedores"]))
    k[2].metric("Tendência de vendas", trend["tendencia"],
                delta=(f'{trend["variacao_pct"]}%' if trend["variacao_pct"] is not None else None))
    k[3].metric("Preço mediano", brl(s["preco_mediano"]))
    if trend["tendencia"] == "desconhecida":
        st.caption("💡 Rode a mesma busca em dias diferentes para o Radar detectar a "
                   "tendência e o momentum de cada produto.")

    # --- ranking de produtos vencedores ---
    rank = rank_products(df, crit=crit, cost=custo, momentum_map=momentum_map)
    vencedores = (rank["Score"] >= 60).sum()
    st.subheader(f"🏅 {vencedores} candidato(s) forte(s) entre {len(rank)} anúncios")

    st.dataframe(
        rank.drop(columns=["_detalhe"]), use_container_width=True, hide_index=True,
        column_config={
            "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"),
            "Link": st.column_config.LinkColumn("Link", display_text="abrir")})

    fig = px.histogram(rank, x="Score", nbins=20,
                       title="Distribuição do score de produto vencedor no nicho")
    fig.add_vline(x=60, line_color="green", annotation_text="candidato forte")
    st.plotly_chart(fig, use_container_width=True)

    # --- detalhe (checklist) dos melhores ---
    st.divider()
    st.subheader("🔍 Checklist dos melhores")
    for _, r in rank.head(8).iterrows():
        det = r["_detalhe"]
        with st.expander(f'{det["veredito"]} · {r["Score"]} — {r["Produto"]}'):
            cols = st.columns([2, 1])
            with cols[0]:
                for nome, ok, valor, meta in det["checklist"]:
                    icon = "✅" if ok else "❌"
                    st.write(f"{icon} **{nome}** — {valor}  _(meta: {meta})_")
                if det["permalink"]:
                    st.markdown(f"[Abrir anúncio]({det['permalink']})")
            with cols[1]:
                sub = det["subscores"]
                radar = px.line_polar(r=list(sub.values()), theta=list(sub.keys()),
                                      line_close=True, range_r=[0, 100])
                st.plotly_chart(radar, use_container_width=True)
elif go:
    st.info("Sem resultados. Confira o termo e as credenciais dos marketplaces.")
