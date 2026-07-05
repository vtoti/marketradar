"""Configuração central do Radar de Mercado.

Lê variáveis de ambiente (via .env) e expõe caminhos e constantes usadas
por coletores, armazenamento e dashboard.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv é opcional
    pass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "marketradar.db"

# --- Mercado Livre ---
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "").strip()
ML_SITE = os.getenv("ML_SITE", "MLB").strip() or "MLB"
# OAuth (para refresh automático — coleta 24/7)
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "").strip()
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "").strip()
ML_REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "https://localhost:8501").strip()
ML_REFRESH_TOKEN = os.getenv("ML_REFRESH_TOKEN", "").strip()
ML_TOKEN_FILE = DATA_DIR / "ml_tokens.json"

# --- Bling (ERP) — engenharia de preços / análise de pedidos ---
BLING_CLIENT_ID = os.getenv("BLING_CLIENT_ID", "").strip()
BLING_CLIENT_SECRET = os.getenv("BLING_CLIENT_SECRET", "").strip()
# Precisa bater com o "link de redirecionamento" cadastrado no app do Bling.
BLING_REDIRECT_URI = os.getenv(
    "BLING_REDIRECT_URI", "http://localhost:8501/Pedidos_Bling").strip()
BLING_TOKEN_FILE = DATA_DIR / "bling_tokens.json"

# --- Shopee ---
SHOPEE_REGION = os.getenv("SHOPEE_REGION", "br").strip() or "br"
SHOPEE_COOKIE = os.getenv("SHOPEE_COOKIE", "").strip()

# --- App / deploy ---
# Senha de acesso ao dashboard. Vazio = sem login (uso local).
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
# Hora (0–23) em que o scheduler roda a coleta diária.
RUN_HOUR = int(os.getenv("RUN_HOUR", "8"))
COLLECT_LIMIT = int(os.getenv("COLLECT_LIMIT", "60"))

# --- Rede ---
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
