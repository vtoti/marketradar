"""Pedidos Bling — análise de margem pedido a pedido a partir do ERP."""
import _shared  # noqa: F401
from _shared import brl

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import config
from marketradar import bling, pricing
from marketradar.storage import db

st.set_page_config(page_title="Pedidos Bling", page_icon="🧾", layout="wide")
_shared.login_gate()
db.init_db()

st.title("🧾 Pedidos — ERP Bling")
st.caption("Cada pedido de venda passa pela engenharia de preços: receita − "
           "custo dos produtos − impostos − taxas do canal − rateio fixo.")

# ---------------------------------------------------------- OAuth callback
qp = st.query_params
if "code" in qp and "state" in qp:
    try:
        bling.exchange_code(qp["code"], qp["state"])
        st.query_params.clear()
        st.success("✅ Bling autorizado com sucesso!")
    except RuntimeError as e:
        st.query_params.clear()
        st.error(f"Falha na autorização: {e}")

# --------------------------------------------------------------- conexão
stt = bling.status()
with st.container(border=True):
    if stt["conectado"]:
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.markdown("**🟢 Conectado ao Bling** — tokens com renovação automática")
        if c2.button("Reautorizar"):
            st.markdown(f"[Autorizar no Bling]({bling.authorization_url()})")
        if c3.button("Desconectar"):
            bling.desconectar()
            st.rerun()
    elif stt["tem_credenciais"]:
        st.markdown("**🟡 Credenciais configuradas — falta autorizar**")
        st.link_button("🔗 Autorizar no Bling", bling.authorization_url(),
                       type="primary")
        st.caption("Você será redirecionado de volta para esta página.")
    else:
        st.markdown("**🔴 Bling não configurado**")
        st.markdown(
            "1. Crie um aplicativo em **developer.bling.com.br** com o link de "
            f"redirecionamento `{config.BLING_REDIRECT_URI}` e escopos de "
            "*leitura* de **Pedidos de venda** e **Produtos**.\n"
            "2. Informe as credenciais abaixo (ou defina `BLING_CLIENT_ID`/"
            "`BLING_CLIENT_SECRET` no `.env`).")
        with st.form("bling_creds"):
            cid = st.text_input("Client ID")
            sec = st.text_input("Client Secret", type="password")
            if st.form_submit_button("Salvar credenciais", type="primary"):
                if cid.strip() and sec.strip():
                    bling.save_credentials(cid, sec)
                    st.rerun()
                else:
                    st.error("Preencha os dois campos.")

# ------------------------------------------------------------ sincronizar
if stt["conectado"]:
    with st.form("sync"):
        c1, c2, c3 = st.columns([1, 1, 1])
        de = c1.date_input("De", date.today() - timedelta(days=30))
        ate = c2.date_input("Até", date.today())
        c3.markdown("&nbsp;")
        go = c3.form_submit_button("⟳ Sincronizar pedidos", type="primary")
    if go:
        if de > ate:
            st.error("Período inválido.")
        else:
            barra = st.progress(0.0, "Iniciando…")
            try:
                pedidos = bling.sync_pedidos(
                    de.isoformat(), ate.isoformat(),
                    progress=lambda i, t, etapa: barra.progress(
                        min(i / t if t else 0.0, 1.0), etapa))
                barra.empty()
                from datetime import datetime, timezone
                n = db.pr_save_pedidos(
                    pedidos, datetime.now(timezone.utc).isoformat())
                st.success(f"{n} pedidos sincronizados.")
            except RuntimeError as e:
                barra.empty()
                st.error(f"Erro na sincronização: {e}")

# ------------------------------------------------------------- análise
pedidos, synced_at = db.pr_load_pedidos()
if not pedidos:
    st.info("Nenhum pedido no cache ainda. Conecte ao Bling e sincronize um "
            "período acima.")
    st.stop()

st.divider()
canais_df = db.pr_canais()
c1, c2 = st.columns(2)
with c1:
    op = ["— nenhum (taxa zero) —"] + list(canais_df["nome"])
    salvo = db.pr_get_config("canal_padrao", "")
    padrao_nome = st.selectbox(
        "Canal padrão p/ pedidos sem taxas informadas pelo Bling", op,
        index=op.index(salvo) if salvo in op else 0)
    db.pr_set_config("canal_padrao", padrao_nome if padrao_nome != op[0] else "")
with c2:
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

receita = sum(a["receita"] for _, a in analises)
mc_t = sum(a["mc"] for _, a in analises)
lucro_t = sum(a["lucro"] for _, a in analises)
neg = sum(1 for _, a in analises if a["lucro"] < 0)
sem_custo = sum(a["itens_sem_custo"] for _, a in analises)

