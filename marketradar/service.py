"""Camada de serviço: orquestra coleta + armazenamento + análise.

É o ponto de entrada usado pelo dashboard e pela CLI, para manter a interface
fina e a lógica testável.
"""
from __future__ import annotations

import pandas as pd

from marketradar.collectors import get_collector
from marketradar.storage import db


def run_search(query: str, marketplaces: list[str], limit: int = 50,
               save: bool = True) -> tuple[pd.DataFrame, dict]:
    """Coleta anúncios de uma busca em um ou mais marketplaces.

    Retorna (DataFrame combinado, dict de status por marketplace).
    """
    db.init_db()
    frames, status = [], {}
    for mp in marketplaces:
        try:
            collector = get_collector(mp)
            listings = collector.search(query, limit=limit)
            if save and listings:
                db.save_listings(listings)
            frames.append(pd.DataFrame([lst.to_dict() for lst in listings]))
            status[mp] = {"ok": True, "anuncios": len(listings), "erro": None}
        except Exception as e:  # coleta é intrinsecamente frágil; degradar bem
            status[mp] = {"ok": False, "anuncios": 0, "erro": str(e)}
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df, status


def evaluate_niches(terms: list[str], marketplaces: list[str],
                    limit: int = 50) -> list[dict]:
    """Avalia vários termos de busca e devolve o score de oportunidade de cada."""
    from marketradar.analysis.opportunity import niche_score
    results = []
    for term in terms:
        df, status = run_search(term, marketplaces, limit=limit)
        scored = niche_score(df)
        scored.update({"termo": term,
                       "marketplace": "+".join(marketplaces),
                       "status": status})
        results.append(scored)
    return results
