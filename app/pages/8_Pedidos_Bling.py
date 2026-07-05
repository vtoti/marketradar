"""Pedidos Bling — análise de margem pedido a pedido a partir do ERP."""
import _shared  # noqa: F401
from _shared import (PALETTE, brl, cor_valor, inject_css, kpi_row, page_header,
                     status_rotulo, waterfall)

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from marketradar import bling, pricing
from marketradar.storage import db

st.set_page_config(page_title="Pedidos Bling", page_icon="🧾", layout="wide")
_shared.login_gate()
inject_css()
db.init_db()

# ---------------------------------------------------------- OAuth callback
qp = st.query_params
if "code" in qp and "state" in qp:
    try:
        bling.exchange_code(qp["code"], qp["state"])
        st.query_params.clear()
        st.toast("Bling autorizado com sucesso!", icon="✅")
    except RuntimeError as e:
        st.query_params.clear()
        st.error(f"Falha na autorização: {e}")

# ------------------------------------------------------------------ header
stt = bling.status()
pedidos, synced_at = db.pr_load_pedidos()
if stt["conectado"]:
    chip = ("Conectado ao Bling", "ok")
elif stt["tem_credenciais"]:
    chip = ("Autorização pendente", "warn")
else:
    chip = ("Bling não configurado", "bad")
page_header("🧾 Pedidos — ERP Bling",
            "O lucro real de cada venda: receita − custos − impostos − taxas "
            "do canal − rateio fixo.", chip)

# --------------------------------------------------------------- conexão
if not stt["conectado"]:
    with st.container(border=True):
        if stt["tem_credenciais"]:
            st.markdown("##### Falta autorizar o acesso à sua conta")
            st.link_button("🔗 Autorizar no Bling", bling.authorization_url(),
                           type="primary")
            st.caption("Você será redirecionado de volta para esta página.")
        else:
            st.markdown("##### Conectar ao Bling")
            st.markdown(
                "1. Crie um aplicativo em **developer.bling.com.br** com o "
                f"link de redirecionamento `{config.BLING_REDIRECT_URI}` e "
                "escopos de *leitura* de **Pedidos de venda** e **Produtos** "
                "(passo a passo no `GUIA-BLING.md`).\n"
                "2. Informe as credenciais abaixo (ou defina "
                "`BLING_CLIENT_ID`/`BLING_CLIENT_SECRET` no `.env`).")
            with st.form("bling_creds", border=False):
                c1, c2 = st.columns(2)
                cid = c1.text_input("Client ID")
                sec = c2.text_input("Client Secret", type="password")
                if st.form_submit_button("Salvar credenciais", type="primary"):
                    if cid.strip() and sec.strip():
                        bling.save_credentials(cid, sec)
                        st.rerun()
                    else:
                        st.error("Preencha os dois campos.")
else:
    with st.expander("⚙️ Conexão e sincronização", expanded=not pedidos):
        with st.form("sync", border=False):
            c1, c2, c3, c4 = st.columns([1, 1, 1.2, 1])
            de = c1.date_input("De", date.today() - timedelta(days=30))
            ate = c2.date_input("Até", date.today())
            c3.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
            go_sync = c3.form_submit_button("⟳ Sincronizar pedidos",
                                            type="primary",
                                            use_container_width=True)
            c4.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
            desconectar = c4.form_submit_button("Desconectar",
                                                use_container_width=True)
        if desconectar:
            bling.desconectar()
            st.rerun()
        if go_sync:
            if de > ate:
                st.error("Período inválido.")
            else:
                barra = st.progress(0.0, "Iniciando…")
                try:
                    novos = bling.sync_pedidos(
                        de.isoformat(), ate.isoformat(),
                        progress=lambda i, t, etapa: barra.progress(
                            min(i / t if t else 0.0, 1.0), etapa))
                    barra.empty()
                    from datetime import datetime, timezone
                    n = db.pr_save_pedidos(
                        novos, datetime.now(timezone.utc).isoformat())
                    st.toast(f"{n} pedidos sincronizados.", icon="✅")
                    st.rerun()
                except RuntimeError as e:
                    barra.empty()
                    st.error(f"Erro na sincronização: {e}")

