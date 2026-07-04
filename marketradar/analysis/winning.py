"""Detector de Produtos Vencedores.

Implementa critérios *validados* de seleção de produtos usados por ferramentas
de mercado (Nubimetric, Jungle Scout/Helium 10) e por vendedores experientes,
adaptados aos dados que conseguimos coletar de Mercado Livre/Shopee.

Critérios (referências no README):
  1. Demanda forte        — vendas acumuladas/velocidade acima de um piso.
  2. Demanda × oferta      — muita procura para poucos vendedores (nicho).
  3. Faixa de preço ideal  — ~R$ 50–150 (compra por impulso + margem).
  4. Margem saudável       — markup ≥ 3x / margem líquida ≥ 30% (se custo informado).
  5. Concorrência batível  — concorrentes com poucas avaliações (baixa barreira).
  6. Brecha de qualidade   — nota média mediana = clientes insatisfeitos = espaço.
  7. Momentum              — tendência de vendas em alta (requer histórico).
  8. Sinais de algoritmo   — frete grátis (proxy de competitividade logística).

Cada critério vira um sub-score 0–100; a nota final é a média ponderada.
Os limiares ficam em `WinningCriteria` e são todos configuráveis.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class WinningCriteria:
    min_vendas: int = 100                 # piso de demanda (vendas acumuladas)
    preco_ideal_min: float = 50.0         # faixa de preço saudável (R$)
    preco_ideal_max: float = 150.0
    max_reviews_bativel: int = 500        # acima disso, concorrente consolidado
    rating_teto_oportunidade: float = 4.6  # nota alta = concorrente difícil de bater
    rating_piso_qualidade: float = 3.3    # nota muito baixa = produto/categoria ruim
    markup_min: float = 3.0               # 3x o custo
    margem_liquida_min: float = 0.30      # 30% líquido
    pesos: dict = field(default_factory=lambda: {
        "demanda": 0.24,
        "preco": 0.14,
        "concorrencia_bativel": 0.18,
        "brecha_qualidade": 0.14,
        "momentum": 0.16,
        "logistica": 0.08,
        "margem": 0.06,
    })


def _clip(x, lo=0.0, hi=100.0):
    return float(max(lo, min(hi, x)))


# --- sub-scores 0–100 ---------------------------------------------------------
def _score_demanda(sold: int, crit: WinningCriteria) -> float:
    # Atinge 100 com o dobro do piso; linear até lá.
    return _clip(sold / max(crit.min_vendas * 2, 1) * 100)


def _score_preco(price: float, crit: WinningCriteria) -> float:
    lo, hi = crit.preco_ideal_min, crit.preco_ideal_max
    if price <= 0:
        return 0.0
    if lo <= price <= hi:
        return 100.0
    if price < lo:
        return _clip(price / lo * 100)          # muito barato aperta margem
    return _clip(100 - (price - hi) / hi * 100)  # caro demais reduz giro


def _score_concorrencia(reviews: int, crit: WinningCriteria) -> float:
    # Poucas avaliações no concorrente => barreira baixa => oportunidade.
    return _clip(100 - reviews / max(crit.max_reviews_bativel, 1) * 100)


def _score_brecha_qualidade(rating, crit: WinningCriteria) -> float:
    if rating is None or pd.isna(rating):
        return 50.0  # desconhecido => neutro
    if rating < crit.rating_piso_qualidade:
        return 25.0  # produto ruim: risco, não oportunidade
    if rating >= crit.rating_teto_oportunidade:
        return _clip(100 - (rating - crit.rating_teto_oportunidade) /
                     (5 - crit.rating_teto_oportunidade) * 100)  # concorrente forte
    # zona doce: entre piso e teto, quanto mais perto do teto-0.x melhor a brecha
    span = crit.rating_teto_oportunidade - crit.rating_piso_qualidade
    return _clip(60 + (crit.rating_teto_oportunidade - rating) / span * 40)


def _score_logistica(free_shipping: bool) -> float:
    return 100.0 if free_shipping else 45.0


def _score_margem(price: float, cost, crit: WinningCriteria):
    if not cost or cost <= 0 or price <= 0:
        return None, None
    markup = price / cost
    return _clip(markup / crit.markup_min * 100), markup


# --- avaliação por produto ----------------------------------------------------
def evaluate_product(row: dict, crit: WinningCriteria | None = None,
                     cost: float | None = None,
                     momentum: float | None = None) -> dict:
    """Avalia um anúncio (linha do DataFrame) como candidato a produto vencedor.

    `momentum` (0–100) é opcional e vem do histórico de snapshots; se ausente,
    usa-se um valor neutro (50) e o peso é redistribuído.
    """
    crit = crit or WinningCriteria()
    price = float(row.get("price") or 0)
    sold = int(row.get("sold_quantity") or 0)
    reviews = int(row.get("reviews") or 0)
    rating = row.get("rating")
    free = bool(row.get("free_shipping"))

    sub = {
        "demanda": _score_demanda(sold, crit),
        "preco": _score_preco(price, crit),
        "concorrencia_bativel": _score_concorrencia(reviews, crit),
        "brecha_qualidade": _score_brecha_qualidade(rating, crit),
        "momentum": 50.0 if momentum is None else _clip(momentum),
        "logistica": _score_logistica(free),
    }
    margem_score, markup = _score_margem(price, cost, crit)
    pesos = dict(crit.pesos)
    if margem_score is None:
        pesos.pop("margem", None)           # sem custo, ignora margem e renormaliza
    else:
        sub["margem"] = margem_score
    total_peso = sum(pesos[k] for k in sub if k in pesos)
    score = sum(sub[k] * pesos[k] for k in sub if k in pesos) / (total_peso or 1)

    checklist = [
        ("Demanda forte", sold >= crit.min_vendas, f"{sold} vendas",
         f"≥ {crit.min_vendas}"),
        ("Preço na faixa saudável",
         crit.preco_ideal_min <= price <= crit.preco_ideal_max,
         f"R$ {price:.2f}", f"R$ {crit.preco_ideal_min:.0f}–{crit.preco_ideal_max:.0f}"),
        ("Concorrência batível", reviews <= crit.max_reviews_bativel,
         f"{reviews} avaliações", f"≤ {crit.max_reviews_bativel}"),
        ("Brecha de qualidade",
         (rating is not None and not pd.isna(rating)
          and crit.rating_piso_qualidade <= rating < crit.rating_teto_oportunidade),
         f"nota {rating}" if rating else "sem nota",
         f"{crit.rating_piso_qualidade}–{crit.rating_teto_oportunidade}"),
        ("Logística competitiva (frete grátis)", free,
         "sim" if free else "não", "sim"),
    ]
    if momentum is not None:
        checklist.append(("Momentum de vendas (alta)", momentum >= 55,
                          f"{momentum:.0f}/100", "≥ 55"))
    if markup is not None:
        checklist.append((f"Margem saudável (≥ {crit.markup_min:.0f}x)",
                          markup >= crit.markup_min, f"{markup:.1f}x",
                          f"≥ {crit.markup_min:.0f}x"))

    aprovados = sum(1 for _, ok, *_ in checklist if ok)
    return {
        "listing_id": row.get("listing_id", ""),
        "title": row.get("title", ""),
        "marketplace": row.get("marketplace", ""),
        "price": price,
        "sold_quantity": sold,
        "reviews": reviews,
        "rating": rating,
        "permalink": row.get("permalink", ""),
        "score": round(score, 1),
        "veredito": _verdict(score),
        "criterios_ok": aprovados,
        "criterios_total": len(checklist),
        "subscores": {k: round(v, 1) for k, v in sub.items()},
        "checklist": checklist,
        "markup": round(markup, 2) if markup else None,
    }


def _verdict(score: float) -> str:
    if score >= 75:
        return "🏆 Produto vencedor"
    if score >= 60:
        return "✅ Forte candidato"
    if score >= 45:
        return "🟡 Potencial (validar)"
    return "🔴 Pouco atrativo"


def rank_products(df: pd.DataFrame, crit: WinningCriteria | None = None,
                  cost: float | None = None,
                  momentum_map: dict | None = None) -> pd.DataFrame:
    """Ranqueia todos os anúncios de um DataFrame pelo score de produto vencedor."""
    if df is None or df.empty:
        return pd.DataFrame()
    momentum_map = momentum_map or {}
    rows = [evaluate_product(r, crit=crit, cost=cost,
                             momentum=momentum_map.get(r.get("listing_id")))
            for r in df.to_dict("records")]
    out = pd.DataFrame([{
        "Produto": r["title"][:70], "Marketplace": r["marketplace"],
        "Preço": r["price"], "Vendas": r["sold_quantity"],
        "Avaliações": r["reviews"], "Nota": r["rating"],
        "Score": r["score"], "Veredito": r["veredito"],
        "Critérios": f'{r["criterios_ok"]}/{r["criterios_total"]}',
        "Link": r["permalink"], "_detalhe": r,
    } for r in rows])
    return out.sort_values("Score", ascending=False).reset_index(drop=True)


# --- sinais de nicho ----------------------------------------------------------
def demand_supply_ratio(summary: dict) -> float:
    """Vendas por vendedor: quanto maior, mais demanda insatisfeita por oferta."""
    if not summary:
        return 0.0
    return round(summary.get("vendas_totais", 0) /
                 max(summary.get("vendedores", 1), 1), 1)


def classify_trend(history: pd.DataFrame) -> dict:
    """Classifica a tendência de vendas de um nicho a partir de snapshots datados.

    Compara o total de vendas acumuladas entre o snapshot mais antigo e o mais
    recente e reporta crescimento diário médio.
    """
    if history is None or history.empty or "collected_at" not in history:
        return {"tendencia": "desconhecida", "variacao_pct": None}
    h = history.copy()
    h["collected_at"] = pd.to_datetime(h["collected_at"], utc=True, errors="coerce")
    daily = h.dropna(subset=["collected_at"]).groupby(
        h["collected_at"].dt.date)["sold_quantity"].sum()
    if len(daily) < 2:
        return {"tendencia": "desconhecida", "variacao_pct": None}
    first, last = daily.iloc[0], daily.iloc[-1]
    if first <= 0:
        return {"tendencia": "desconhecida", "variacao_pct": None}
    var = (last - first) / first * 100
    if var >= 10:
        t = "📈 em alta"
    elif var <= -10:
        t = "📉 em queda"
    else:
        t = "➡️ estável"
    return {"tendencia": t, "variacao_pct": round(var, 1)}
