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
