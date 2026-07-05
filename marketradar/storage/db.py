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

-- ===== Engenharia de preços (PreçoReal) =====
CREATE TABLE IF NOT EXISTS pr_produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sku TEXT DEFAULT '',
    preco REAL NOT NULL,
    custo REAL NOT NULL,        -- aquisição
    frete REAL DEFAULT 0,       -- frete de compra
    embalagem REAL DEFAULT 0,
    outros REAL DEFAULT 0,
    vendas_mes INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS pr_canais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    comissao_pct REAL DEFAULT 0,
    tarifa_fixa REAL DEFAULT 0,
    frete_subsidiado REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pr_fixos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor_mensal REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pr_config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS pr_pedidos (
    id INTEGER PRIMARY KEY,     -- id do pedido no Bling
    numero TEXT,
    data TEXT,
    cliente TEXT,
    situacao TEXT,
    loja TEXT,
    total REAL,
    frete REAL,
    desconto REAL,
    comissao REAL,              -- taxas.taxaComissao do Bling
    custo_frete REAL,           -- taxas.custoFrete do Bling
    itens_json TEXT,            -- [{codigo, descricao, quantidade, valor, custo_bling}]
    synced_at TEXT
);
"""

# canais criados na primeira execução (todos editáveis depois)
PR_CANAIS_PADRAO = [
    ("Venda direta (B2B)", 0.0, 0.0, 0.0),
    ("Mercado Livre Clássico", 12.0, 6.5, 0.0),
    ("Mercado Livre Premium", 17.0, 6.5, 0.0),
    ("Shopee", 14.0, 4.0, 0.0),
    ("Amazon", 15.0, 4.5, 0.0),
    ("Magalu", 14.5, 5.0, 0.0),
    ("Loja própria (gateway)", 4.99, 0.4, 0.0),
]


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
        # semeia canais de venda na primeira execução
        if conn.execute("SELECT COUNT(*) FROM pr_canais").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO pr_canais (nome, comissao_pct, tarifa_fixa, "
                "frete_subsidiado) VALUES (?,?,?,?)", PR_CANAIS_PADRAO)


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


# ===== Engenharia de preços (PreçoReal) =====
def _pr_table(table: str) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id", conn)


def pr_produtos() -> pd.DataFrame:
    return _pr_table("pr_produtos")


def pr_canais() -> pd.DataFrame:
    return _pr_table("pr_canais")


def pr_fixos() -> pd.DataFrame:
    return _pr_table("pr_fixos")


def pr_upsert(table: str, row: dict, row_id: int | None = None) -> None:
    """Insere (row_id=None) ou atualiza uma linha de pr_produtos/pr_canais/pr_fixos."""
    assert table in ("pr_produtos", "pr_canais", "pr_fixos"), table
    cols = list(row.keys())
    with connect() as conn:
        if row_id is None:
            conn.execute(
                f"INSERT INTO {table} ({','.join(cols)}) "
                f"VALUES ({','.join('?' * len(cols))})", list(row.values()))
        else:
            sets = ",".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE id=?",
                         [*row.values(), row_id])


def pr_delete(table: str, row_id: int) -> None:
    assert table in ("pr_produtos", "pr_canais", "pr_fixos"), table
    with connect() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))


def pr_get_config(chave: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT valor FROM pr_config WHERE chave=?", (chave,)).fetchone()
    return row["valor"] if row else default


def pr_set_config(chave: str, valor: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO pr_config (chave, valor) VALUES (?,?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, valor))


def pr_save_pedidos(pedidos: list[dict], synced_at: str) -> int:
    """Substitui o cache de pedidos pelo resultado de uma sincronização."""
    import json as _json
    with connect() as conn:
        conn.execute("DELETE FROM pr_pedidos")
        conn.executemany(
            "INSERT OR REPLACE INTO pr_pedidos (id, numero, data, cliente, "
            "situacao, loja, total, frete, desconto, comissao, custo_frete, "
            "itens_json, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(p["id"], str(p.get("numero") or ""), p.get("data") or "",
              p.get("cliente") or "", p.get("situacao") or "", p.get("loja") or "",
              p.get("total") or 0, p.get("frete") or 0, p.get("desconto") or 0,
              (p.get("taxas") or {}).get("comissao") or 0,
              (p.get("taxas") or {}).get("custo_frete") or 0,
              _json.dumps(p.get("itens") or [], ensure_ascii=False), synced_at)
             for p in pedidos])
    return len(pedidos)


def pr_load_pedidos() -> tuple[list[dict], str | None]:
    """Pedidos do cache no formato de pricing.analisar_pedido + data da sync."""
    import json as _json
    with connect() as conn:
        rows = conn.execute("SELECT * FROM pr_pedidos ORDER BY data DESC, id DESC").fetchall()
    pedidos = [{
        "id": r["id"], "numero": r["numero"], "data": r["data"],
        "cliente": r["cliente"], "situacao": r["situacao"], "loja": r["loja"],
        "total": r["total"], "frete": r["frete"], "desconto": r["desconto"],
        "taxas": {"comissao": r["comissao"], "custo_frete": r["custo_frete"]},
        "itens": _json.loads(r["itens_json"] or "[]"),
    } for r in rows]
    synced_at = rows[0]["synced_at"] if rows else None
    return pedidos, synced_at
