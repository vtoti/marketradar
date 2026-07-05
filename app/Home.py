"""Radar de Mercado — página inicial do dashboard."""
import _shared  # bootstrap de path  # noqa: F401
import streamlit as st

import config
from marketradar import jobs, auth_ml
from marketradar.storage import db

st.set_page_config(page_title="Radar de Mercado", page_icon="📡", layout="wide")
_shared.login_gate()
db.init_db()

st.title("📡 Radar de Mercado")
st.caption("Inteligência de marketplaces para e-commerce — Mercado Livre & Shopee")

st.markdown(
    """
Bem-vindo. Use o menu lateral para navegar:

- **🔎 Pesquisa de Mercado** — analise um nicho/termo: preços, concorrência,
  vendedores líderes e faturamento estimado.
- **📦 Análise de Produtos** — acompanhe *seus* produtos vs. o mercado e estime
  a velocidade de vendas dos concorrentes.
- **💡 Descoberta de Produtos** — compare vários nichos e ranqueie por
  **score de oportunidade** (alta demanda + baixa concorrência).
- **🏪 Concorrentes** — monitore vendedores e termos ao longo do tempo.
- **💰 Engenharia de Preços** — margem de contribuição real por produto e
  canal: custos, impostos, taxas de marketplace e rateio de fixos.
- **🧾 Pedidos Bling** — importe os pedidos do seu ERP e veja o lucro real
  de cada venda, pedido a pedido.
"""
)

bar1, bar2 = st.columns([1, 3])
with bar1:
    if st.button("🔄 Atualizar dados agora", type="primary", use_container_width=True):
        terms = jobs.tracked_terms()
        if not terms:
            st.warning("Nenhum termo monitorado ainda. Faça uma busca ou use a "
                       "página 🔄 Atualização & Agendamento.")
        else:
            p = st.progress(0.0, "Coletando...")
            res = jobs.run_daily(
                origem="manual",
                progress=lambda i, t, term: p.progress(i / t, f"[{i}/{t}] {term}"))
            p.empty()
            st.success(f"Atualizado: {res['termos']} termos, "
                       f"{res['anuncios']} anúncios.")
with bar2:
    _last = db.last_job_run()
    if _last:
        st.caption(f"Última atualização: {(_last['finished_at'] or '')[:19].replace('T',' ')} "
                   f"· {_last['anuncios']} anúncios ({_last['origem']})")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.subheader("Status da configuração")
    _ml = auth_ml.status()
    if _ml["tem_refresh"]:
        _exp = _ml["expira_em_min"]
        st.write("**Mercado Livre**: ✅ OAuth com refresh automático"
                 + (f" (token válido por ~{_exp:.0f} min)" if _exp and _exp > 0 else ""))
    elif _ml["tem_token"]:
        st.write("**Mercado Livre**: 🟡 token estático (sem refresh — "
                 "expira em ~6h). Rode `python mlauth.py` para 24/7.")
    else:
        st.write("**Mercado Livre**: ⚠️ sem token — a busca exige autenticação.")
    st.write("**Shopee**:",
             "✅ cookie configurado" if config.SHOPEE_COOKIE
             else "⚠️ sem cookie (a coleta pode ser bloqueada)")
    st.write("**Banco de dados**:", f"`{config.DB_PATH}`")

with col2:
    st.subheader("Buscas já coletadas")
    q = db.list_queries()
    if q.empty:
        st.info("Nenhuma coleta ainda. Comece pela **Pesquisa de Mercado**.")
    else:
        st.dataframe(q, use_container_width=True, hide_index=True)

st.divider()
st.caption("Dica: rode a mesma busca em dias diferentes para o Radar estimar a "
           "velocidade de vendas (vendas/dia) dos anúncios.")
