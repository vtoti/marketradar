"""Bootstrap de path + helpers compartilhados entre as páginas Streamlit."""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto (onde ficam config.py e marketradar/) esteja
# no sys.path, independente de onde o streamlit for iniciado.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import config  # noqa: E402

MARKETPLACES = {"Mercado Livre": "mercadolivre", "Shopee": "shopee"}

# ---------------------------------------------------------------- design ---
# Paleta validada (CVD/contraste) — polos diverging p/ finanças + neutros.
PALETTE = {
    "pos": "#059669",      # emerald  — lucro / positivo
    "neg": "#DC2626",      # red      — prejuízo / negativo
    "warn": "#D97706",     # amber    — atenção
    "info": "#2563EB",     # blue     — informativo
    "neutro": "#334155",   # slate    — totais (waterfall)
    "ink": "#0F172A", "ink2": "#475569", "ink3": "#64748B",
    "line": "#E2E8F0", "card": "#FFFFFF", "bg": "#F8FAFC",
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
#MainMenu, footer, .stAppDeployButton, [data-testid="stToolbar"] {{ display: none !important; }}
.block-container {{ padding-top: 4.5rem; max-width: 1240px; }}

/* hero da página */
.pr-hero {{ display:flex; align-items:center; justify-content:space-between;
  gap:16px; flex-wrap:wrap; margin-bottom:2px; }}
.pr-hero h1 {{ font-size:1.7rem; font-weight:800; letter-spacing:-.03em;
  color:{PALETTE['ink']}; margin:0; padding:0; }}
.pr-hero .sub {{ color:{PALETTE['ink3']}; font-size:.9rem; margin-top:2px; }}
.pr-chip {{ display:inline-flex; align-items:center; gap:7px; padding:6px 14px;
  border-radius:999px; font-size:.8rem; font-weight:600; border:1px solid; }}
.pr-chip .dot {{ width:8px; height:8px; border-radius:50%; }}

/* cartões de KPI */
.pr-kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(168px,1fr));
  gap:12px; margin:14px 0 6px; }}
.pr-kpi {{ background:{PALETTE['card']}; border:1px solid {PALETTE['line']};
  border-radius:14px; padding:14px 16px 12px; position:relative; overflow:hidden;
  box-shadow:0 1px 2px rgba(15,23,42,.04); }}
.pr-kpi::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; }}
.pr-kpi .l {{ font-size:.68rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; color:{PALETTE['ink3']}; }}
.pr-kpi .v {{ font-size:1.55rem; font-weight:800; letter-spacing:-.02em;
  color:{PALETTE['ink']}; font-variant-numeric:tabular-nums; line-height:1.25; }}
.pr-kpi .s {{ font-size:.74rem; color:{PALETTE['ink3']}; }}
.pr-kpi.ok::before   {{ background:{PALETTE['pos']}; }}
.pr-kpi.ok .v        {{ color:{PALETTE['pos']}; }}
.pr-kpi.bad::before  {{ background:{PALETTE['neg']}; }}
.pr-kpi.bad .v       {{ color:{PALETTE['neg']}; }}
.pr-kpi.warn::before {{ background:{PALETTE['warn']}; }}
.pr-kpi.info::before {{ background:{PALETTE['info']}; }}
.pr-kpi.neutral::before {{ background:{PALETTE['line']}; }}

/* abas */
.stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid {PALETTE['line']}; }}
.stTabs [data-baseweb="tab"] {{ font-weight:600; font-size:.88rem;
  padding:10px 16px; color:{PALETTE['ink3']}; }}
.stTabs [aria-selected="true"] {{ color:{PALETTE['ink']} !important; }}

/* botões e inputs mais suaves */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {{
  border-radius:10px; font-weight:600; }}
[data-testid="stForm"] {{ border:1px solid {PALETTE['line']}; border-radius:14px;
  background:{PALETTE['card']}; }}
[data-testid="stExpander"] {{ border:1px solid {PALETTE['line']}; border-radius:14px;
  background:{PALETTE['card']}; }}
[data-testid="stDataFrame"] {{ border:1px solid {PALETTE['line']}; border-radius:12px; }}
hr {{ margin:1.2rem 0; }}
</style>"""


def inject_css():
    """Aplica o design system (chamar depois de st.set_page_config)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(titulo: str, subtitulo: str, chip: tuple[str, str] | None = None):
    """Cabeçalho com título e chip de status. chip = (texto, tom ok|warn|bad)."""
    tons = {"ok": PALETTE["pos"], "warn": PALETTE["warn"], "bad": PALETTE["neg"]}
    chip_html = ""
    if chip:
        cor = tons.get(chip[1], PALETTE["ink3"])
        chip_html = (f'<span class="pr-chip" style="color:{cor};'
                     f'border-color:{cor}33;background:{cor}0d">'
                     f'<span class="dot" style="background:{cor}"></span>'
                     f'{chip[0]}</span>')
    st.markdown(
        f'<div class="pr-hero"><div><h1>{titulo}</h1>'
        f'<div class="sub">{subtitulo}</div></div>{chip_html}</div>',
        unsafe_allow_html=True)