if not pedidos:
    st.info("Nenhum pedido no cache ainda. Conecte ao Bling e sincronize um "
            "período acima.", icon="📭")
    st.stop()

# ------------------------------------------------------------- parâmetros
canais_df = db.pr_canais()
f1, f2 = st.columns(2)
with f1:
    op = ["— nenhum (taxa zero) —"] + list(canais_df["nome"])
    salvo = db.pr_get_config("canal_padrao", "")
    padrao_nome = st.selectbox(
        "Canal padrão p/ pedidos sem taxas informadas pelo Bling", op,
        index=op.index(salvo) if salvo in op else 0)
    db.pr_set_config("canal_padrao", padrao_nome if padrao_nome != op[0] else "")
with f2:
    ignorar = st.text_input("Situações ignoradas (contém)", "cancelado")

canal_padrao = None
if padrao_nome != op[0]:
    cr = canais_df[canais_df["nome"] == padrao_nome].iloc[0]
    canal_padrao = pricing.Canal(cr["nome"], cr["comissao_pct"],
                                 cr["tarifa_fixa"], cr["frete_subsidiado"])

aliquota = float(db.pr_get_config("aliquota", "6"))
fixos = db.pr_fixos()
prods = db.pr_produtos()
total_fixos = float(fixos["valor_mensal"].sum()) if not fixos.empty else 0.0
volume = float(prods["vendas_mes"].sum()) if not prods.empty else 0.0
rateio = pricing.rateio_fixo(total_fixos, volume)


def _custo_local(codigo: str, descricao: str) -> float | None:
    """Resolve custo pelo cadastro local (SKU e depois nome)."""
    if prods.empty:
        return None
    if codigo:
        hit = prods[prods["sku"].str.strip().str.lower() == codigo.strip().lower()]
        if not hit.empty:
            r = hit.iloc[0]
            return pricing.custo_variavel(r["custo"], r["frete"],
                                          r["embalagem"], r["outros"])
    hit = prods[prods["nome"].str.strip().str.lower()
                == (descricao or "").strip().lower()]
    if not hit.empty:
        r = hit.iloc[0]
        return pricing.custo_variavel(r["custo"], r["frete"],
                                      r["embalagem"], r["outros"])
    return None


termos = [t.strip().lower() for t in ignorar.split(",") if t.strip()]
vivos = [p for p in pedidos
         if not any(t in (p.get("situacao") or "").lower() for t in termos)]
analises = [(p, pricing.analisar_pedido(p, aliquota, rateio, canal_padrao,
                                        _custo_local)) for p in vivos]

# ------------------------------------------------------------------- KPIs
receita = sum(a["receita"] for _, a in analises)
mc_t = sum(a["mc"] for _, a in analises)
lucro_t = sum(a["lucro"] for _, a in analises)
neg = sum(1 for _, a in analises if a["lucro"] < 0)
sem_custo = sum(a["itens_sem_custo"] for _, a in analises)

kpis = [
    {"label": "Pedidos analisados", "value": len(analises), "tone": "info",
     "sub": (f"{len(pedidos) - len(analises)} ignorados por situação"
             if len(pedidos) != len(analises) else "no período sincronizado")},
    {"label": "Receita", "value": brl(receita), "tone": "info"},
    {"label": "Margem de contribuição", "value": brl(mc_t), "tone": "neutral",
     "sub": f"{mc_t / receita * 100:.1f}% da receita" if receita else ""},
    {"label": "Lucro líquido", "value": brl(lucro_t),
     "tone": "ok" if lucro_t >= 0 else "bad",
     "sub": f"{lucro_t / receita * 100:.1f}% da receita" if receita else ""},
    {"label": "Pedidos no prejuízo", "value": neg,
     "tone": "warn" if neg else "neutral",
     "sub": "exigem atenção" if neg else "nenhum 🎉"},
]
if sem_custo:
    kpis.append({"label": "Itens sem custo", "value": sem_custo, "tone": "bad",
                 "sub": "cadastre o custo no Bling"})
