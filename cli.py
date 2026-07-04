"""CLI do Radar de Mercado.

Exemplos:
    python cli.py search "fone bluetooth" --marketplaces mercadolivre --limit 30
    python cli.py niches "fone bluetooth" "garrafa termica" --marketplaces mercadolivre
"""
from __future__ import annotations

import argparse
import json

from marketradar.service import run_search, evaluate_niches
from marketradar.analysis import metrics


def cmd_search(args):
    df, status = run_search(args.query, args.marketplaces, limit=args.limit)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if df.empty:
        print("Sem resultados.")
        return
    print(json.dumps(metrics.market_summary(df), ensure_ascii=False, indent=2))


def cmd_niches(args):
    scored = evaluate_niches(args.terms, args.marketplaces, limit=args.limit)
    for s in sorted(scored, key=lambda x: x["score"], reverse=True):
        print(f"{s['score']:>5}  {s['termo']:<30} {s.get('classificacao','')}")


def main():
    p = argparse.ArgumentParser(description="Radar de Mercado")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("search", help="Analisa um termo")
    s.add_argument("query")
    s.add_argument("--marketplaces", nargs="+", default=["mercadolivre"])
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)

    n = sub.add_parser("niches", help="Ranqueia nichos por oportunidade")
    n.add_argument("terms", nargs="+")
    n.add_argument("--marketplaces", nargs="+", default=["mercadolivre"])
    n.add_argument("--limit", type=int, default=40)
    n.set_defaults(func=cmd_niches)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