def kpi_row(itens: list[dict]):
    """Cartões de KPI. item = {label, value, sub?, tone: ok|bad|warn|info|neutral}."""
    cards = "".join(
        f'<div class="pr-kpi {i.get("tone", "neutral")}">'
        f'<div class="l">{i["label"]}</div><div class="v">{i["value"]}</div>'
        f'<div class="s">{i.get("sub", "&nbsp;")}</div></div>'
        for i in itens)
    st.markdown(f'<div class="pr-kpis">{cards}</div>', unsafe_allow_html=True)


STATUS_EMOJI = {"saudável": "🟢 saudável", "apertado": "🟡 apertado",
                "no limite": "🟠 no limite", "prejuízo": "🔴 prejuízo"}


def status_rotulo(status: str) -> str:
    """Status com indicador visual (nunca só cor)."""
    return STATUS_EMOJI.get(status, status)


def cor_valor(v) -> str:
    """CSS p/ colorir valores monetários por sinal (uso com pandas Styler)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v < 0:
        return f"color:{PALETTE['neg']};font-weight:600"
    return f"color:{PALETTE['pos']};font-weight:600" if v > 0 else ""


def waterfall(etapas: list[tuple[str, float, str]], height: int = 300):
    """Cascata financeira. etapas = [(rótulo, valor, 'absolute'|'relative'|'total')].

    Entradas em emerald, saídas em vermelho, totais em slate (neutro) — polos
    validados p/ daltonismo; valores sempre rotulados (nunca só cor).
    """
    import plotly.graph_objects as go
    # rótulo dos totais = acumulado até ali (o y de entrada deles é ignorado)
    rotulos, acum = [], 0.0
    for _, v, m in etapas:
        acum = v if m == "absolute" else (acum if m == "total" else acum + v)
        rotulos.append(brl(acum) if m == "total" else brl(v))
    fig = go.Figure(go.Waterfall(
        orientation="v",
        x=[e[0] for e in etapas],
        y=[e[1] for e in etapas],
        measure=[e[2] for e in etapas],
        text=rotulos,
        textposition="outside",
        textfont=dict(size=12, family="Inter"),
        increasing=dict(marker=dict(color=PALETTE["pos"])),
        decreasing=dict(marker=dict(color=PALETTE["neg"])),
        totals=dict(marker=dict(color=PALETTE["neutro"])),
        connector=dict(line=dict(color=PALETTE["line"], width=1)),
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=PALETTE["ink2"], size=12),
        yaxis=dict(gridcolor=PALETTE["line"], zerolinecolor=PALETTE["line"],
                   tickprefix="R$ "),
        xaxis=dict(showgrid=False),
    )
    # folga p/ os rótulos externos não cortarem (acompanha o acumulado)
    acumulado, picos = 0.0, [0.0]
    for _, v, m in etapas:
        acumulado = v if m == "absolute" else (acumulado if m == "total"
                                               else acumulado + v)
        picos.append(acumulado)
    topo, piso = max(picos), min(picos)
    faixa = (topo - piso) or 1.0
    fig.update_yaxes(range=[piso - faixa * 0.18, topo + faixa * 0.18])
    return fig


def login_gate():
    """Bloqueia a página com senha se APP_PASSWORD estiver definido.

    Sem APP_PASSWORD (uso local), não pede login. Deve ser chamado logo após
    st.set_page_config em cada página.
    """
    if not config.APP_PASSWORD:
        return
    if st.session_state.get("_authed"):
        return
    st.title("🔒 Radar de Mercado")
    with st.form("login"):
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if senha == config.APP_PASSWORD:
                st.session_state["_authed"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()


def brl(v) -> str:
    try:
        return ("R$ " + f"{float(v):,.2f}").replace(",", "X").replace(
            ".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def num(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def marketplace_picker(default=("mercadolivre",), key="mp"):
    labels = st.multiselect(
        "Marketplaces", list(MARKETPLACES.keys()),
        default=[k for k, v in MARKETPLACES.items() if v in default], key=key)
    return [MARKETPLACES[l] for l in labels]


def show_status(status: dict):
    for mp, s in status.items():
        if s["ok"]:
            st.success(f"{mp}: {s['anuncios']} anúncios coletados.")
        else:
            st.warning(f"{mp}: falha na coleta — {s['erro']}")


def listings_table(df: pd.DataFrame):
    cols = ["title", "price", "sold_quantity", "seller_name", "rating",
            "free_shipping", "marketplace", "permalink"]
    view = df[[c for c in cols if c in df.columns]].copy()
    view = view.rename(columns={
        "title": "Anúncio", "price": "Preço", "sold_quantity": "Vendas",
        "seller_name": "Vendedor", "rating": "Nota", "free_shipping": "Frete grátis",
        "marketplace": "Marketplace", "permalink": "Link"})
    st.dataframe(
        view, use_container_width=True, hide_index=True,
        column_config={
            "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
            "Link": st.column_config.LinkColumn("Link", display_text="abrir"),
        })