kpi_row(kpis)
if synced_at:
    st.caption(f"Última sincronização: {synced_at[:19].replace('T', ' ')} UTC")

# ------------------------------------------------------------------ visões
_fmt_moeda = {c: st.column_config.NumberColumn(format="R$ %.2f")
              for c in ("Receita", "Custo prod.", "Custo", "Impostos", "Taxas",
                        "MC (R$)", "Lucro")}
_fmt_pct = {"MC %": st.column_config.NumberColumn(format="%.1f%%"),
            "Lucro %": st.column_config.NumberColumn(format="%.1f%%")}
_col_lucro = ["MC (R$)", "Lucro"]


def _tabela(df: pd.DataFrame, extra_cfg: dict | None = None):
    sty = df.style.map(cor_valor, subset=[c for c in _col_lucro
                                          if c in df.columns])
    st.dataframe(sty, use_container_width=True, hide_index=True,
                 column_config=_fmt_moeda | _fmt_pct | (extra_cfg or {}))


t_ped, t_item, t_sku, t_zoom = st.tabs(
    ["📄 Por pedido", "📦 Por item", "🏷️ Por SKU", "🔍 Raio-X do pedido"])

with t_ped:
    _tabela(pd.DataFrame([{
        "Pedido": f"#{p.get('numero') or p['id']}",
        "Data": p.get("data") or "",
        "SKU": ", ".join(sorted({it.get("codigo") for it in (p.get("itens") or [])
                                 if it.get("codigo")})) or "—",
        "Situação": p.get("situacao") or "—",
        "Receita": a["receita"], "Custo prod.": a["custo_prod"],
        "Impostos": a["impostos"], "Taxas": a["taxas"],
        "Fonte taxa": a["fonte_taxa"],
        "MC (R$)": a["mc"], "MC %": a["mc_pct"], "Lucro": a["lucro"],
        "Status": status_rotulo(a["status"]),
        "Itens s/ custo": a["itens_sem_custo"] or None,
    } for p, a in analises]))

with t_item:
    st.caption("Pedidos com mais de um produto aparecem em várias linhas — "
               "impostos e taxas rateados pela receita de cada item; custo "
               "fixo, pela quantidade.")
    linhas_item = []
    for p, a in analises:
        for m in pricing.margens_por_item(a):
            linhas_item.append({
                "Pedido": f"#{p.get('numero') or p['id']}",
                "Data": p.get("data") or "",
                "SKU": m["codigo"] or "—",
                "Item": (m["descricao"] or "")[:50],
                "Qtd": m["quantidade"],
                "Receita": m["receita"], "Custo": m["custo"],
                "Impostos": m["impostos"], "Taxas": m["taxas"],
                "MC (R$)": m["mc"], "MC %": m["mc_pct"], "Lucro": m["lucro"],
                "Status": status_rotulo(m["status"]),
                "Fonte custo": m["fonte_custo"]})
    _tabela(pd.DataFrame(linhas_item))

