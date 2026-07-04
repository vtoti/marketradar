"""Jobs de coleta em lote.

Um "job diário" percorre todos os termos monitorados e coleta um novo snapshot
de cada um. É isso que constrói a série temporal usada para estimar velocidade
de vendas, momentum e tendência.

Termos monitorados = termos adicionados explicitamente (watchlist kind='termo')
UNIÃO todas as buscas já coletadas alguma vez (para manter o histórico vivo).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from marketradar.storage import db
from marketradar.service import run_search

DEFAULT_MARKETPLACES = ["mercadolivre"]


def add_tracked_term(term: str, marketplaces: list[str]) -> None:
    """Registra um termo para ser coletado no job diário."""
    term = term.strip()
    if not term:
        return
    existing = tracked_terms()
    for t in existing:
        if t["term"].lower() == term.lower():
            return  # já monitorado
    db.add_watch("termo", ",".join(marketplaces), term, term)


def tracked_terms() -> list[dict]:
    """Lista de {term, marketplaces} a coletar."""
    merged: dict[str, set] = {}

    wl = db.get_watchlist("termo")
    for _, row in wl.iterrows():
        mps = [m for m in str(row["marketplace"]).split(",") if m]
        merged.setdefault(row["ref"], set()).update(mps or DEFAULT_MARKETPLACES)

    hist = db.list_queries()
    for _, row in hist.iterrows():
        merged.setdefault(row["query"], set()).add(row["marketplace"])

    return [{"term": term, "marketplaces": sorted(mps)}
            for term, mps in merged.items() if mps]


def run_daily(limit: int = 60, origem: str = "agendado",
              progress=None) -> dict:
    """Executa a coleta de todos os termos monitorados e registra a execução.

    `progress` é um callback opcional progress(i, total, termo) para a UI.
    """
    db.init_db()
    started = datetime.now(timezone.utc)
    terms = tracked_terms()
    total_anuncios, detalhe, all_ok = 0, {}, True

    for i, t in enumerate(terms, 1):
        if progress:
            progress(i, len(terms), t["term"])
        df, status = run_search(t["term"], t["marketplaces"], limit=limit)
        total_anuncios += 0 if df is None or df.empty else len(df)
        detalhe[t["term"]] = status
        if not all(s["ok"] for s in status.values()):
            all_ok = False

    finished = datetime.now(timezone.utc)
    db.save_job_run(started.isoformat(), finished.isoformat(), origem,
                    len(terms), total_anuncios, all_ok,
                    json.dumps(detalhe, ensure_ascii=False))
    return {
        "termos": len(terms),
        "anuncios": total_anuncios,
        "ok": all_ok,
        "duracao_s": round((finished - started).total_seconds(), 1),
        "detalhe": detalhe,
    }
