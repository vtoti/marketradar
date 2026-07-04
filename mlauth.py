"""Autorização inicial do Mercado Livre (rodar UMA vez).

Pré-requisitos no .env: ML_CLIENT_ID, ML_CLIENT_SECRET, ML_REDIRECT_URI
(o redirect precisa ser exatamente o cadastrado no seu app do ML).

Uso:
    python mlauth.py url                 # imprime a URL de autorização
    python mlauth.py exchange <code>     # troca o code pelos tokens
    python mlauth.py status              # mostra o estado do token
    python mlauth.py refresh             # força uma renovação

Passo a passo:
    1) python mlauth.py url  → abra a URL, faça login e autorize.
    2) O navegador vai para o seu redirect_uri com ...?code=TG-xxxx
    3) python mlauth.py exchange TG-xxxx
    Pronto: refresh automático a partir daqui.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from marketradar import auth_ml


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "url":
        print("\nAbra esta URL, faça login e autorize:\n")
        print(auth_ml.authorization_url())
        print("\nDepois copie o `code` da URL de retorno e rode:\n"
              "  python mlauth.py exchange <code>\n")
    elif cmd == "exchange":
        if len(sys.argv) < 3:
            print("Informe o code: python mlauth.py exchange <code>")
            return
        store = auth_ml.exchange_code(sys.argv[2])
        print(f"OK! Tokens salvos. user_id={store.get('user_id')}")
        print("Refresh automático ativado.")
    elif cmd == "status":
        print(auth_ml.status())
    elif cmd == "refresh":
        auth_ml.refresh()
        print("Token renovado.", auth_ml.status())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
