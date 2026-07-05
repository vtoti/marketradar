"""Teste de fumaça: valida armazenamento e análise com dados sintéticos,
sem depender da rede. Use para confirmar que a instalação está sã.

    python selftest.py
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timezone, timedelta

try:  # console Windows costuma ser cp1252; emojis dos veredicts exigem utf-8
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from marketradar.collectors.base import Listing
from marketradar.storage import db
from marketradar.analysis import metrics
from marketradar.analysis.opportunity import niche_score
import pandas as pd


def fake_listings(query="teste", n=40):
    sellers = [f"loja_{i}" for i in range(8)]
    out = []
    for i in range(n):
        price = round(random.uniform(50, 400), 2)
        seller = random.choice(sellers)
        out.append(Listing(
            marketplace="mercadolivre", listing_id=f"MLB{i}", title=f"Produto {i}",
            price=price, query=query,
            sold_quantity=random.randint(0, 5000),
            available_quantity=random.randint(1, 100),
            seller_id=seller,
            seller_name=seller,
            rating=round(random.uniform(3.5, 5.0), 1),
            reviews=random.randint(0, 800),
            free_shipping=random.random() > 0.5,
        ))
    return out


def main():
    print("1) init_db...")
    db.init_db()

    print("2) coleta sintética + save...")
    listings = fake_listings()
    n = db.save_listings(listings)
    assert n == len(listings), "save_listings falhou"

    df = pd.DataFrame([l.to_dict() for l in listings])

    print("3) market_summary...")
    s = metrics.market_summary(df)
    assert s["anuncios"] == len(listings)
    assert s["vendedores"] >= 1
    print("   ", {k: s[k] for k in ("anuncios", "vendedores", "preco_mediano",
                                    "vendas_totais", "gmv_total")})

    print("4) seller_ranking / hhi...")
    r = metrics.seller_ranking(df)
    assert not r.empty and abs(r["share_pct"].sum() - 100) < 1.0

    print("5) niche_score...")
    ns = niche_score(df)
    assert 0 <= ns["score"] <= 100
    print("    score:", ns["score"], "-", ns["classificacao"])
    print("    componentes:", ns["componentes"])

    print("6) estimate_velocity (2 snapshots)...")
    now = datetime.now(timezone.utc)
    hist = pd.DataFrame([
        {"collected_at": (now - timedelta(days=10)).isoformat(),
         "price": 100.0, "sold_quantity": 100, "available_quantity": 50},
        {"collected_at": now.isoformat(),
         "price": 100.0, "sold_quantity": 250, "available_quantity": 40},
    ])
    v = metrics.estimate_velocity(hist)
    assert v["vendas_por_dia"] == 15.0, v
    print("    ", v)

    print("7) detector de produtos vencedores...")
    from marketradar.analysis.winning import (
        WinningCriteria, evaluate_product, rank_products,
        demand_supply_ratio, classify_trend)
    # produto claramente vencedor: demanda alta, preço na faixa, poucas reviews,
    # nota mediana, frete grátis.
    otimo = {"listing_id": "X1", "title": "Bom", "marketplace": "mercadolivre",
             "price": 99.0, "sold_quantity": 800, "reviews": 40, "rating": 4.2,
             "free_shipping": True, "permalink": ""}
    ruim = {"listing_id": "X2", "title": "Ruim", "marketplace": "mercadolivre",
            "price": 9.0, "sold_quantity": 2, "reviews": 9000, "rating": 4.95,
            "free_shipping": False, "permalink": ""}
    e_otimo = evaluate_product(otimo, WinningCriteria())
    e_ruim = evaluate_product(ruim, WinningCriteria())
    assert e_otimo["score"] > e_ruim["score"], (e_otimo["score"], e_ruim["score"])
    assert e_otimo["score"] >= 60, e_otimo["score"]
    print(f"    ótimo={e_otimo['score']} ({e_otimo['veredito']}) | "
          f"ruim={e_ruim['score']} ({e_ruim['veredito']})")

    # margem entra quando há custo
    com_custo = evaluate_product(otimo, WinningCriteria(), cost=25.0)
    assert com_custo["markup"] == round(99.0 / 25.0, 2)

    rk = rank_products(df, WinningCriteria())
    assert not rk.empty and rk["Score"].is_monotonic_decreasing
    print("    ranking:", len(rk), "produtos, topo =", rk.iloc[0]["Score"])

    # market_summary devolve vendas_totais=0 de propósito (frente pública do
    # ML não expõe vendas) → o ratio calculado do summary é 0; com vendas
    # informadas, deve ser positivo.
    assert demand_supply_ratio(s) == 0.0
    assert demand_supply_ratio({"vendas_totais": 900, "vendedores": 8}) > 0
    t = classify_trend(pd.DataFrame([
        {"collected_at": (now - timedelta(days=5)).isoformat(), "sold_quantity": 100},
        {"collected_at": now.isoformat(), "sold_quantity": 200},
    ]))
    assert t["tendencia"].endswith("em alta"), t
    print("    demanda×oferta e tendência OK:", t)

    print("8) camada de jobs (offline)...")
    from marketradar import jobs
    jobs.add_tracked_term("caneca termica selftest", ["mercadolivre"])
    tracked = jobs.tracked_terms()
    assert any(x["term"] == "caneca termica selftest" for x in tracked), tracked
    # 'teste' foi salvo nos snapshots => deve aparecer como termo monitorado
    assert any(x["term"] == "teste" for x in tracked), tracked
    db.save_job_run(now.isoformat(), now.isoformat(), "manual",
                    len(tracked), 123, True, "{}")
    assert db.last_job_run()["anuncios"] == 123
    assert not db.list_job_runs().empty
    print(f"    {len(tracked)} termos monitorados, job_run registrado OK")

    print("9) engenharia de preços (pricing)...")
    from marketradar import pricing
    ml = pricing.Canal("Mercado Livre Clássico", 12.0, 6.5, 0.0)
    cv = pricing.custo_variavel(98.0, 6.0, 4.0)          # 108.0
    assert cv == 108.0, cv
    rat = pricing.rateio_fixo(6000.0, 255)               # ~23.53
    d = pricing.decompor(180.0, cv, 6.0, ml, rat)
    # 180 − 108 − 10.80 − (21.60+6.50) = 33.10 de MC
    assert abs(d.impostos - 10.80) < 0.01 and abs(d.taxas_canal - 28.10) < 0.01
    assert abs(d.mc - 33.10) < 0.01, d
    assert abs(d.lucro - (33.10 - rat)) < 0.01
    # preço ideal fecha o ciclo: decompor(preco_ideal) devolve a margem alvo
    ideal = pricing.preco_ideal(cv, 6.0, ml, 20.0, rat)
    di = pricing.decompor(ideal, cv, 6.0, ml, rat)
    assert abs(di.lucro_pct - 20.0) < 0.05, di.lucro_pct
    assert pricing.preco_ideal(cv, 50.0, ml, 45.0) is None  # impossível
    be = pricing.ponto_equilibrio(6000.0, d.mc)
    assert be is not None and abs(be - 6000.0 / d.mc) < 0.01
    assert pricing.classificar(-1) == "prejuízo"
    print(f"    MC={d.mc:.2f} lucro={d.lucro:.2f} ideal={ideal:.2f} "
          f"breakeven={be:.0f} un/mês")

    print("10) análise de pedido (Bling offline)...")
    pedido = {
        "total": 189.90, "frete": 0,
        "taxas": {"comissao": 32.28, "custo_frete": 21.90},
        "itens": [{"codigo": "VS-14", "descricao": "Válvula Solenóide",
                   "quantidade": 1, "valor": 189.90, "custo_bling": 98.0}],
    }
    a = pricing.analisar_pedido(pedido, 6.0, rat)
    # 189.90 − 98 − 11.394 − 54.18 = 26.33 de MC; lucro = MC − rateio
    assert abs(a["mc"] - 26.33) < 0.01, a["mc"]
    assert a["fonte_taxa"] == "Bling" and a["itens_sem_custo"] == 0
    assert abs(a["lucro"] - (a["mc"] - rat)) < 0.01
    # sem custo no ERP → resolve pelo cadastro local; sem match → sinaliza
    pedido2 = {"total": 100.0, "taxas": {"comissao": 0, "custo_frete": 0},
               "itens": [{"codigo": "X", "descricao": "Produto Y",
                          "quantidade": 2, "valor": 50.0, "custo_bling": 0}]}
    a2 = pricing.analisar_pedido(
        pedido2, 6.0, 0.0, ml, custo_local=lambda cod, desc: 20.0)
    assert a2["custo_prod"] == 40.0 and a2["itens"][0]["fonte_custo"] == "produto local"
    a3 = pricing.analisar_pedido(pedido2, 6.0, 0.0, ml)
    assert a3["itens_sem_custo"] == 1
    # canal padrão aplicado quando o ERP não traz taxas
    assert abs(a3["taxas"] - (100 * 0.12 + 6.5)) < 0.01
    print(f"    pedido ML: MC={a['mc']:.2f} ({a['mc_pct']:.1f}%) "
          f"status={a['status']} | fallback local/sem-custo OK")

    print("11) persistência pr_* (produtos/canais/fixos/pedidos)...")
    assert not db.pr_canais().empty, "canais padrão não semeados"
    db.pr_upsert("pr_produtos", {"nome": "Prod Selftest", "sku": "ST-1",
                                 "preco": 100.0, "custo": 40.0, "frete": 5.0,
                                 "embalagem": 2.0, "outros": 0.0,
                                 "vendas_mes": 30})
    assert (db.pr_produtos()["nome"] == "Prod Selftest").any()
    db.pr_set_config("aliquota", "8.5")
    assert db.pr_get_config("aliquota") == "8.5"
    db.pr_save_pedidos([{**pedido, "id": 1, "numero": "42", "data": "2026-07-01",
                         "cliente": "Cliente T", "situacao": "Atendido",
                         "loja": "", "desconto": 0}], now.isoformat())
    carregados, sync_at = db.pr_load_pedidos()
    assert len(carregados) == 1 and carregados[0]["taxas"]["comissao"] == 32.28
    assert sync_at == now.isoformat()
    print(f"    {len(db.pr_canais())} canais, produto salvo, "
          f"{len(carregados)} pedido em cache OK")

    print("\n[OK] Todos os testes passaram.")


if __name__ == "__main__":
    main()
