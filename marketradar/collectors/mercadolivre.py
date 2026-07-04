"""Coletor do Mercado Livre.

Usa a API oficial (api.mercadolibre.com). A busca por palavra-chave passou a
exigir, na maioria dos casos, um access token OAuth — defina ML_ACCESS_TOKEN
no .env. Sem token, o coletor tenta mesmo assim e reporta erro claro se o
endpoint responder 401/403.

Docs: https://developers.mercadolivre.com.br/pt_br/itens-e-buscas
"""
from __future__ import annotations

import config
from .base import BaseCollector, Listing

API = "https://api.mercadolibre.com"


class MercadoLivreCollector(BaseCollector):
    name = "mercadolivre"

    def __init__(self, site: str | None = None, token: str | None = None, **kw):
        super().__init__(**kw)
        self.site = site or config.ML_SITE
        # token explícito sobrepõe; senão resolve dinamicamente (com refresh).
        self._explicit_token = token

    def _current_token(self) -> str:
        if self._explicit_token is not None:
            return self._explicit_token
        from marketradar import auth_ml  # import tardio evita ciclo
        return auth_ml.get_valid_token()

    def _auth_headers(self) -> dict:
        token = self._current_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def search(self, query: str, limit: int = 50, condition: str = "") -> list[Listing]:
        listings: list[Listing] = []
        offset = 0
        page = 50
        while len(listings) < limit:
            params = {"q": query, "limit": min(page, limit - len(listings)),
                      "offset": offset}
            if condition:
                params["condition"] = condition
            resp = self._get(f"{API}/sites/{self.site}/search",
                             params=params, headers=self._auth_headers())
            if resp.status_code in (401, 403):
                raise PermissionError(
                    "Mercado Livre exigiu autenticação. Configure ML_ACCESS_TOKEN "
                    f"no .env. (HTTP {resp.status_code})"
                )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for r in results:
                listings.append(self._parse(r, query))
            paging = data.get("paging", {})
            offset += len(results)
            if offset >= paging.get("total", 0):
                break
        return listings[:limit]

    def _parse(self, r: dict, query: str) -> Listing:
        seller = r.get("seller", {}) or {}
        shipping = r.get("shipping", {}) or {}
        return Listing(
            marketplace=self.name,
            listing_id=str(r.get("id", "")),
            title=r.get("title", ""),
            price=float(r.get("price") or 0),
            query=query,
            currency=r.get("currency_id", "BRL"),
            sold_quantity=int(r.get("sold_quantity") or 0),
            available_quantity=int(r.get("available_quantity") or 0),
            condition=r.get("condition", "new"),
            seller_id=str(seller.get("id", "")),
            seller_name=seller.get("nickname", "") or "",
            free_shipping=bool(shipping.get("free_shipping", False)),
            category_id=r.get("category_id", "") or "",
            permalink=r.get("permalink", "") or "",
            thumbnail=r.get("thumbnail", "") or "",
        )

    def trends(self) -> list[dict]:
        """Tendências de busca do site (produtos em alta). Requer token."""
        resp = self._get(f"{API}/trends/{self.site}", headers=self._auth_headers())
        if resp.status_code == 200:
            return resp.json()
        return []