k = st.columns(5)
k[0].metric("Pedidos analisados", len(analises),
            delta=f"-{len(pedidos) - len(analises)} ignorados"
            if len(pedidos) != len(analises) else None, delta_color="off")
k[1].metric("Receita no período", brl(receita))
k[2].metric("Margem de contribuição", brl(mc_t),
            delta=f"{mc_t / receita * 100:.1f}% da receita" if receita else None,
            delta_color="off")
k[3].metric("Lucro líquido", brl(lucro_t),
            delta=f"{lucro_t / receita * 100:.1f}% da receita" if receita else None)
k[4].metric("Pedidos no prejuízo", neg)
if sem_custo:
    st.warning(f"⚠️ {sem_custo} itens **sem custo** — preencha o *preço de "
               "custo* no Bling ou cadastre o produto (com SKU) na página "
               "💰 Engenharia de Preços.")
if synced_at:
    st.caption(f"Última sincronização: {synced_at[:19].replace('T', ' ')} UTC")

_fmt_moeda = {c: st.column_config.NumberColumn(format="R$ %.2f")
              for c in ("Receita", "Custo prod.", "Custo", "Impostos", "Taxas",
                        "MC (R$)", "Lucro")}
_fmt_pct = {"MC %": st.column_config.NumberColumn(format="%.1f%%"),
            "Lucro %": st.column_config.NumberColumn(format="%.1f%%")}

t_ped, t_item, t_sku = st.tabs(["📄 Por pedido", "📦 Por item", "🏷️ Por SKU"])

with t_ped:
    tabela = pd.DataFrame([{
        "Pedido": f"#{p.get('numero') or p['id']}",
        "Data": p.get("data") or "",
        "SKU": ", ".join(sorted({it.get("codigo") for it in (p.get("itens") or [])
                                 if it.get("codigo")})) or "—",
        "Situação": p.get("situacao") or "—",
        "Receita": a["receita"], "Custo prod.": a["custo_prod"],
        "Impostos": a["impostos"], "Taxas": a["taxas"], "Fonte taxa": a["fonte_taxa"],
        "MC (R$)": a["mc"], "MC %": a["mc_pct"], "Lucro": a["lucro"],
        "Status": a["status"], "Itens s/ custo": a["itens_sem_custo"] or None,
    } for p, a in analises])
    st.dataframe(tabela, use_container_width=True, hide_index=True,
                 column_config=_fmt_moeda | _fmt_pct)

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
                "Status": m["status"],
                "Fonte custo": m["fonte_custo"]})
    st.dataframe(pd.DataFrame(linhas_item), use_container_width=True,
                 hide_index=True, column_config=_fmt_moeda | _fmt_pct)

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
    st.dataframe(agg, use_container_width=True, hide_index=True,
                 column_config=_fmt_moeda | _fmt_pct)

# ----------------------------------------------------------- drill-down
st.subheader("🔍 Detalhar um pedido")
opcoes = {f"#{p.get('numero') or p['id']} — {p.get('cliente') or '?'} "
          f"({brl(a['receita'])})": (p, a) for p, a in analises}
sel = st.selectbox("Pedido", list(opcoes))
p, a = opcoes[sel]
d1, d2 = st.columns([3, 2])
with d1:
    itens = pd.DataFrame([{
        "Item": it.get("descricao"), "SKU": it.get("codigo"),
        "Qtd": it.get("quantidade"), "Valor un.": it.get("valor"),
        "Custo un.": it.get("custo_unit"), "Fonte": it.get("fonte_custo"),
    } for it in a["itens"]])
    st.dataframe(itens, use_container_width=True, hide_index=True,
                 column_config={
                     "Valor un.": st.column_config.NumberColumn(format="R$ %.2f"),
                     "Custo un.": st.column_config.NumberColumn(format="R$ %.2f")})
with d2:
    st.markdown(f"""
| | |
|---|---:|
| Receita | **{brl(a['receita'])}** |
| Custo dos produtos | −{brl(a['custo_prod'])} |
| Impostos ({aliquota:.1f}%) | −{brl(a['impostos'])} |
| Taxas do canal ({a['fonte_taxa']}) | −{brl(a['taxas'])} |
| **Margem de contribuição** | **{brl(a['mc'])}** ({a['mc_pct']:.1f}%) |
| Custo fixo rateado ({a['unidades']:.0f} un × {brl(rateio)}) | −{brl(a['fixo'])} |
| **Lucro líquido** | **{brl(a['lucro'])}** ({a['lucro_pct']:.1f}%) |
""")
    st.caption(f"Status: **{a['status']}** · Frete do pedido: {brl(p.get('frete'))}")
