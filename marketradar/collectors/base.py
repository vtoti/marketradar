"""Modelo de dados normalizado e classe base dos coletores."""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional

import requests

import config


@dataclass
class Listing:
    """Um anúncio normalizado, comum a todos os marketplaces."""

    marketplace: str
    listing_id: str
    title: str
    price: float
    query: str = ""
    currency: str = "BRL"
    sold_quantity: int = 0          # vendas acumuladas (histórico)
    available_quantity: int = 0     # estoque
    condition: str = "new"
    seller_id: str = ""
    seller_name: str = ""
    rating: Optional[float] = None
    reviews: int = 0
    free_shipping: bool = False
    category_id: str = ""
    permalink: str = ""
    thumbnail: str = ""
    # --- sinais do scraping do site (frente pública do ML) ---
    original_price: Optional[float] = None   # preço "de" (antes do desconto)
    discount_pct: Optional[float] = None      # % de desconto anunciado
    is_bestseller: bool = False               # selo "MAIS VENDIDO"
    is_ad: bool = False                       # anúncio patrocinado
    position: int = 0                         # posição no ranking de busca
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def gmv(self) -> float:
        """Faturamento bruto acumulado estimado (preço x vendas)."""
        return round(self.price * self.sold_quantity, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["gmv"] = self.gmv
        return d


class BaseCollector:
    """Base com sessão HTTP, headers e rate limiting."""

    name = "base"

    def __init__(self, delay: float | None = None):
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

    def _get(self, url: str, params: dict | None = None,
             headers: dict | None = None, timeout: int = 20) -> requests.Response:
        resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
        if self.delay:
            time.sleep(self.delay)
        return resp

    def search(self, query: str, limit: int = 50) -> list[Listing]:  # pragma: no cover
        raise NotImplementedError
