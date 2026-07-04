"""Score de oportunidade para descoberta de novos produtos.

Combina demanda, concorrência, concentração e satisfação em uma nota 0–100.
A ideia (como nas ferramentas de mercado) é achar nichos com **alta demanda e
baixa concorrência** — onde entrar com um produto novo tende a valer mais a pena.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import market_summary


def _clip(x, lo=0.0, hi=100.0):
    return float(max(lo, min(hi, x)))


def niche_score(df: pd.DataFrame) -> dict:
    """Calcula o score de oportunidade de um nicho (resultado de uma busca)."""
    s = market_summary(df)
    if not s:
        return {"score": 0, "componentes": {}, "resumo": s}

    # Demanda: vendas totais do nicho (escala log, satura ~50k vendas).
    demanda = _clip(np.log1p(s["vendas_totais"]) / np.log1p(50000) * 100)

    # Concorrência: menos vendedores => mais oportunidade (satura ~200).
    concorrencia = _clip(100 - np.log1p(s["vendedores"]) / np.log1p(200) * 100)

    # Concentração: mercado pulverizado (HHI baixo) => mais espaço para entrar.
    # HHI 0 (pulverizado) -> 100 ; HHI 10000 (monopólio) -> 0.
    concentracao = _clip(100 - s["concentracao_hhi"] / 100)

    # Satisfação: avaliação média baixa => clientes insatisfeitos => brecha.
    rating = s.get("avaliacao_media")
    insatisfacao = _clip((5 - rating) / 5 * 100) if rating else 50.0

    # Ticket: preços muito baixos apertam margem; recompensa ticket saudável.
    ticket = s["ticket_medio"]
    margem = _clip(np.log1p(ticket) / np.log1p(500) * 100) if ticket else 0.0

    pesos = {
        "demanda": 0.35,
        "baixa_concorrencia": 0.25,
        "mercado_pulverizado": 0.15,
        "brecha_satisfacao": 0.15,
        "potencial_margem": 0.10,
    }
    comp = {
        "demanda": round(demanda, 1),
        "baixa_concorrencia": round(concorrencia, 1),
        "mercado_pulverizado": round(concentracao, 1),
        "brecha_satisfacao": round(insatisfacao, 1),
        "potencial_margem": round(margem, 1),
    }
    score = sum(comp[k] * pesos[k] for k in pesos)
    return {
        "score": round(score, 1),
        "classificacao": _classify(score),
        "componentes": comp,
        "pesos": pesos,
        "resumo": s,
    }


def _classify(score: float) -> str:
    if score >= 70:
        return "Excelente oportunidade"
    if score >= 55:
        return "Boa oportunidade"
    if score >= 40:
        return "Oportunidade moderada"
    return "Mercado difícil / saturado"


def rank_niches(scored: list[dict]) -> pd.DataFrame:
    """Ordena vários nichos avaliados (para comparar termos de busca)."""
    rows = []
    for item in scored:
        s = item.get("resumo", {})
        rows.append({
            "termo": item.get("termo", ""),
            "marketplace": item.get("marketplace", ""),
            "score": item.get("score", 0),
            "classificacao": item.get("classificacao", ""),
            "vendas_totais": s.get("vendas_totais", 0),
            "vendedores": s.get("vendedores", 0),
            "ticket_medio": round(s.get("ticket_medio", 0), 2),
            "gmv_total": round(s.get("gmv_total", 0), 2),
        })
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
