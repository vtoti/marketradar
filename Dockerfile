FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# dependências primeiro (cache de camadas)
COPY requirements.txt .
RUN pip install -r requirements.txt

# código
COPY . .

# dados persistentes (montados como volume no compose)
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8501

# healthcheck do Streamlit
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').read()==b'ok' else 1)" || exit 1

# padrão: dashboard. O serviço 'scheduler' sobrescreve o command no compose.
CMD ["streamlit", "run", "app/Home.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
