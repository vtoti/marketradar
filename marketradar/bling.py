"""Integração com o ERP Bling (API v3) — OAuth + sincronização de pedidos.

Espelha o padrão de `auth_ml.py`: tokens persistidos em data/bling_tokens.json
com refresh automático. As credenciais (client_id/client_secret) vêm do .env
(BLING_CLIENT_ID/BLING_CLIENT_SECRET) ou, em fallback, do próprio arquivo de
tokens (quando salvas pela interface).

Fluxo (uma vez, pela página 🧾 Pedidos Bling):
    1. authorization_url() → usuário autoriza no Bling → redirect com ?code=
    2. exchange_code(code) → tokens salvos.
    3. get_valid_token() renova sozinho (access ~6h, refresh ~30 dias).

Docs: https://developer.bling.com.br
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from pathlib import Path
from typing import Callable

import requests

import config

AUTH_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
API_URL = "https://api.bling.com.br/Api/v3"
_SKEW = 300           # renova 5 min antes de expirar
_DELAY = 0.4          # limite Bling: 3 req/s — usamos ~2,5/s
_PAGE = 100
_MAX_PEDIDOS = 500    # teto de segurança por sincronização
_last_call = 0.0


# ------------------------------------------------------------- store -------
def _store_path() -> Path:
    return config.BLING_TOKEN_FILE


def _load_store() -> dict:
    p = _store_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def credentials() -> tuple[str, str]:
    """client_id/secret do .env, com fallback para os salvos pela interface."""
    store = _load_store()
    cid = config.BLING_CLIENT_ID or store.get("client_id", "")
    sec = config.BLING_CLIENT_SECRET or store.get("client_secret", "")
    return cid, sec


def save_credentials(client_id: str, client_secret: str) -> None:
    """Salva credenciais digitadas na interface (invalida tokens antigos)."""
    _save_store({"client_id": client_id.strip(),
                 "client_secret": client_secret.strip()})


# ------------------------------------------------------------- OAuth -------
def authorization_url() -> str:
    """URL de autorização (passo 1). Gera e persiste um `state` anti-CSRF."""
    cid, _ = credentials()
    if not cid:
        raise RuntimeError("Configure o Client ID do Bling primeiro.")
    store = _load_store()
    store["oauth_state"] = secrets.token_hex(16)
    _save_store(store)
    return f"{AUTH_URL}?response_type=code&client_id={cid}&state={store['oauth_state']}"


def _basic_auth() -> str:
    cid, sec = credentials()
    return "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode()


def _post_token(payload: dict) -> dict:
    resp = requests.post(
        TOKEN_URL, data=payload, timeout=30,
        headers={"Authorization": _basic_auth(), "Accept": "application/json"})
    if resp.status_code != 200:
        raise RuntimeError(f"Falha OAuth Bling ({resp.status_code}): {resp.text[:300]}")
    tok = resp.json()
    store = _load_store()
    store.update({
        "access_token": tok["access_token"],
        "refresh_token": tok.get("refresh_token", store.get("refresh_token", "")),
        "expires_at": time.time() + int(tok.get("expires_in", 21600)),
    })
    store.pop("oauth_state", None)
    _save_store(store)
    return store


def exchange_code(code: str, state: str) -> dict:
    """Troca o `code` por tokens (passo 2), validando o state anti-CSRF."""
    saved = _load_store().get("oauth_state", "")
    if not saved or state != saved:
        raise RuntimeError("state da autorização não confere — recomece a conexão.")
    return _post_token({"grant_type": "authorization_code", "code": code})


def refresh() -> dict:
    store = _load_store()
    rt = store.get("refresh_token")
    if not rt:
        raise RuntimeError("Sem refresh_token — refaça a autorização com o Bling.")
    return _post_token({"grant_type": "refresh_token", "refresh_token": rt})


def get_valid_token() -> str:
    store = _load_store()
    if store.get("access_token") and store.get("expires_at", 0) - _SKEW > time.time():
        return store["access_token"]
    return refresh()["access_token"]


def status() -> dict:
    """Resumo para o dashboard."""
    store = _load_store()
    cid, sec = credentials()
    exp = store.get("expires_at", 0)
    return {
        "tem_credenciais": bool(cid and sec),
        "conectado": bool(store.get("refresh_token")),
        "expira_em_min": round((exp - time.time()) / 60, 1) if exp else None,
    }


def desconectar() -> None:
    """Remove tokens (mantém credenciais salvas pela interface)."""
    store = _load_store()
    for k in ("access_token", "refresh_token", "expires_at", "oauth_state"):
        store.pop(k, None)
    _save_store(store)


# ------------------------------------------------------------- API ---------
def _get(path: str, _retried: bool = False) -> dict:
    """GET autenticado com throttle (3 req/s) e retry de 401/429."""
    global _last_call
    wait = _last_call + _DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()

    resp = requests.get(
        API_URL + path, timeout=30,
        headers={"Authorization": f"Bearer {get_valid_token()}",
                 "Accept": "application/json"})
    if resp.status_code == 401 and not _retried:
        refresh()
        return _get(path, _retried=True)
    if resp.status_code == 429:
        time.sleep(1.5)
        return _get(path, _retried)
    if resp.status_code != 200:
        detalhe = ""
        try:
            err = resp.json().get("error", {})
            detalhe = err.get("description") or err.get("message") or ""
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(f"Bling {path} → HTTP {resp.status_code} {detalhe}".strip())
    return resp.json()


def _mapa_custos() -> dict:
    """produto_id → preço de custo, varrendo o cadastro de produtos."""
    mapa: dict = {}
    for pagina in range(1, 21):
        body = _get(f"/produtos?pagina={pagina}&limite={_PAGE}")
        lista = body.get("data") or []
        for p in lista:
            if p.get("id"):
                custo = p.get("precoCusto") or (p.get("fornecedor") or {}).get("precoCusto") or 0
                mapa[p["id"]] = float(custo or 0)
        if len(lista) < _PAGE:
            break
    return mapa


def sync_pedidos(data_inicial: str, data_final: str,
                 progress: Callable[[int, int, str], None] | None = None) -> list[dict]:
    """Baixa pedidos do período (AAAA-MM-DD) já enriquecidos com custos.

    Retorna a lista de pedidos no formato usado por pricing.analisar_pedido.
    `progress(atual, total, etapa)` é chamado ao longo da sincronização.
    """
    def _p(i: int, t: int, etapa: str) -> None:
        if progress:
            progress(i, t, etapa)

    _p(0, 1, "Baixando custos dos produtos…")
    custos = _mapa_custos()

    resumo: list[dict] = []
    for pagina in range(1, 100):
        _p(0, 1, f"Listando pedidos (página {pagina})…")
        body = _get(f"/pedidos/vendas?pagina={pagina}&limite={_PAGE}"
                    f"&dataInicial={data_inicial}&dataFinal={data_final}")
        lista = body.get("data") or []
        resumo.extend(lista)
        if len(lista) < _PAGE or len(resumo) >= _MAX_PEDIDOS:
            break
    resumo = resumo[:_MAX_PEDIDOS]

    pedidos: list[dict] = []
    total = len(resumo)
    for i, r in enumerate(resumo, 1):
        _p(i, total, f"Detalhando pedido {i}/{total}…")
        det = _get(f"/pedidos/vendas/{r['id']}").get("data") or {}
        itens = [{
            "codigo": it.get("codigo") or "",
            "descricao": it.get("descricao") or "",
            "quantidade": float(it.get("quantidade") or 0),
            "valor": float(it.get("valor") or 0),
            "custo_bling": float(custos.get((it.get("produto") or {}).get("id"), 0)),
        } for it in det.get("itens") or []]
        taxas = det.get("taxas") or {}
        pedidos.append({
            "id": det.get("id") or r["id"],
            "numero": det.get("numero") or r.get("numero"),
            "data": det.get("data") or r.get("data") or "",
            "cliente": (det.get("contato") or {}).get("nome")
                        or (r.get("contato") or {}).get("nome") or "",
            "situacao": str((det.get("situacao") or {}).get("valor")
                            or (r.get("situacao") or {}).get("valor")
                            or (det.get("situacao") or {}).get("id") or ""),
            "loja": str((det.get("loja") or {}).get("id") or ""),
            "total": float(det.get("total") or r.get("total") or 0),
            "frete": float((det.get("transporte") or {}).get("frete") or 0),
            "desconto": float((det.get("desconto") or {}).get("valor") or 0),
            "taxas": {"comissao": float(taxas.get("taxaComissao") or 0),
                      "custo_frete": float(taxas.get("custoFrete") or 0)},
            "itens": itens,
        })
    return pedidos
