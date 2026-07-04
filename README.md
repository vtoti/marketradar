# 📡 Radar de Mercado

Ferramenta de **inteligência de marketplaces** para e-commerce — no espírito do
Nubimetric e do AVantPro. Coleta anúncios do **Mercado Livre** e da **Shopee**,
calcula métricas de mercado, estima faturamento e ranqueia nichos por
**oportunidade** (alta demanda + baixa concorrência).

## O que ele faz (mapeado às ferramentas comerciais)

| Recurso | Como aparece aqui | Página |
|---|---|---|
| Análise de mercado de um termo/produto | Preço mín/mediano/máx, nº de vendedores, vendas acumuladas, faturamento estimado (GMV), % frete grátis, concentração | 🔎 Pesquisa de Mercado |
| Distribuição de preços & "faixa campeã" | Histograma de preços + dispersão preço × vendas | 🔎 Pesquisa de Mercado |
| Ranking de vendedores / share de mercado | Faturamento estimado por vendedor, HHI, share do líder, gráfico de pizza | 🔎 / 🏪 |
| Meu produto vs. concorrência | Posição do seu preço na curva do mercado, concorrentes diretos | 📦 Análise de Produtos |
| Estimativa de vendas/dia e faturamento mensal | Calculada a partir de 2+ snapshots do mesmo anúncio | 📦 / 🏪 |
| Descoberta de novos produtos | **Score de oportunidade 0–100** comparando vários nichos | 💡 Descoberta |
| **Detector de produtos vencedores** | Checklist validado por anúncio + score 0–100 + veredito | 🏆 Produtos Vencedores |
| Monitoramento de concorrentes | Watchlist + evolução de preço/estoque/vendas | 🏪 Concorrentes |

## Como as estimativas funcionam

- **Faturamento acumulado (GMV):** `preço × vendas acumuladas` de cada anúncio.
- **Velocidade de vendas (vendas/dia):** diferença de vendas acumuladas entre
  dois snapshots ÷ dias decorridos. Por isso o Radar guarda um histórico: **rode
  a mesma busca em dias diferentes** e a projeção mensal fica cada vez melhor.
- **Score de oportunidade:** média ponderada de demanda (35%), baixa concorrência
  (25%), mercado pulverizado/HHI (15%), brecha de satisfação (15%) e potencial de
  margem (10%). Ver `marketradar/analysis/opportunity.py`.

## Critérios validados de "produtos vencedores"

O detector (`marketradar/analysis/winning.py`) aplica a cada anúncio um checklist
com limiares configuráveis, sintetizados de fontes de mercado. Cada critério gera
um sub-score 0–100 e a nota final é a média ponderada.

| Critério | Padrão | Racional / fonte |
|---|---|---|
| **Demanda forte** | ≥ 100 vendas acum. | Volume de vendas consistente é o 1º filtro (Jungle Scout/Helium 10). |
| **Demanda × oferta** | vendas/vendedor alto | Núcleo do índice de oportunidade do Nubimetric: muita procura, poucos vendedores. |
| **Faixa de preço** | R$ 50–150 | Zona de impulso com margem — regra do 3x custo no dropshipping. |
| **Margem** | markup ≥ 3x / ≥ 30% líq. | Só ativa se você informar o custo do fornecedor. |
| **Concorrência batível** | ≤ 500 avaliações | Concorrente com poucas reviews = baixa barreira de entrada. |
| **Brecha de qualidade** | nota 3,3–4,6 | Nota mediana = clientes insatisfeitos = espaço para um produto melhor. |
| **Momentum** | tendência ≥ +10% | Procura sustentada/crescente, não sazonal (requer histórico de snapshots). |
| **Logística** | frete grátis | Fator direto do algoritmo do Mercado Livre (Full/frete grátis). |

**Veredito:** 🏆 Vencedor (≥75) · ✅ Forte candidato (≥60) · 🟡 Potencial (≥45) · 🔴 Pouco atrativo.

