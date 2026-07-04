# ✅ Checklist final — do zero ao ar (siga de cima para baixo)

Domínio: **gsvecomm.tech** · Detalhes de cada item: [GUIA-INICIANTE.md](GUIA-INICIANTE.md)
Marque `[x]` conforme conclui. **Não pule a ordem.**

---

## 🔹 ETAPA 1 — Preparar o código (no seu PC)
- [ ] 1. Criar conta em **github.com** (anotar o usuário)
- [ ] 2. Instalar **GitHub Desktop** (desktop.github.com) e fazer login
- [ ] 3. **File → Add local repository** → escolher a pasta `marketradar` →
      clicar **create a repository** → **Create Repository**
- [ ] 4. Escrever `primeira versao` em Summary → **Commit to main**
- [ ] 5. **Publish repository** → **desmarcar** "Keep this code private" →
      **Publish**
- [ ] 6. Anotar o endereço: `https://github.com/SEU_USUARIO/marketradar`

## 🔹 ETAPA 2 — Domínio (no navegador)
- [ ] 7. Pegar o **IP do VPS** (painel Hostinger → VPS → topo da página)
- [ ] 8. No DNS do `gsvecomm.tech`, criar registro **A**: Nome `@` → o IP do VPS
- [ ] 9. Testar em **dnschecker.org** (tipo A) até aparecer o IP do VPS
      ⏳ *pode levar de minutos a horas — só siga quando aparecer*

## 🔹 ETAPA 3 — App do Mercado Livre (no navegador)
- [ ] 10. Em **developers.mercadolivre.com.br** → criar aplicação
- [ ] 11. URI de redirect = `https://gsvecomm.tech`
- [ ] 12. Copiar **Client ID** e **Client Secret** para um bloco de notas

## 🔹 ETAPA 4 — Servidor (terminal do VPS)
Abrir: painel Hostinger → VPS → **Browser terminal**. Colar cada bloco + Enter.

- [ ] 13. Conferir Docker:
      ```bash
      docker --version && docker compose version
      ```
      *(se faltar: `curl -fsSL https://get.docker.com | sh`)*
- [ ] 14. Abrir portas:
      ```bash
      ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
      ```
      *(e liberar 80/443 no Firewall do painel Hostinger)*
- [ ] 15. Baixar o código (troque SEU_USUARIO):
      ```bash
      apt install -y git
      git clone https://github.com/SEU_USUARIO/marketradar.git
      cd marketradar
      ```
- [ ] 16. Criar o arquivo de senhas:
      ```bash
      cp .env.deploy.example .env
      nano .env
      ```
- [ ] 17. No nano, preencher (MAIÚSCULAS): `ACME_EMAIL`, `APP_PASSWORD`,
      `ML_CLIENT_ID`, `ML_CLIENT_SECRET` → salvar com **Ctrl+O**, **Enter**,
      **Ctrl+X**
- [ ] 18. Ligar tudo:
      ```bash
      chmod +x deploy.sh
      ./deploy.sh
      ```
- [ ] 19. Conferir que subiu: `docker compose ps` → caddy, web, scheduler
      *running*

## 🔹 ETAPA 5 — Ativar e usar
- [ ] 20. Abrir **https://gsvecomm.tech** → entrar com a `APP_PASSWORD`
- [ ] 21. Conectar o Mercado Livre:
      ```bash
      docker compose exec web python mlauth.py url
      ```
      abrir o link, autorizar, copiar o `code` do redirect, e:
      ```bash
      docker compose exec web python mlauth.py exchange TG-SEU-CODIGO
      ```
- [ ] 22. Primeira coleta:
      ```bash
      docker compose exec web python collect_job.py --add "fone bluetooth"
      docker compose exec web python collect_job.py
      ```
- [ ] 23. Voltar ao site e ver os dados nas páginas 🔎 e 🏆 🎉

---

## 🆘 Se travar
- **Site não abre / erro de certificado** → volte ao item 9 (DNS) e confirme
  portas 80/443 no firewall do painel. Rode `./deploy.sh` de novo.
- **403 do Mercado Livre** → refaça o item 21.
- **Shopee vazio** → normal no VPS; use só Mercado Livre por enquanto.
- **Perdido** → rode `docker compose ps` e `docker compose logs web` e peça ajuda
  com o que apareceu.

## 🔁 Rotina depois de no ar
- Coleta diária: **automática** (serviço `scheduler`). Nada a fazer.
- Atualizar código: GitHub Desktop (**Commit** → **Push**) e no VPS:
  ```bash
  cd marketradar && git pull && docker compose up -d --build
  ```
