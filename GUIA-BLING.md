# 🧾 Guia — Criar o aplicativo no Bling (passo a passo)

Para a página **🧾 Pedidos Bling** funcionar, o Bling exige um "aplicativo"
cadastrado na sua conta — é ele que gera o **Client ID** e o **Client Secret**
usados na conexão OAuth. É de graça, leva ~5 minutos e só precisa ser feito
**uma vez**.

**Tenha em mãos:** login e senha da sua conta Bling (a mesma do ERP).

---

## Passo 1 — Entrar no portal de desenvolvedores

1. Abra **https://developer.bling.com.br**
2. Clique em **Entrar** (canto superior direito) e use o **mesmo login do seu
   Bling** (o portal é ligado à sua conta do ERP)
3. Se for a primeira vez, aceite os termos do portal

## Passo 2 — Criar o aplicativo

1. No painel, procure **Aplicativos** → **Criar aplicativo**
   (ou "Cadastrar novo aplicativo")
2. Preencha os dados básicos:

| Campo | O que colocar |
|---|---|
| **Nome do aplicativo** | `MarketRadar` (ou o nome que quiser) |
| **Descrição** | `Análise de margem dos pedidos de venda` |
| **Logo** | opcional, pode pular |
| **Link do site** | `https://gsvecomm.tech` |
| **Link de redirecionamento** | `https://gsvecomm.tech/Pedidos_Bling` |

> ⚠️ **O link de redirecionamento é o campo mais importante.** Tem que ser
> EXATAMENTE `https://gsvecomm.tech/Pedidos_Bling` — com `https`, com o `P` e o
> `B` maiúsculos, **sem barra no final**. Qualquer diferença gera o erro
> *"redirect_uri inválido"* na hora de autorizar.

## Passo 3 — Marcar os escopos (permissões)

Na seção de **escopos/permissões** do formulário, marque **somente leitura**:

- ✅ **Vendas → Pedidos de Venda** → *Visualizar / Leitura*
- ✅ **Cadastros (ou Suprimentos) → Produtos** → *Visualizar / Leitura*

Não marque permissões de escrita/alteração — o MarketRadar **só lê** seus
dados, nunca altera nada no ERP.

## Passo 4 — Salvar e copiar as credenciais

1. Clique em **Salvar/Criar**
2. Abra o aplicativo recém-criado e localize a seção de credenciais
   ("Dados do aplicativo")
3. Copie o **Client ID** e o **Client Secret**

> 🔒 O Client Secret é como uma senha: não mande por WhatsApp/e-mail e não
> poste em lugar público. Se vazar, gere um novo no portal (isso desconecta a
> integração até reautorizar).

## Passo 5 — Configurar no MarketRadar

**Opção A — pelo `.env` do VPS** (recomendado):

```bash
cd ~/marketradar
nano .env
```

Adicione (cole seus valores):

```
BLING_CLIENT_ID=cole_aqui_o_client_id
BLING_CLIENT_SECRET=cole_aqui_o_client_secret
BLING_REDIRECT_URI=https://gsvecomm.tech/Pedidos_Bling
```

Salve (`Ctrl+O`, `Enter`, `Ctrl+X`) e aplique:

```bash
docker compose up -d
```

**Opção B — pela tela**: abra **https://gsvecomm.tech** → página
**🧾 Pedidos Bling** → cole Client ID e Client Secret no formulário → **Salvar
credenciais**.

## Passo 6 — Autorizar (conectar sua conta)

1. Na página **🧾 Pedidos Bling**, clique em **🔗 Autorizar no Bling**
2. O Bling abre uma tela de consentimento — confira os escopos e **autorize**
3. Você volta automaticamente para a página, que mostra
   **✅ Bling autorizado com sucesso!** e o status **🟢 Conectado**

A partir daí a renovação do acesso é automática (o token de 6h renova sozinho;
o refresh token dura ~30 dias e se renova a cada uso).

## Passo 7 — Sincronizar e analisar

1. Escolha o período (padrão: últimos 30 dias)
2. **⟳ Sincronizar pedidos** — a barra mostra o progresso (baixa primeiro os
   custos dos produtos, depois os pedidos; ~100 pedidos ≈ 1 minuto por causa
   do limite de requisições do Bling)
3. Veja a margem real de cada pedido, o drill-down item a item e os alertas
   de **itens sem custo**

> 💡 Para a análise ficar completa, preencha o **preço de custo** dos produtos
> no cadastro do Bling. Alternativa: cadastre o produto (com o mesmo SKU) na
> página **💰 Engenharia de Preços**, e o custo local será usado.

---

## Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| **"redirect_uri inválido"** ao autorizar | O link de redirecionamento no app do Bling não bate 100% com `https://gsvecomm.tech/Pedidos_Bling`. Edite o app no portal e confira letra por letra. |
| **"invalid_client"** | Client ID/Secret colados com espaço ou trocados. Copie de novo. |
| **"state da autorização não confere"** | A autorização começou em outra aba/sessão. Clique de novo em **Autorizar no Bling** e conclua na mesma janela. |
| **HTTP 403 na sincronização** | Escopos não marcados no app. Edite o app no portal, marque Pedidos de Venda + Produtos (leitura) e **reautorize**. |
| **Itens "sem custo"** | O produto não tem *preço de custo* no Bling. Preencha lá (ou cadastre com SKU na Engenharia de Preços). |
| **Desconectou depois de ~30 dias sem uso** | O refresh token expirou. Clique em **Autorizar no Bling** de novo. |
