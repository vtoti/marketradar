"""Engenharia de Preços — margem de contribuição real por produto e canal."""
import _shared  # noqa: F401
from _shared import brl

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from marketradar import pricing
from marketradar.storage import db

st.set_page_config(page_title="Engenharia de Preços", page_icon="💰", layout="wide")
_shared.login_gate()
db.init_db()

st.title("💰 Engenharia de Preços")
st.caption("Margem de contribuição real: preço − custos variáveis − impostos − "
           "taxas do canal − rateio de custos fixos.")


# ------------------------------------------------------------------ helpers
def _canais() -> list[pricing.Canal]:
    return [pricing.Canal(r["nome"], r["comissao_pct"], r["tarifa_fixa"],
                          r["frete_subsidiado"])
            for _, r in db.pr_canais().iterrows()]


def _aliquota() -> float:
    return float(db.pr_get_config("aliquota", "6"))


def _rateio() -> float:
    fixos = db.pr_fixos()
    prods = db.pr_produtos()
    total = fixos["valor_mensal"].sum() if not fixos.empty else 0.0
    volume = prods["vendas_mes"].sum() if not prods.empty else 0
    return pricing.rateio_fixo(float(total), float(volume))


aba_dash, aba_prod, aba_canais, aba_fixos, aba_calc = st.tabs(
    ["📊 Rentabilidade", "📦 Produtos", "🏪 Canais & Impostos",
     "🏢 Custos Fixos", "🧮 Calculadora"])

# ------------------------------------------------------------- rentabilidade
with aba_dash:
    prods = db.pr_produtos()
    canais_df = db.pr_canais()
    if prods.empty:
        st.info("Cadastre seus produtos na aba **📦 Produtos** para ver a "
                "rentabilidade do catálogo.")
    else:
        canal_nome = st.selectbox("Canal de análise", canais_df["nome"])
        cr = canais_df[canais_df["nome"] == canal_nome].iloc[0]
        canal = pricing.Canal(cr["nome"], cr["comissao_pct"], cr["tarifa_fixa"],
                              cr["frete_subsidiado"])
        aliq, rateio = _aliquota(), _rateio()

        linhas, fat, mc_mes, lucro_mes = [], 0.0, 0.0, 0.0
        for _, p in prods.iterrows():
            cv = pricing.custo_variavel(p["custo"], p["frete"], p["embalagem"],
                                        p["outros"])
            d = pricing.decompor(p["preco"], cv, aliq, canal, rateio)
            fat += p["preco"] * p["vendas_mes"]
            mc_mes += d.mc * p["vendas_mes"]
            lucro_mes += d.lucro * p["vendas_mes"]
            linhas.append({
                "Produto": p["nome"], "Preço": p["preco"], "Custo var.": cv,
                "Impostos": d.impostos, "Taxas canal": d.taxas_canal,
                "MC (R$)": d.mc, "MC %": d.mc_pct, "Lucro/un": d.lucro,
                "Status": pricing.classificar(d.lucro_pct)})

        k = st.columns(4)
        k[0].metric("Faturamento previsto/mês", brl(fat))
        k[1].metric("Margem de contribuição/mês", brl(mc_mes))
        k[2].metric("Lucro líquido/mês", brl(lucro_mes),
                    delta=f"{lucro_mes / fat * 100:.1f}% da receita" if fat else None)
        piores = sum(1 for l in linhas if l["Status"] == "prejuízo")
        k[3].metric("Produtos no prejuízo", piores)

        st.dataframe(
            pd.DataFrame(linhas), use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="R$ %.2f")
                           for c in ("Preço", "Custo var.", "Impostos",
                                     "Taxas canal", "MC (R$)", "Lucro/un")}
            | {"MC %": st.column_config.NumberColumn(format="%.1f%%")})