Todos os limiares são ajustáveis na barra lateral da página 🏆 e no `WinningCriteria`.

Fontes: [Nubimetrics — Oportunidades](https://academia.nubimetrics.com/br/oportunidades) ·
[Nubimetrics — Algoritmo do ML](https://academia.nubimetrics.com/br/algoritmo-mercado-livre) ·
[Jungle Scout vs Helium 10](https://www.junglescout.com/resources/articles/jungle-scout-vs-helium-10/) ·
[Cartpanda — Produto vencedor](https://cartpanda.com.br/blog/produto-vencedor-dropshipping) ·
[Go Smarter — Algoritmo do Mercado Livre](https://gosmarter.com.br/algoritmo-mercado-livre/).

## Instalação

```powershell
cd marketradar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # edite o .env
```

### Credenciais (importante)

Os marketplaces **protegem seus dados**. Sem credencial, a coleta é bloqueada:

- **Mercado Livre:** a API de busca exige um token OAuth (sem ele retorna HTTP 403).
  - **Uso rápido/local:** gere um *access token* de teste e coloque em
    `ML_ACCESS_TOKEN` (expira em ~6h).
  - **Uso contínuo/24-7 (recomendado):** configure o **refresh automático**:
    1. Crie um app grátis em <https://developers.mercadolivre.com.br>.
    2. No `.env`: `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`
       (idêntico ao cadastrado no app).
    3. Autorize uma vez:
       ```powershell
       python mlauth.py url            # abra a URL, logue e autorize
       python mlauth.py exchange <code>  # cole o code do redirect
       ```
    A partir daí o token é renovado sozinho (`marketradar/auth_ml.py`).
- **Shopee:** usa endpoints internos com anti-bot. Se a coleta vier vazia/bloqueada,
  copie o cabeçalho `Cookie` de uma sessão logada do navegador para `SHOPEE_COOKIE`.

> É a mesma dependência de acesso que ferramentas comerciais têm — elas mantêm
> credenciais/proxies rotativos por trás dos panos.

## Uso

**Dashboard (recomendado):**
```powershell
streamlit run app/Home.py
```
Abre em <http://localhost:8501>.

**Linha de comando:**
```powershell
python cli.py search "fone bluetooth" --marketplaces mercadolivre --limit 30
python cli.py niches "fone bluetooth" "garrafa termica" --marketplaces mercadolivre
```

**Teste de saúde (sem rede):**
```powershell
python selftest.py
```

## Atualização de dados (manual e automática)

O Radar guarda um **snapshot** a cada coleta. Ter vários snapshots do mesmo
anúncio é o que permite estimar velocidade de vendas, momentum e tendência —
por isso vale atualizar todo dia.

**Botão "🔄 Atualizar agora":** na página inicial e em *🔄 Atualização &
Agendamento*. Recoleta todos os **termos monitorados** (toda busca feita nas
outras páginas entra automaticamente na lista; você também pode adicionar termos
manualmente).

**Coleta diária automática (Windows):**
```powershell
# registrar para rodar todo dia às 08:00
.\register_task.ps1

# horário/limite personalizados
.\register_task.ps1 -Time "07:30" -Limit 80

# testar agora
Start-ScheduledTask -TaskName "RadarDeMercado-ColetaDiaria"

# remover
.\register_task.ps1 -Unregister
```
A tarefa executa `collect_job.py`, que atualiza todos os termos monitorados e
registra cada execução (visível no histórico do dashboard).

Pela linha de comando:
```powershell
python collect_job.py --add "fone bluetooth" "garrafa termica"  # monitorar termos
python collect_job.py --limit 60                                # coletar tudo agora
```

## Deploy 100% online (VPS + domínio + HTTPS)

Sobe 3 contêineres: **caddy** (HTTPS automático), **web** (dashboard) e
**scheduler** (coleta diária). Banco e tokens ficam em volume persistente.

**Pré-requisitos:** VPS Linux com Docker + um domínio cujo registro **A** aponte
para o IP do VPS, e portas **80/443** abertas no firewall.

```bash
# no servidor, dentro da pasta do projeto
cp .env.example .env
nano .env        # DOMAIN, APP_PASSWORD, ML_CLIENT_ID/SECRET, ACME_EMAIL, RUN_HOUR
./deploy.sh      # build + up + espera ficar saudável
```

O `deploy.sh` valida o `.env`, sobe tudo e imprime os próximos passos. O Caddy
emite o certificado Let's Encrypt sozinho (~1 min na primeira vez).

- Dashboard: `https://SEU_DOMINIO` (protegido por `APP_PASSWORD`).
- Autorize o Mercado Livre uma vez (o `ML_REDIRECT_URI` deve ser
  `https://SEU_DOMINIO`, cadastrado igual no app do ML):
  ```bash
  docker compose exec web python mlauth.py url
  docker compose exec web python mlauth.py exchange <code>
  ```
- Testar a coleta na hora: `docker compose exec web python collect_job.py`.
- Logs: `docker compose logs -f caddy` (HTTPS) · `... scheduler` (coletas).

| Peça | Local (Windows) | Online (VPS) |
|---|---|---|
| Acesso | localhost:8501 | `https://dominio` (Caddy) |
| Dashboard | `streamlit run` | serviço `web` |
| Agendador | `register_task.ps1` | serviço `scheduler` |
| Token ML | token estático | OAuth + refresh automático |
| Banco/tokens | pasta `data/` | volumes `mrdata` / `caddy_data` |

> **Shopee em nuvem:** o IP de datacenter costuma ser bloqueado. Para coleta
> confiável, use proxies residenciais ou uma API de scraping paga (fase 2).

## Arquitetura

```
marketradar/
├─ config.py                 # env, caminhos, constantes
├─ cli.py                    # interface de linha de comando
├─ mlauth.py                 # autorização OAuth do ML (uma vez)
├─ collect_job.py            # job de coleta em lote (Agendador de Tarefas)
├─ scheduler.py              # scheduler diário para nuvem/containers
├─ register_task.ps1         # registra/remove a tarefa diária no Windows
├─ Dockerfile / docker-compose.yml   # deploy online (web + scheduler)
├─ selftest.py               # teste de fumaça com dados sintéticos
├─ marketradar/
│  ├─ collectors/            # mercadolivre.py, shopee.py, base.py (modelo Listing)
│  ├─ storage/db.py          # SQLite: snapshots + watchlist + job_runs
│  ├─ analysis/              # metrics.py, opportunity.py, winning.py
│  ├─ auth_ml.py             # OAuth + refresh automático de token do ML
│  ├─ jobs.py                # termos monitorados + coleta diária
│  └─ service.py             # orquestra coleta + storage + análise
└─ app/                      # dashboard Streamlit (Home + 6 páginas, com login)
```

Camadas desacopladas: trocar/adicionar um marketplace = criar um novo coletor
que devolve `Listing`; toda a análise e o dashboard funcionam sem alteração.

## Próximos passos sugeridos

1. ✅ ~~Refresh automático do token do ML~~ — implementado (`auth_ml.py` + `mlauth.py`).
2. ✅ ~~Agendador de coleta diária~~ — Windows (`register_task.ps1`) e nuvem (`scheduler.py`).
3. ✅ ~~Deploy online~~ — `Dockerfile` + `docker-compose.yml` + login.
4. **Mais marketplaces** (Amazon via API paga tipo Keepa/Rainforest; Magalu).
5. **Alertas** de queda de preço do concorrente ou ruptura de estoque.
6. **Shopee confiável em nuvem** via proxies residenciais / API de scraping.
7. **Exportação** para Excel/Google Sheets.

## Aviso

Respeite os Termos de Uso e o `robots.txt` de cada marketplace e a LGPD.
Use APIs oficiais quando disponíveis; coleta de endpoints internos pode violar
termos e é frágil por natureza.
