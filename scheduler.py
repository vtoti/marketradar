"""Scheduler da coleta diária (para nuvem/containers).

Substitui o Agendador de Tarefas do Windows: um processo de longa duração que
dispara a coleta uma vez por dia, na hora definida por RUN_HOUR (0–23, UTC do
container). Também renova o token do ML antes de coletar.

Roda como serviço próprio no docker-compose. Localmente você pode simplesmente:
    python scheduler.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
from marketradar import jobs


def _seconds_until_next_run(hour: int) -> float:
    now = datetime.now()
    nxt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def run_once():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Coleta iniciada.", flush=True)
    try:
        # renova token do ML (se OAuth configurado) antes de coletar
        try:
            from marketradar import auth_ml
            auth_ml.get_valid_token()
        except Exception as e:
            print(f"  aviso: token ML não renovado: {e}", flush=True)

        res = jobs.run_daily(limit=config.COLLECT_LIMIT, origem="agendado")
        status = "OK" if res["ok"] else "COM FALHAS"
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Coleta {status}: "
              f"{res['termos']} termos, {res['anuncios']} anúncios, "
              f"{res['duracao_s']}s.", flush=True)
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERRO na coleta: {e}", flush=True)


def main():
    hour = config.RUN_HOUR
    print(f"Scheduler ativo. Coleta diária às {hour:02d}:00 "
          f"(limite {config.COLLECT_LIMIT}/termo).", flush=True)
    # Se RUN_ON_START=1, coleta uma vez ao subir (útil para testar o deploy).
    import os
    if os.getenv("RUN_ON_START", "0") == "1":
        run_once()
    while True:
        wait = _seconds_until_next_run(hour)
        print(f"Próxima coleta em {wait/3600:.1f}h "
              f"({datetime.now() + timedelta(seconds=wait):%Y-%m-%d %H:%M}).",
              flush=True)
        time.sleep(wait)
        run_once()


if __name__ == "__main__":
    main()
