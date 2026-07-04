"""Coletores de marketplaces."""
from .base import Listing, BaseCollector
from .mercadolivre import MercadoLivreCollector
from .shopee import ShopeeCollector

COLLECTORS = {
    "mercadolivre": MercadoLivreCollector,
    "shopee": ShopeeCollector,
}


def get_collector(name: str, **kw) -> BaseCollector:
    if name not in COLLECTORS:
        raise ValueError(f"Marketplace desconhecido: {name}. "
                         f"Opções: {list(COLLECTORS)}")
    return COLLECTORS[name](**kw)


__all__ = ["Listing", "BaseCollector", "MercadoLivreCollector",
           "ShopeeCollector", "COLLECTORS", "get_collector"]