# ------------------------------------------------------------------ produtos
with aba_prod:
    st.markdown("Cadastre o custo **real** por unidade: aquisição, frete de "
                "compra, embalagem e outros variáveis.")
    prods = db.pr_produtos()
    edit = st.data_editor(
        prods.drop(columns=["id"]) if not prods.empty else pd.DataFrame(
            columns=["nome", "sku", "preco", "custo", "frete", "embalagem",
                     "outros", "vendas_mes"]),
        num_rows="dynamic", use_container_width=True, key="ed_prod",
        column_config={
            "nome": st.column_config.TextColumn("Produto", required=True),
            "sku": st.column_config.TextColumn("SKU"),
            "preco": st.column_config.NumberColumn("Preço venda", format="R$ %.2f",
                                                   min_value=0.0, required=True),
            "custo": st.column_config.NumberColumn("Custo aquisição",
                                                   format="R$ %.2f", min_value=0.0),
            "frete": st.column_config.NumberColumn("Frete compra", format="R$ %.2f",
                                                   min_value=0.0),
            "embalagem": st.column_config.NumberColumn("Embalagem", format="R$ %.2f",
                                                       min_value=0.0),
            "outros": st.column_config.NumberColumn("Outros", format="R$ %.2f",
                                                    min_value=0.0),
            "vendas_mes": st.column_config.NumberColumn("Vendas/mês", min_value=0,
                                                        step=1),
        })
    if st.button("💾 Salvar produtos", type="primary"):
        with db.connect() as conn:
            conn.execute("DELETE FROM pr_produtos")
        for _, r in edit.iterrows():
            if not str(r.get("nome") or "").strip():
                continue
            db.pr_upsert("pr_produtos", {
                "nome": str(r["nome"]).strip(), "sku": str(r.get("sku") or ""),
                "preco": float(r.get("preco") or 0),
                "custo": float(r.get("custo") or 0),
                "frete": float(r.get("frete") or 0),
                "embalagem": float(r.get("embalagem") or 0),
                "outros": float(r.get("outros") or 0),
                "vendas_mes": int(r.get("vendas_mes") or 0)})
        st.success("Produtos salvos.")
        st.rerun()

# ------------------------------------------------------------------- canais
with aba_canais:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Impostos")
        regimes = {"Simples Nacional — Anexo I (~6%)": 6.0,
                   "Simples Nacional — faixa 2 (~8%)": 8.0,
                   "Simples Nacional — faixa 3 (~11%)": 11.0,
                   "MEI (~0% por venda)": 0.0,
                   "Lucro Presumido (~13,3%)": 13.3}
        aliq_atual = _aliquota()
        aliq = st.number_input("Alíquota efetiva sobre a venda (%)",
                               0.0, 40.0, aliq_atual, 0.1)
        preset = st.selectbox("…ou use um preset", ["(manter)"] + list(regimes))
        if preset != "(manter)":
            aliq = regimes[preset]
        if st.button("💾 Salvar alíquota", type="primary"):
            db.pr_set_config("aliquota", str(aliq))
            st.success(f"Alíquota salva: {aliq:.1f}%")
            st.rerun()
    with c2:
        st.subheader("Canais de venda")
        canais_df = db.pr_canais()
        edit_c = st.data_editor(
            canais_df.drop(columns=["id"]), num_rows="dynamic",
            use_container_width=True, key="ed_canais",
            column_config={
                "nome": st.column_config.TextColumn("Canal", required=True),
                "comissao_pct": st.column_config.NumberColumn(
                    "Comissão %", format="%.2f%%", min_value=0.0, max_value=100.0),
                "tarifa_fixa": st.column_config.NumberColumn(
                    "Tarifa fixa", format="R$ %.2f", min_value=0.0),
                "frete_subsidiado": st.column_config.NumberColumn(
                    "Frete subsid.", format="R$ %.2f", min_value=0.0)})
        if st.button("💾 Salvar canais", type="primary"):
            with db.connect() as conn:
                conn.execute("DELETE FROM pr_canais")
            for _, r in edit_c.iterrows():
                if not str(r.get("nome") or "").strip():
                    continue
                db.pr_upsert("pr_canais", {
                    "nome": str(r["nome"]).strip(),
                    "comissao_pct": float(r.get("comissao_pct") or 0),
                    "tarifa_fixa": float(r.get("tarifa_fixa") or 0),
                    "frete_subsidiado": float(r.get("frete_subsidiado") or 0)})
            st.success("Canais salvos.")
            st.rerun()

# -------------------------------------------------------------------- fixos
with aba_fixos:
    st.markdown("Aluguel, pró-labore, contador, software… rateados por unidade "
                "conforme o volume mensal total dos produtos.")
    fixos = db.pr_fixos()
    edit_f = st.data_editor(
        fixos.drop(columns=["id"]) if not fixos.empty else pd.DataFrame(
            columns=["descricao", "valor_mensal"]),
        num_rows="dynamic", use_container_width=True, key="ed_fixos",
        column_config={
            "descricao": st.column_config.TextColumn("Descrição", required=True),
            "valor_mensal": st.column_config.NumberColumn(
                "Valor mensal", format="R$ %.2f", min_value=0.0)})
    if st.button("💾 Salvar custos fixos", type="primary"):
        with db.connect() as conn:
            conn.execute("DELETE FROM pr_fixos")
        for _, r in edit_f.iterrows():
            if not str(r.get("descricao") or "").strip():
                continue
            db.pr_upsert("pr_fixos", {
                "descricao": str(r["descricao"]).strip(),
                "valor_mensal": float(r.get("valor_mensal") or 0)})
        st.success("Custos fixos salvos.")
        st.rerun()

    total = fixos["valor_mensal"].sum() if not fixos.empty else 0.0
    vol = db.pr_produtos()["vendas_mes"].sum() if not db.pr_produtos().empty else 0
    m = st.columns(3)
    m[0].metric("Total fixo/mês", brl(total))
    m[1].metric("Volume mensal previsto", f"{int(vol)} un")
    m[2].metric("Rateio por unidade", brl(_rateio()))

