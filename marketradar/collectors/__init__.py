"""Coletores de marketplaces."""
from .base import Listing, BaseCollector
from .mercadolivre import MercadoLivreCollector          # API oficial (requer parceria)
from .mercadolivre_web import MercadoLivreWebCollector    # scraping via navegador (PC)
from .shopee import ShopeeCollector

COLLECTORS = {
    "mercadolivre": MercadoLivreWebCollector,   # padrão: scraping (funciona sem parceria)
    "mercadolivre_api": MercadoLivreCollector,  # reservado p/ acesso de parceiro futuro
    "shopee": ShopeeCollector,
}


def get_collector(name: str, **kw) -> BaseCollector:
    if name not in COLLECTORS:
        raise ValueError(f"Marketplace desconhecido: {name}. "
                         f"Opções: {list(COLLECTORS)}")
    return COLLECTORS[name](**kw)


__all__ = ["Listing", "BaseCollector", "MercadoLivreCollector",
           "ShopeeCollector", "COLLECTORS", "get_collector"]
