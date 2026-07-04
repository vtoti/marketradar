"""OAuth do Mercado Livre com refresh automático de token.

O `access_token` do ML expira em ~6h. Para coleta autônoma 24/7, guardamos o
`refresh_token` e trocamos por um novo par automaticamente antes de cada uso.

Fluxo (uma vez, via mlauth.py):
    1. Abrir a URL de autorização e logar → o ML redireciona com `?code=...`.
    2. Trocar o `code` por access_token + refresh_token (exchange_code).
    3. Os tokens ficam salvos em data/ml_tokens.json (disco persistente).

Depois disso, get_valid_token() renova sozinho enquanto o refresh_token viver.
Docs: https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

import config

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
_SKEW = 300  # renova 5 min antes de expirar


def _store_path() -> Path:
    return config.ML_TOKEN_FILE


def _load_store() -> dict:
    p = _store_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    # bootstrap a partir do .env, se houver refresh_token configurado
    if config.ML_REFRESH_TOKEN:
        return {"access_token": config.ML_ACCESS_TOKEN,
                "refresh_token": config.ML_REFRESH_TOKEN,
                "expires_at": 0}
    return {}


def _save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def authorization_url() -> str:
    """URL para o usuário autorizar o app (passo 1)."""
    if not config.ML_CLIENT_ID or not config.ML_REDIRECT_URI:
        raise RuntimeError("Defina ML_CLIENT_ID e ML_REDIRECT_URI no .env.")
    return (f"{AUTH_URL}?response_type=code&client_id={config.ML_CLIENT_ID}"
            f"&redirect_uri={config.ML_REDIRECT_URI}")


def _post_token(payload: dict) -> dict:
    payload.update({"client_id": config.ML_CLIENT_ID,
                    "client_secret": config.ML_CLIENT_SECRET})
    resp = requests.post(TOKEN_URL, data=payload,
                         headers={"Accept": "application/json"}, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Falha OAuth ML ({resp.status_code}): {resp.text}")
    tok = resp.json()
    store = {
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token", ""),
        "expires_at": time.time() + int(tok.get("expires_in", 21600)),
        "user_id": tok.get("user_id"),
    }
    _save_store(store)
    return store


def exchange_code(code: str) -> dict:
    """Troca o `code` da autorização por tokens (passo 2)."""
    return _post_token({"grant_type": "authorization_code", "code": code,
                        "redirect_uri": config.ML_REDIRECT_URI})


def refresh() -> dict:
    """Renova o access_token usando o refresh_token."""
    store = _load_store()
    rt = store.get("refresh_token") or config.ML_REFRESH_TOKEN
    if not rt:
        raise RuntimeError("Sem refresh_token. Rode `python mlauth.py` uma vez.")
    return _post_token({"grant_type": "refresh_token", "refresh_token": rt})


def get_valid_token() -> str:
    """Retorna um access_token válido, renovando automaticamente se preciso.

    Ordem de fallback:
      1. Token do arquivo (renovado se expirado e houver refresh_token).
      2. ML_ACCESS_TOKEN estático do .env (uso simples/manual).
    """
    store = _load_store()
    now = time.time()
    if store.get("access_token") and store.get("expires_at", 0) - _SKEW > now:
        return store["access_token"]
    if store.get("refresh_token") or config.ML_REFRESH_TOKEN:
        try:
            return refresh()["access_token"]
        except Exception:
            pass
    return store.get("access_token") or config.ML_ACCESS_TOKEN


def status() -> dict:
    """Resumo do estado do token, para o dashboard."""
    store = _load_store()
    exp = store.get("expires_at", 0)
    return {
        "tem_token": bool(store.get("access_token") or config.ML_ACCESS_TOKEN),
        "tem_refresh": bool(store.get("refresh_token") or config.ML_REFRESH_TOKEN),
        "expira_em_min": round((exp - time.time()) / 60, 1) if exp else None,
    }
