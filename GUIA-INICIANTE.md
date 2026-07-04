# 🟢 Guia para iniciantes — colocar o Radar de Mercado no ar

Feito para quem **nunca** usou terminal, Docker ou servidor. Vá com calma, um
passo de cada vez. Domínio usado: **gsvecomm.tech**.

## Dicionário rápido (leia 1 min)
- **VPS**: um computador da Hostinger, ligado 24h, que você controla pela internet.
- **Terminal**: uma tela preta onde você digita comandos (em vez de clicar).
- **Comando**: uma linha de texto que você cola e aperta Enter.
- **DNS**: a "lista telefônica" da internet — liga seu domínio ao número (IP) do VPS.
- **Docker**: programa que empacota o Radar e faz ele rodar sozinho.
- **HTTPS / cadeado**: o site abrir seguro, com `https://`.

> 💡 Regra de ouro: **copie o comando, cole no terminal, aperte Enter, espere
> terminar.** Para colar no terminal, geralmente é `Ctrl+Shift+V` ou clique com
> o botão direito.

---

## PARTE A — Coisas no navegador (do seu PC)

### Passo 1 — Ligar o domínio ao VPS (DNS)
1. Descubra o **IP do seu VPS**: painel da Hostinger → **VPS** → seu servidor →
   o IP aparece no topo (algo como `191.101.x.x`). Anote.
2. Vá onde você gerencia o domínio `gsvecomm.tech` (se comprou na Hostinger:
   painel → **Domínios** → **Zona DNS**).
3. Crie um registro assim:
   - **Tipo:** A
   - **Nome/Host:** `@`
   - **Aponta para / Valor:** o IP do VPS
   - **TTL:** deixe o padrão
4. Salve. **Pronto, agora espere** (pode levar de minutos a algumas horas).
   - Para testar: abra https://dnschecker.org, digite `gsvecomm.tech`, escolha
     tipo **A**. Quando aparecer o IP do seu VPS, o DNS está pronto.

### Passo 2 — Criar o aplicativo no Mercado Livre
1. Acesse https://developers.mercadolivre.com.br e faça login com sua conta ML.
2. Vá em **Suas aplicações** → **Criar nova aplicação**.
3. Preencha o nome. No campo **URIs de redirect**, cole exatamente:
   ```
   https://gsvecomm.tech
   ```
4. Salve. A tela vai mostrar um **Client ID** (número) e um **Client Secret**
   (código secreto). **Copie os dois** para um bloco de notas. Você usa no Passo 7.

---

## PARTE B — No terminal do VPS

### Passo 3 — Abrir o terminal do VPS (sem instalar nada)
1. Painel da Hostinger → **VPS** → seu servidor.
2. Procure o botão **"Browser terminal"** (terminal no navegador) e clique.
3. Abre uma tela preta já conectada ao seu servidor. É aqui que você trabalha.
   - (Se pedir usuário, é `root` e a senha que você definiu ao criar o VPS.)

### Passo 4 — Conferir o Docker
Cole e aperte Enter:
```bash
docker --version && docker compose version
```
- Se aparecerem duas versões → ótimo, siga.
- Se der "command not found", cole isto e espere terminar (1–2 min):
```bash
curl -fsSL https://get.docker.com | sh
```

### Passo 5 — Abrir as "portas" (firewall)
Cole tudo de uma vez e Enter:
```bash
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```
> Também no painel da Hostinger: **VPS → Firewall** → garanta que as portas
> **80** e **443** estão liberadas.

### Passo 6 — Baixar o Radar no servidor
Você vai trazer o programa para dentro do VPS. O jeito mais simples é pelo
GitHub (o código não tem segredos — suas senhas ficam só no VPS).
```bash
apt install -y git
git clone https://github.com/SEU_USUARIO/marketradar.git
cd marketradar
```
> Se você ainda não tem o código no GitHub, veja a seção **"Como subir para o
> GitHub sem terminal"** no fim deste guia (usa o programa GitHub Desktop, só
> com botões).

### Passo 7 — Preencher suas senhas (arquivo .env)
1. Crie o arquivo a partir do modelo:
```bash
cp .env.deploy.example .env
```
2. Abra para editar (o editor se chama **nano**):
```bash
nano .env
```
3. Troque só o que estiver em MAIÚSCULAS. Use as setas do teclado para andar:
   - `ACME_EMAIL=` → seu e-mail
   - `APP_PASSWORD=` → invente uma senha forte (é a senha do seu painel)
   - `ML_CLIENT_ID=` → o Client ID do Passo 2
   - `ML_CLIENT_SECRET=` → o Client Secret do Passo 2
   - `DOMAIN` e `ML_REDIRECT_URI` já vêm com `gsvecomm.tech` — não mexa.
4. Salvar e sair do nano:
   - Aperte **Ctrl + O**, depois **Enter** (salva).
   - Aperte **Ctrl + X** (sai).

