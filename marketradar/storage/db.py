"""Armazenamento em SQLite.

Guarda snapshots de anúncios ao longo do tempo. Ter dois snapshots do mesmo
anúncio em datas diferentes permite estimar a *velocidade de vendas* (vendas
por dia), que é a base da estimativa de faturamento mensal — o mesmo princípio
usado por Nubimetric/AVantPro.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pandas as pd

import config
from marketradar.collectors.base import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marketplace TEXT, listing_id TEXT, title TEXT, query TEXT,
    price REAL, currency TEXT, sold_quantity INTEGER, available_quantity INTEGER,
    condition TEXT, seller_id TEXT, seller_name TEXT, rating REAL, reviews INTEGER,
    free_shipping INTEGER, category_id TEXT, permalink TEXT, thumbnail TEXT,
    original_price REAL, discount_pct REAL, is_bestseller INTEGER,
    is_ad INTEGER, position INTEGER,
    gmv REAL, collected_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_query ON snapshots(query, marketplace);
CREATE INDEX IF NOT EXISTS idx_listing ON snapshots(listing_id, collected_at);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT,           -- 'produto' | 'concorrente' | 'termo'
    marketplace TEXT,
    ref TEXT,            -- termo de busca, seller_id ou listing_id
    label TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    origem TEXT,         -- 'agendado' | 'manual'
    termos INTEGER,
    anuncios INTEGER,
    ok INTEGER,
    detalhe TEXT         -- JSON com status por termo/marketplace
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def save_listings(listings: list[Listing]) -> int:
    if not listings:
        return 0
    cols = ("marketplace", "listing_id", "title", "query", "price", "currency",
            "sold_quantity", "available_quantity", "condition", "seller_id",
            "seller_name", "rating", "reviews", "free_shipping", "category_id",
            "permalink", "thumbnail", "original_price", "discount_pct",
            "is_bestseller", "is_ad", "position", "gmv", "collected_at")
    bool_cols = {"free_shipping", "is_bestseller", "is_ad"}
    rows = []
    for lst in listings:
        d = lst.to_dict()
        rows.append(tuple(int(d[c]) if c in bool_cols else d[c] for c in cols))
    with connect() as conn:
        conn.executemany(
            f"INSERT INTO snapshots ({','.join(cols)}) "
            f"VALUES ({','.join('?' * len(cols))})", rows,
        )
    return len(rows)


def load_query(query: str, marketplace: str | None = None,
               latest_only: bool = True) -> pd.DataFrame:
    """Carrega os anúncios de uma busca. latest_only mantém só o snapshot mais
    recente de cada anúncio."""
    sql = "SELECT * FROM snapshots WHERE query = ?"
    params: list = [query]
    if marketplace:
        sql += " AND marketplace = ?"
        params.append(marketplace)
    with connect() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    if df.empty or not latest_only:
        return df
    df = df.sort_values("collected_at").groupby(
        ["marketplace", "listing_id"], as_index=False).last()
    return df


def list_queries() -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT query, marketplace, COUNT(DISTINCT listing_id) AS anuncios, "
            "MAX(collected_at) AS ultima_coleta "
            "FROM snapshots GROUP BY query, marketplace "
            "ORDER BY ultima_coleta DESC", conn)


def listing_history(listing_id: str) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT collected_at, price, sold_quantity, available_quantity "
            "FROM snapshots WHERE listing_id = ? ORDER BY collected_at",
            conn, params=[listing_id])


# --- watchlist ---
def add_watch(kind: str, marketplace: str, ref: str, label: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO watchlist (kind, marketplace, ref, label) VALUES (?,?,?,?)",
            (kind, marketplace, ref, label))


def get_watchlist(kind: str | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM watchlist"
    params: list = []
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    with connect() as conn:
        return pd.read_sql_query(sql + " ORDER BY created_at DESC", conn, params=params)


def remove_watch(watch_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))


# --- execuções de job (coleta em lote) ---
def save_job_run(started_at: str, finished_at: str, origem: str, termos: int,
                 anuncios: int, ok: bool, detalhe: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO job_runs (started_at, finished_at, origem, termos, "
            "anuncios, ok, detalhe) VALUES (?,?,?,?,?,?,?)",
            (started_at, finished_at, origem, termos, anuncios, int(ok), detalhe))


def list_job_runs(limit: int = 20) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT started_at, finished_at, origem, termos, anuncios, ok "
            "FROM job_runs ORDER BY id DESC LIMIT ?", conn, params=[limit])


def last_job_run() -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM job_runs ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None
