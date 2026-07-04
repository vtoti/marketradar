# 🚀 Deploy do Radar de Mercado — 11 passos

Guia rápido para colocar no ar num VPS (Hostinger) com domínio + HTTPS.
Referência completa: [README.md](README.md).

**Antes de começar, tenha em mãos:** IP e acesso root do VPS · seu domínio ·
conta em developers.mercadolivre.com.br.

---

### 1. DNS → aponte o domínio para o VPS
No painel de DNS, crie um registro **A**:

| Tipo | Nome | Valor |
|------|------|-------|
| A | `@` | `IP_DO_VPS` |

> Opcional: um registro A extra com nome `www` para o mesmo IP, se quiser que
> `www.gsvecomm.tech` também funcione (exigiria adicionar o host no Caddyfile).

Verifique do seu PC (o IP tem que ser o do VPS):
```
nslookup gsvecomm.tech
```
> ⚠️ Espere propagar antes do passo 7 (o HTTPS depende disso).

### 2. Conectar no VPS
```bash
ssh root@IP_DO_VPS
```

### 3. Docker + firewall
```bash
docker --version && docker compose version   # se faltar: curl -fsSL https://get.docker.com | sh
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```
> Libere 80/443 também no **firewall do painel da Hostinger**.

### 4. Enviar o projeto
**Git (recomendado):**
```bash
apt install -y git
git clone https://github.com/SEU_USUARIO/marketradar.git && cd marketradar
```
**Ou SFTP:** suba a pasta `marketradar` (sem `.venv`) com o WinSCP e `cd marketradar`.

### 5. Criar o app no Mercado Livre
Em developers.mercadolivre.com.br → criar aplicação. No **URI de redirect** ponha
`https://gsvecomm.tech`. Anote **Client ID** e **Client Secret**.

### 6. Configurar o `.env`
```bash
cp .env.deploy.example .env
nano .env     # troque DOMAIN, ACME_EMAIL, APP_PASSWORD, ML_CLIENT_ID/SECRET, ML_REDIRECT_URI
```
Salvar: `Ctrl+O`, `Enter`, `Ctrl+X`.

### 7. Subir tudo
```bash
chmod +x deploy.sh
./deploy.sh
```
Primeira vez: ~1 min para o certificado HTTPS.
```bash
docker compose ps               # caddy, web, scheduler = running/healthy
docker compose logs -f caddy    # "certificate obtained successfully"
```

### 8. Acessar
Abra **`https://gsvecomm.tech`** → login com a `APP_PASSWORD`. 🎉

### 9. Autorizar o Mercado Livre (uma vez)
```bash
docker compose exec web python mlauth.py url
# abra a URL, autorize, copie o "code" do redirect, e:
docker compose exec web python mlauth.py exchange TG-xxxxxxxx
docker compose exec web python mlauth.py status   # confere
```

### 10. Cadastrar termos e testar coleta
```bash
docker compose exec web python collect_job.py --add "fone bluetooth" "garrafa termica"
docker compose exec web python collect_job.py
```

### 11. Automação diária
Já roda sozinha às `RUN_HOUR`. Conferir:
```bash
docker compose logs scheduler   # "Próxima coleta em Xh"
```

---

## Manutenção
```bash
docker compose ps                  # status
docker compose logs -f web         # logs do dashboard
docker compose restart             # reiniciar
docker compose up -d --build       # aplicar atualização (após git pull)
docker compose down                # parar (dados ficam nos volumes)
# backup do banco:
docker compose exec web cp /app/data/marketradar.db /app/data/backup-$(date +%F).db
```

## Se der errado
- **Erro de certificado no log do Caddy** → DNS ainda não propagou, ou 80/443
  fechadas no firewall do painel.
- **502/página não abre** → veja `docker compose logs web`; confirme os 3
  contêineres em `docker compose ps`.
- **ML retorna 403** → refaça o passo 9 (`mlauth.py status` deve mostrar
  `tem_refresh: True`).
- **Shopee vazio/bloqueado** → esperado a partir do VPS; use só Mercado Livre
  por ora (fase 2 = proxy residencial).
