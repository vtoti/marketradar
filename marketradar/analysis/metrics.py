"""Métricas de mercado a partir de um conjunto de anúncios (DataFrame).

Todas as funções recebem um DataFrame com as colunas do modelo Listing
(ver storage.db) e devolvem números/DataFrames prontos para o dashboard.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def market_summary(df: pd.DataFrame) -> dict:
    """Panorama do mercado de um termo/nicho."""
    if df is None or df.empty:
        return {}
    price = df["price"].replace(0, np.nan).dropna()
    sold = df["sold_quantity"].fillna(0)
    gmv = df.get("gmv", df["price"] * sold).fillna(0)
    return {
        "anuncios": int(len(df)),
        "vendedores": int(df["seller_id"].nunique()),
        "preco_min": float(price.min()) if not price.empty else 0.0,
        "preco_mediano": float(price.median()) if not price.empty else 0.0,
        "preco_medio": float(price.mean()) if not price.empty else 0.0,
        "preco_max": float(price.max()) if not price.empty else 0.0,
        "vendas_totais": int(sold.sum()),
        "gmv_total": float(gmv.sum()),          # faturamento acumulado estimado
        "ticket_medio": float(price.mean()) if not price.empty else 0.0,
        "avaliacao_media": float(df["rating"].dropna().mean())
        if df["rating"].notna().any() else None,
        "pct_frete_gratis": float(df["free_shipping"].fillna(0).mean() * 100),
        "concentracao_hhi": seller_hhi(df),
        "share_lider_pct": top_seller_share(df),
    }


def seller_ranking(df: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """Ranking de vendedores por faturamento estimado e vendas."""
    if df.empty:
        return pd.DataFrame()
    g = df.copy()
    g["gmv"] = g.get("gmv", g["price"] * g["sold_quantity"]).fillna(0)
    agg = g.groupby(["seller_id", "seller_name"], as_index=False).agg(
        anuncios=("listing_id", "nunique"),
        vendas=("sold_quantity", "sum"),
        gmv=("gmv", "sum"),
        preco_medio=("price", "mean"),
    ).sort_values("gmv", ascending=False)
    total = agg["gmv"].sum() or 1
    agg["share_pct"] = (agg["gmv"] / total * 100).round(1)
    return agg.head(top).reset_index(drop=True)


def top_seller_share(df: pd.DataFrame) -> float:
    """Fatia de faturamento do maior vendedor (% de concentração)."""
    r = seller_ranking(df, top=1)
    return float(r["share_pct"].iloc[0]) if not r.empty else 0.0


def seller_hhi(df: pd.DataFrame) -> float:
    """Índice Herfindahl-Hirschman (0–10000). Alto = mercado concentrado."""
    if df.empty:
        return 0.0
    g = df.copy()
    g["gmv"] = g.get("gmv", g["price"] * g["sold_quantity"]).fillna(0)
    shares = g.groupby("seller_id")["gmv"].sum()
    total = shares.sum()
    if total <= 0:
        return 0.0
    return float(((shares / total * 100) ** 2).sum())


def price_histogram(df: pd.DataFrame, bins: int = 15) -> pd.DataFrame:
    price = df["price"].replace(0, np.nan).dropna()
    if price.empty:
        return pd.DataFrame(columns=["faixa", "anuncios"])
    cut = pd.cut(price, bins=bins)
    out = cut.value_counts().sort_index().reset_index()
    out.columns = ["faixa", "anuncios"]
    out["faixa"] = out["faixa"].astype(str)
    return out


def price_vs_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela para dispersão preço x vendas (identifica faixa de preço campeã)."""
    cols = ["title", "price", "sold_quantity", "seller_name", "rating", "permalink"]
    d = df[[c for c in cols if c in df.columns]].copy()
    d["gmv"] = d["price"] * d["sold_quantity"]
    return d.sort_values("gmv", ascending=False)


def estimate_velocity(history: pd.DataFrame) -> dict:
    """Estima vendas/dia e projeção mensal a partir do histórico de um anúncio.

    Precisa de pelo menos 2 snapshots em datas diferentes.
    """
    if history is None or len(history) < 2:
        return {"vendas_por_dia": None, "vendas_mes": None, "faturamento_mes": None}
    h = history.copy()
    h["collected_at"] = pd.to_datetime(h["collected_at"], utc=True, errors="coerce")
    h = h.dropna(subset=["collected_at"]).sort_values("collected_at")
    if len(h) < 2:
        return {"vendas_por_dia": None, "vendas_mes": None, "faturamento_mes": None}
    first, last = h.iloc[0], h.iloc[-1]
    days = (last["collected_at"] - first["collected_at"]).total_seconds() / 86400
    if days <= 0:
        return {"vendas_por_dia": None, "vendas_mes": None, "faturamento_mes": None}
    dsold = max(0, int(last["sold_quantity"]) - int(first["sold_quantity"]))
    per_day = dsold / days
    price = float(last["price"] or 0)
    return {
        "vendas_por_dia": round(per_day, 2),
        "vendas_mes": round(per_day * 30, 1),
        "faturamento_mes": round(per_day * 30 * price, 2),
        "periodo_dias": round(days, 1),
    }