# --------------------------------------------------------------- calculadora
with aba_calc:
    prods = db.pr_produtos()
    if prods.empty:
        st.info("Cadastre produtos primeiro (aba 📦 Produtos).")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            nome_p = st.selectbox("Produto", prods["nome"])
        p = prods[prods["nome"] == nome_p].iloc[0]
        canais_df = db.pr_canais()
        with c2:
            nome_c = st.selectbox("Canal", canais_df["nome"])
        cr = canais_df[canais_df["nome"] == nome_c].iloc[0]
        canal = pricing.Canal(cr["nome"], cr["comissao_pct"], cr["tarifa_fixa"],
                              cr["frete_subsidiado"])
        with c3:
            preco = st.number_input("Preço simulado (R$)", 0.0,
                                    value=float(p["preco"]), step=1.0)
        with c4:
            meta = st.number_input("Margem líquida desejada (%)", 0.0, 90.0,
                                   20.0, 0.5)

        cv = pricing.custo_variavel(p["custo"], p["frete"], p["embalagem"],
                                    p["outros"])
        aliq, rateio = _aliquota(), _rateio()
        d = pricing.decompor(preco, cv, aliq, canal, rateio)

        e1, e2 = st.columns([3, 2])
        with e1:
            st.subheader("Raio-X do preço")
            partes = [("Custos variáveis", d.custo_var, "#64748b"),
                      ("Impostos", d.impostos, "#b45309"),
                      ("Taxas do canal", d.taxas_canal, "#7c3aed"),
                      ("Custo fixo rateado", d.fixo_rateado, "#0369a1"),
                      ("Lucro líquido", d.lucro,
                       "#0d6b3f" if d.lucro >= 0 else "#b3261e")]
            fig = go.Figure(go.Bar(
                x=[v for _, v, _ in partes], y=[n for n, _, _ in partes],
                orientation="h", marker_color=[c for _, _, c in partes],
                text=[brl(v) for _, v, _ in partes], textposition="outside"))
            fig.update_layout(height=280, margin=dict(l=0, r=40, t=10, b=10),
                              xaxis_title=f"Preço simulado: {brl(preco)}")
            st.plotly_chart(fig, use_container_width=True)
            if d.lucro < 0:
                st.error(f"Prejuízo de {brl(-d.lucro)} por unidade neste canal.")
        with e2:
            st.subheader("Preço ideal & equilíbrio")
            ideal = pricing.preco_ideal(cv, aliq, canal, meta, rateio)
            minimo = pricing.preco_ideal(cv, aliq, canal, 0, rateio)
            st.metric(f"Preço p/ margem de {meta:.0f}%",
                      brl(ideal) if ideal else "impossível")
            st.metric("Preço mínimo (lucro zero)", brl(minimo) if minimo else "—")
            fixos_total = (db.pr_fixos()["valor_mensal"].sum()
                           if not db.pr_fixos().empty else 0.0)
            be = pricing.ponto_equilibrio(float(fixos_total), d.mc)
            st.metric("Ponto de equilíbrio",
                      f"{be:.0f} un/mês" if be else "—",
                      help="Vendas deste item, sozinho, para pagar todos os "
                           "custos fixos do mês.")

        st.subheader("Comparativo entre canais")
        comp = []
        for cn in _canais():
            dc = pricing.decompor(preco, cv, aliq, cn, rateio)
            comp.append({"Canal": cn.nome, "MC (R$)": dc.mc, "MC %": dc.mc_pct,
                         "Lucro/un": dc.lucro, "Lucro %": dc.lucro_pct,
                         "Status": pricing.classificar(dc.lucro_pct)})
        st.dataframe(
            pd.DataFrame(comp).sort_values("Lucro/un", ascending=False),
            use_container_width=True, hide_index=True,
            column_config={
                "MC (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Lucro/un": st.column_config.NumberColumn(format="R$ %.2f"),
                "MC %": st.column_config.NumberColumn(format="%.1f%%"),
                "Lucro %": st.column_config.NumberColumn(format="%.1f%%")})
