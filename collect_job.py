"""Ponto de entrada do job diário (executado pelo Agendador de Tarefas).

Uso:
    python collect_job.py            # coleta todos os termos monitorados
    python collect_job.py --limit 40 --add "fone bluetooth" "garrafa termica"

Registre no Windows com register_task.ps1 (ver README).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from marketradar import jobs


def main():
    p = argparse.ArgumentParser(description="Coleta diária do Radar de Mercado")
    p.add_argument("--limit", type=int, default=60,
                   help="anúncios por termo (padrão 60)")
    p.add_argument("--marketplaces", nargs="+", default=["mercadolivre"],
                   help="usados ao registrar novos termos com --add")
    p.add_argument("--add", nargs="+", default=[],
                   help="registra termos para monitoramento e sai")
    args = p.parse_args()

    if args.add:
        for term in args.add:
            jobs.add_tracked_term(term, args.marketplaces)
            print(f"+ termo monitorado: {term} ({', '.join(args.marketplaces)})")
        return

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Iniciando coleta diária...")
    terms = jobs.tracked_terms()
    if not terms:
        print("Nenhum termo monitorado ainda. Use --add ou o dashboard para "
              "adicionar termos.")
        return

    def prog(i, total, term):
        print(f"  [{i}/{total}] {term}")

    res = jobs.run_daily(limit=args.limit, origem="agendado", progress=prog)
    status = "OK" if res["ok"] else "COM FALHAS"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Concluído ({status}): "
          f"{res['termos']} termos, {res['anuncios']} anúncios, "
          f"{res['duracao_s']}s")
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