### Passo 8 — Ligar o Radar
Cole e Enter:
```bash
chmod +x deploy.sh
./deploy.sh
```
Vai baixar e montar tudo (demora alguns minutos na 1ª vez). No fim aparece uma
mensagem com "Pronto! Acesse: https://gsvecomm.tech".
- O cadeado HTTPS pode levar ~1 minuto para ficar pronto.
- Para ver se está tudo de pé:
```bash
docker compose ps
```
Os três (**caddy**, **web**, **scheduler**) devem aparecer como *running*.

---

## PARTE C — Usar

### Passo 9 — Entrar no painel
Abra no navegador: **https://gsvecomm.tech**
Vai pedir a senha (`APP_PASSWORD` que você criou). Entrou? 🎉

### Passo 10 — Conectar sua conta do Mercado Livre (uma vez só)
1. No terminal do VPS, cole:
```bash
docker compose exec web python mlauth.py url
```
2. Ele imprime um **link**. Copie, abra no navegador, faça login no ML e clique
   em **Autorizar**.
3. O navegador vai para um endereço tipo `https://gsvecomm.tech/?code=TG-1234...`.
   Copie tudo que vem depois de `code=`.
4. Volte ao terminal e cole (trocando pelo seu código):
```bash
docker compose exec web python mlauth.py exchange TG-1234...
```
Aparecendo "Tokens salvos", pronto — daqui pra frente renova sozinho.

### Passo 11 — Buscar dados de verdade
No terminal:
```bash
docker compose exec web python collect_job.py --add "fone bluetooth" "garrafa termica"
docker compose exec web python collect_job.py
```
Agora atualize o painel no navegador: as páginas 🔎 e 🏆 já mostram dados reais.
A partir de hoje ele coleta sozinho todo dia. **Terminou!**

---

## Comandos úteis do dia a dia
```bash
docker compose ps            # ver se está tudo ligado
docker compose logs -f web   # ver o que o painel está fazendo (Ctrl+C sai)
docker compose restart       # reiniciar tudo
docker compose up -d --build # aplicar uma atualização do código
```

## Como subir o código para o GitHub (clique a clique) — para o Passo 6

**1. Criar conta no GitHub**
- Acesse https://github.com → **Sign up**. Informe e-mail, senha e um nome de
  usuário (guarde esse usuário — vira parte do endereço do seu código).
- Confirme o e-mail que o GitHub enviar.

**2. Instalar o GitHub Desktop**
- Acesse https://desktop.github.com → **Download for Windows** → instale.
- Ao abrir, clique **Sign in to GitHub.com** e entre com a conta do passo 1.
- Em "Configure Git", pode clicar **Continue** e depois **Finish**.

**3. Adicionar a pasta do Radar**
- Menu **File → Add local repository**.
- Clique **Choose...** e selecione a pasta:
  `C:\Users\SEU_USUARIO\Documents\VITOR\Claude\marketradar`
- Vai aparecer o aviso *"This directory does not appear to be a Git
  repository"* com um link **create a repository**. Clique nesse link.

**4. Criar o repositório**
- Na janela que abre, deixe o **Name** como `marketradar`.
- Não precisa mexer em mais nada (o `.gitignore` já existe no projeto).
- Clique **Create Repository**.

**5. Fazer o primeiro "commit"** (salvar uma versão)
- No canto inferior esquerdo, no campo **Summary**, escreva algo como
  `primeira versao`.
- Clique no botão azul **Commit to main**.
- 👀 Confira na lista de arquivos que **NÃO** aparecem `.env`, `.venv` nem
  `ml_tokens.json` — eles são ignorados de propósito (suas senhas ficam fora).

**6. Publicar na internet**
- Clique no botão **Publish repository** (no topo).
- **DESMARQUE** a opção *"Keep this code private"* — deixando público, o
  servidor baixa o código sem precisar de senha. (Pode ficar público com
  tranquilidade: não há segredos no código.)
- Clique **Publish repository**.

**7. Pegar o endereço para o Passo 6**
- Menu **Repository → View on GitHub** (abre no navegador).
- O endereço será `https://github.com/SEU_USUARIO/marketradar`.
- No Passo 6, o comando fica:
  ```bash
  git clone https://github.com/SEU_USUARIO/marketradar.git
  ```

**Depois, para enviar atualizações do código:** faça a mudança na pasta, volte
ao GitHub Desktop, escreva um Summary, clique **Commit to main** e depois
**Push origin**. No VPS, rode `git pull` e `docker compose up -d --build`.

## Se algo der errado
- **Site não abre / erro de certificado:** o DNS (Passo 1) ainda não propagou,
  ou as portas 80/443 estão fechadas no firewall do painel. Espere e tente
  `./deploy.sh` de novo.
- **Aparece "403" do Mercado Livre:** refaça o Passo 10.
- **Shopee vem vazio:** é esperado no VPS; comece só com Mercado Livre.
- **Travou/perdido:** rode `docker compose ps` e me mande o que aparecer.
