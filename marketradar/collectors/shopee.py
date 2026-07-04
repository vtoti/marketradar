"""Coletor da Shopee.

Usa o endpoint interno de busca (api/v4/search/search_items) que alimenta o
site. Não é uma API oficial: a Shopee aplica anti-bot e pode exigir cookies
válidos de uma sessão de navegador. Se a coleta vier vazia ou bloquear, cole
o cabeçalho Cookie do navegador em SHOPEE_COOKIE no .env.
"""
from __future__ import annotations

import config
from .base import BaseCollector, Listing


class ShopeeCollector(BaseCollector):
    name = "shopee"

    def __init__(self, region: str | None = None, cookie: str | None = None, **kw):
        super().__init__(**kw)
        self.region = region or config.SHOPEE_REGION
        self.cookie = cookie if cookie is not None else config.SHOPEE_COOKIE
        self.base = f"https://shopee.com.{self.region}" if self.region == "br" \
            else f"https://shopee.{self.region}"

    def _headers(self, keyword: str) -> dict:
        h = {
            "Accept": "application/json",
            "Referer": f"{self.base}/search?keyword={keyword}",
            "X-Requested-With": "XMLHttpRequest",
            "x-api-source": "pc",
            "x-shopee-language": "pt-BR",
        }
        if self.cookie:
            h["Cookie"] = self.cookie
        return h

    def search(self, query: str, limit: int = 50) -> list[Listing]:
        listings: list[Listing] = []
        newest = 0
        while len(listings) < limit:
            params = {
                "by": "relevancy", "keyword": query, "limit": 60,
                "newest": newest, "order": "desc",
                "page_type": "search", "scenario": "PAGE_GLOBAL_SEARCH",
                "version": 2,
            }
            resp = self._get(f"{self.base}/api/v4/search/search_items",
                             params=params, headers=self._headers(query))
            if resp.status_code != 200:
                raise ConnectionError(
                    f"Shopee retornou HTTP {resp.status_code}. Pode exigir cookies "
                    "válidos (SHOPEE_COOKIE no .env) ou estar bloqueando o acesso."
                )
            data = resp.json()
            items = data.get("items") or []
            if not items:
                break
            for it in items:
                b = it.get("item_basic") or it
                listings.append(self._parse(b, query))
            newest += 60
            if newest >= (data.get("total_count") or 0):
                break
        return listings[:limit]

    def _parse(self, b: dict, query: str) -> Listing:
        itemid, shopid = b.get("itemid"), b.get("shopid")
        rating = (b.get("item_rating") or {}).get("rating_star")
        rcount_list = (b.get("item_rating") or {}).get("rating_count") or []
        reviews = rcount_list[0] if rcount_list else 0
        permalink = ""
        if itemid and shopid:
            slug = (b.get("name", "").replace(" ", "-"))[:60]
            permalink = f"{self.base}/{slug}-i.{shopid}.{itemid}"
        return Listing(
            marketplace=self.name,
            listing_id=f"{shopid}.{itemid}",
            title=b.get("name", ""),
            price=float(b.get("price") or 0) / 100000.0,  # Shopee usa micros
            query=query,
            currency=b.get("currency", "BRL"),
            sold_quantity=int(b.get("historical_sold") or b.get("sold") or 0),
            available_quantity=int(b.get("stock") or 0),
            seller_id=str(shopid or ""),
            seller_name=b.get("shop_location", "") or "",
            rating=round(float(rating), 2) if rating else None,
            reviews=int(reviews or 0),
            free_shipping=False,
            permalink=permalink,
            thumbnail=(f"https://cf.shopee.com.br/file/{b.get('image')}"
                       if b.get("image") else ""),
        )
