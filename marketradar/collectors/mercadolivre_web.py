"""Coletor do Mercado Livre via navegador real (Playwright).

A API pública e o scraping simples são bloqueados pelo ML (política + anti-bot
"tráfego suspeito"). Um Chrome de verdade, a partir de um IP residencial,
passa pela verificação e renderiza os resultados. Este coletor roda no PC do
usuário (não no VPS).

Campos disponíveis na frente pública do ML (2026): título, preço (atual e "de"),
desconto, vendedor, nota, frete grátis, selo "MAIS VENDIDO", patrocinado e a
posição no ranking. NÃO há quantidade de vendas (o ML removeu do site).

Requer: pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import re

import config
from .base import BaseCollector, Listing

SEARCH_BASE = "https://lista.mercadolivre.com.br/"

_JS = r"""
() => {
  const cards = document.querySelectorAll('.poly-card');
  const txt = (el, sel) => { const e = el.querySelector(sel); return e ? e.innerText.trim() : null; };
  const money = (el, sel) => {
    const box = el.querySelector(sel); if (!box) return null;
    const fr = box.querySelector('.andes-money-amount__fraction');
    const ce = box.querySelector('.andes-money-amount__cents');
    if (!fr) return null;
    const cents = ce ? ce.innerText.replace(/\D/g,'') : '0';
    return parseFloat(fr.innerText.replace(/\./g,'') + '.' + (cents || '0'));
  };
  const out = [];
  cards.forEach((c, idx) => {
    const titleEl = c.querySelector('.poly-component__title');
    const link = c.querySelector('.poly-component__title a, a.poly-component__title, a');
    const ratingRaw = txt(c, '.poly-component__review-compacted') || '';
    const rm = ratingRaw.match(/([0-9])[.,]([0-9])/);
    const ship = (txt(c, '.poly-component__shipping-v2') || txt(c, '.poly-component__shipping') || '');
    const label = (txt(c, '.poly-component__poly-label') || '').toUpperCase();
    const full = c.innerText || '';
    out.push({
      title: titleEl ? titleEl.innerText.trim() : (txt(c, 'a') || ''),
      href: link ? link.href : null,
      price: money(c, '.poly-price__current'),
      original: money(c, '.andes-money-amount--previous'),
      seller: txt(c, '.poly-component__seller'),
      rating: rm ? parseFloat(rm[1] + '.' + rm[2]) : null,
      free_shipping: /gr[aá]tis/i.test(ship),
      bestseller: label.includes('MAIS VENDIDO') || /MAIS VENDIDO/i.test(full),
      is_ad: !!c.querySelector('.poly-component__ads-promotions'),
      position: idx + 1,
    });
  });
  return out;
}
"""


class MercadoLivreWebCollector(BaseCollector):
    name = "mercadolivre"

    def __init__(self, headless: bool = True, wait_ms: int = 9000, **kw):
        super().__init__(**kw)
        self.headless = headless
        self.wait_ms = wait_ms

    def search(self, query: str, limit: int = 50) -> list[Listing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright não instalado. Rode: pip install playwright && "
                "python -m playwright install chromium") from e

        url = SEARCH_BASE + re.sub(r"\s+", "-", query.strip())
        raw = []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(
                user_agent=config.USER_AGENT, locale="pt-BR",
                viewport={"width": 1366, "height": 768})
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="commit", timeout=60000)
                page.wait_for_timeout(self.wait_ms)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                if "account-verification" in page.url or "suspicious-traffic" in page.content():
                    raise ConnectionError(
                        "ML mostrou verificação anti-robô. Tente novamente, use "
                        "headless=False, ou rode de um IP residencial.")
                raw = page.evaluate(_JS)
            finally:
                browser.close()

        listings, seen = [], set()
        for r in raw:
            item_id = self._item_id(r.get("href"))
            key = item_id or r.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            listings.append(self._to_listing(r, query, item_id))
            if len(listings) >= limit:
                break
        return listings

    @staticmethod
    def _item_id(href: str | None) -> str:
        if not href:
            return ""
        m = re.search(r"MLB-?\d{6,}", href)
        return m.group(0).replace("-", "") if m else ""

    def _to_listing(self, r: dict, query: str, item_id: str) -> Listing:
        price = float(r.get("price") or 0)
        original = r.get("original")
        discount = None
        if original and price and original > price:
            discount = round((1 - price / original) * 100, 1)
        permalink = (f"https://www.mercadolivre.com.br/p/{item_id}"
                     if item_id else (r.get("href") or ""))
        return Listing(
            marketplace=self.name,
            listing_id=item_id or (r.get("title", "")[:40]),
            title=r.get("title", ""),
            price=price,
            query=query,
            seller_name=r.get("seller") or "",
            seller_id=(r.get("seller") or "").lower(),
            rating=r.get("rating"),
            free_shipping=bool(r.get("free_shipping")),
            permalink=permalink,
            original_price=float(original) if original else None,
            discount_pct=discount,
            is_bestseller=bool(r.get("bestseller")),
            is_ad=bool(r.get("is_ad")),
            position=int(r.get("position") or 0),
        )
