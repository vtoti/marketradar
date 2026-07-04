# 🔀 HANDOFF — estado do projeto para continuar em outro PC

Atualizado: 2026-07-04. Leia isto + [CHECKLIST.md](CHECKLIST.md) para retomar.

## Visão geral
Radar de Mercado = clone estilo Nubimetric/AVantPro para Mercado Livre.
Decisão de arquitetura: **HÍBRIDO**
- **Coleta** roda no **PC** (Playwright/Chrome real + IP residencial) — único jeito
  de passar pelo anti-bot do ML.
- **Painel** (dashboard) roda no **VPS** em `https://gsvecomm.tech` (24/7, HTTPS).
- O PC coleta e **envia o banco** para o VPS (sync ainda a fazer).

## Fatos do ambiente
- Repo GitHub (público): `https://github.com/vtoti/marketradar`
- VPS Hostinger KVM2 Ubuntu, IP `76.13.229.106`, domínio `gsvecomm.tech`
- App Mercado Livre: Client ID `1993447427039992` (Secret fica só no `.env` do VPS)
- Dashboard já no ar (caddy+web+scheduler via docker compose).

## Descobertas importantes (limites reais do ML)
- API pública de busca: **bloqueada por política** (403 PolicyAgent).
- Scraping simples (requests): **bloqueado** (página "tráfego suspeito").
- **Playwright (Chrome real) no PC: FUNCIONA** — traz os resultados. ✅
- A frente pública do ML **NÃO mostra quantidade de vendas** nem nº de avaliações.
  → O tool virou "Radar de Preço/Concorrência/Mais Vendidos" (sem faturamento).
  → Proxy de demanda = selo "MAIS VENDIDO" + posição no ranking.

## ✅ O que já está pronto
- Coletor `marketradar/collectors/mercadolivre_web.py` (Playwright) — testado, traz
  título, preço, desconto, vendedor, nota, frete, selo "mais vendido", ad, posição.
- Novos campos no modelo `Listing` e no banco (`original_price`, `discount_pct`,
  `is_bestseller`, `is_ad`, `position`).
- `metrics.market_summary` e `seller_ranking` adaptados (sem vendas; usam preço,
  desconto, frete, nota, mais-vendidos, concorrência por nº de anúncios).
- Deploy no VPS com HTTPS, login, OAuth do ML com refresh automático.

## ⏳ O que FALTA (retomar aqui)
1. **Adaptar o resto da análise** ao "sem vendas":
   - `marketradar/analysis/winning.py`: trocar `_score_demanda` (usa `sold_quantity`)
     por sinal de `is_bestseller` + `position` + nota.
   - `marketradar/analysis/opportunity.py`: idem para `niche_score` (não usar vendas).
   - `selftest.py`: ajustar asserções que dependem de `vendas_totais`/velocidade.
   - Páginas do dashboard (`app/pages/*`): remover/ocultar "faturamento/vendas" e
     mostrar os novos sinais.
2. **Sync PC → VPS**: script que, após coletar, envia `data/marketradar.db` ao VPS
   via `scp` (configurar chave SSH PC→VPS sem senha).
3. **Ajustar o VPS**: trocar o volume `mrdata` por **bind mount** `./data` (para o
   scp escrever fácil) e **desligar o serviço `scheduler`** (coleta agora é no PC).
4. **Agendar no PC**: tarefa diária (Task Scheduler) rodando a coleta local.

## Como rodar/coletar no PC
```powershell
# na pasta do projeto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium     # baixa o Chrome do Playwright (~130MB)
# testar coleta:
python -c "from marketradar.collectors import get_collector as g; print(len(g('mercadolivre').search('fone bluetooth', limit=10)))"
```

## Continuar em OUTRO computador
1. Instalar Git (ou GitHub Desktop) e clonar: `git clone https://github.com/vtoti/marketradar.git`
2. Seguir "Como rodar/coletar no PC" acima (venv + requirements + playwright install).
3. O `.env` NÃO está no Git (tem segredos). No VPS ele já existe; no PC de coleta,
   crie um `.env` só se for rodar o dashboard localmente.
4. Abrir uma nova conversa com o assistente na pasta do projeto e apontar este
   HANDOFF.md — ele retoma a partir daqui.
