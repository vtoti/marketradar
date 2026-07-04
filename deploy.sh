#!/usr/bin/env bash
# Deploy do Radar de Mercado no VPS (Docker + Caddy/HTTPS).
# Uso:  ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Verificando pré-requisitos..."
command -v docker >/dev/null || { echo "Docker não encontrado."; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose v2 não encontrado."; exit 1; }

if [ ! -f .env ]; then
  echo "Arquivo .env não existe. Criando a partir do exemplo..."
  cp .env.example .env
  echo ">> Edite o .env (DOMAIN, APP_PASSWORD, ML_CLIENT_ID/SECRET) e rode de novo."
  exit 1
fi

# valida presença das variáveis essenciais (sem sourcing, evita erro com
# caracteres especiais na senha)
grep -q '^DOMAIN=.\+' .env || { echo "Defina DOMAIN no .env"; exit 1; }
grep -q '^APP_PASSWORD=.\+' .env || { echo "Defina APP_PASSWORD no .env (segurança!)"; exit 1; }
DOMAIN=$(grep '^DOMAIN=' .env | cut -d= -f2-)

echo "==> Domínio: $DOMAIN"
echo "==> Subindo os containers (build)..."
docker compose up -d --build

echo "==> Aguardando o dashboard ficar saudável..."
for i in $(seq 1 30); do
  if docker compose exec -T web python -c \
     "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').read()==b'ok' else 1)" 2>/dev/null; then
    echo "   OK, dashboard respondendo."
    break
  fi
  sleep 2
done

echo
echo "==> Status:"
docker compose ps
echo
echo "Pronto! Acesse: https://$DOMAIN  (pode levar ~1 min para o certificado HTTPS)"
echo
echo "Próximo passo — autorizar o Mercado Livre uma única vez:"
echo "  docker compose exec web python mlauth.py url"
echo "  docker compose exec web python mlauth.py exchange <code>"
echo
echo "Testar a coleta agora:"
echo "  docker compose exec web python collect_job.py --add \"fone bluetooth\""
echo "  docker compose exec web python collect_job.py"