with t_sku:
    st.caption("Todos os pedidos do período somados por produto — o ranking "
               "do que dá (ou tira) dinheiro.")
    por_sku: dict = {}
    for _, a in analises:
        for m in pricing.margens_por_item(a):
            chave = m["codigo"] or m["descricao"] or "—"
            g = por_sku.setdefault(chave, {
                "SKU": m["codigo"] or "—", "Item": (m["descricao"] or "")[:50],
                "Pedidos": 0, "Qtd": 0.0, "Receita": 0.0, "Custo": 0.0,
                "MC (R$)": 0.0, "Lucro": 0.0})
            g["Pedidos"] += 1
            g["Qtd"] += m["quantidade"]
            g["Receita"] += m["receita"]
            g["Custo"] += m["custo"]
            g["MC (R$)"] += m["mc"]
            g["Lucro"] += m["lucro"]
    agg = pd.DataFrame(list(por_sku.values()))
    if not agg.empty:
        agg["Lucro %"] = (agg["Lucro"] / agg["Receita"].replace(0, pd.NA)
                          * 100).fillna(0.0)
        agg = agg.sort_values("Lucro", ascending=False)

        top = agg.head(15).iloc[::-1]  # horizontal: maior em cima
        fig = go.Figure(go.Bar(
            x=top["Lucro"], y=top["SKU"] + "  ", orientation="h",
            marker_color=[PALETTE["pos"] if v >= 0 else PALETTE["neg"]
                          for v in top["Lucro"]],
            text=[brl(v) for v in top["Lucro"]], textposition="outside",
            textfont=dict(size=11, family="Inter"), width=0.55,
            hovertemplate="<b>%{y}</b><br>Lucro: %{text}<extra></extra>"))
        fig.update_layout(
            title=dict(text="Lucro líquido por SKU no período",
                       font=dict(size=14, family="Inter",
                                 color=PALETTE["ink"])),
            height=max(220, 34 * len(top) + 70),
            margin=dict(l=0, r=60, t=40, b=0), showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color=PALETTE["ink2"], size=12),
            xaxis=dict(gridcolor=PALETTE["line"],
                       zerolinecolor=PALETTE["ink3"], tickprefix="R$ "),
            yaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True)
    _tabela(agg)

with t_zoom:
    opcoes = {f"#{p.get('numero') or p['id']} · {p.get('data') or ''} · "
              f"{p.get('cliente') or '?'} · {brl(a['receita'])}": (p, a)
              for p, a in analises}
    sel = st.selectbox("Escolha o pedido", list(opcoes))
    p, a = opcoes[sel]

    z1, z2 = st.columns([3, 2])
    with z1:
        st.markdown("###### Cascata do pedido — para onde vai cada real")
        st.plotly_chart(waterfall([
            ("Receita", a["receita"], "absolute"),
            ("Custo produtos", -a["custo_prod"], "relative"),
            ("Impostos", -a["impostos"], "relative"),
            (f"Taxas ({a['fonte_taxa']})", -a["taxas"], "relative"),
            ("Margem contrib.", 0, "total"),
            ("Fixo rateado", -a["fixo"], "relative"),
            ("Lucro líquido", 0, "total"),
        ], height=320), use_container_width=True)
    with z2:
        st.markdown("###### Resumo")
        kpi_row([
            {"label": "Margem de contribuição", "value": brl(a["mc"]),
             "sub": f"{a['mc_pct']:.1f}% da receita", "tone": "neutral"},
            {"label": "Lucro líquido", "value": brl(a["lucro"]),
             "sub": f"{a['lucro_pct']:.1f}% · {status_rotulo(a['status'])}",
             "tone": "ok" if a["lucro"] >= 0 else "bad"},
        ])
        st.caption(f"Frete do pedido: {brl(p.get('frete'))} · Rateio fixo: "
                   f"{a['unidades']:.0f} un × {brl(rateio)} = {brl(a['fixo'])}")

    st.markdown("###### Itens do pedido")
    _tabela(pd.DataFrame([{
        "Item": it.get("descricao"), "SKU": it.get("codigo"),
        "Qtd": it.get("quantidade"), "Valor un.": it.get("valor"),
        "Custo un.": it.get("custo_unit"),
        "Fonte do custo": it.get("fonte_custo"),
    } for it in a["itens"]]), extra_cfg={
        "Valor un.": st.column_config.NumberColumn(format="R$ %.2f"),
        "Custo un.": st.column_config.NumberColumn(format="R$ %.2f")})
