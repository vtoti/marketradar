"""Atualização & Agendamento — botão de atualizar e coleta diária."""
import _shared  # noqa: F401
from _shared import num, marketplace_picker

import pandas as pd
import streamlit as st

from marketradar import jobs
from marketradar.storage import db

st.set_page_config(page_title="Atualização & Agendamento", page_icon="🔄",
                   layout="wide")
_shared.login_gate()
st.title("🔄 Atualização & Agendamento")
st.caption("Atualize os dados sob demanda ou deixe a coleta diária rodando sozinha.")

db.init_db()

# ------------------------------------------------------------------ atualizar
st.subheader("Atualizar agora")
last = db.last_job_run()
c1, c2 = st.columns([1, 2])
with c1:
    limite = st.number_input("Anúncios por termo", 10, 200, 60, step=10)
    atualizar = st.button("🔄 Atualizar agora", type="primary",
                          use_container_width=True)
with c2:
    if last:
        st.metric("Última atualização", (last["finished_at"] or "")[:19].replace("T", " "))
        st.write(f"{'✅' if last['ok'] else '⚠️'} {last['termos']} termos · "
                 f"{last['anuncios']} anúncios coletados ({last['origem']})")
    else:
        st.info("Nenhuma coleta em lote ainda. Clique em **Atualizar agora** "
                "ou registre a tarefa diária abaixo.")

terms = jobs.tracked_terms()
if atualizar:
    if not terms:
        st.warning("Nenhum termo monitorado. Adicione termos na seção abaixo primeiro.")
    else:
        bar = st.progress(0.0, "Iniciando...")

        def prog(i, total, term):
            bar.progress(i / total, f"[{i}/{total}] {term}")

        res = jobs.run_daily(limit=int(limite), origem="manual", progress=prog)
        bar.empty()
        if res["ok"]:
            st.success(f"Atualizado: {res['termos']} termos, {res['anuncios']} "
                       f"anúncios em {res['duracao_s']}s.")
        else:
            st.warning(f"Concluído com falhas em alguns termos "
                       f"({res['anuncios']} anúncios). Veja o detalhe abaixo.")
            st.json(res["detalhe"])
        st.rerun()

st.divider()

# --------------------------------------------------------- termos monitorados
st.subheader("Termos monitorados")
st.caption("Estes termos são recoletados a cada atualização e pela tarefa diária. "
           "Toda busca feita nas outras páginas também entra aqui automaticamente.")

with st.form("add_term"):
    a, b, c = st.columns([3, 2, 1])
    with a:
        novo = st.text_input("Adicionar termo", placeholder="ex: caneca térmica")
    with b:
        mps = marketplace_picker(default=("mercadolivre",), key="mp_track")
    with c:
        st.write("")
        addbtn = st.form_submit_button("➕ Adicionar")
    if addbtn and novo and mps:
        jobs.add_tracked_term(novo, mps)
        st.success(f"'{novo}' adicionado ao monitoramento.")
        st.rerun()

if terms:
    df = pd.DataFrame([{"Termo": t["term"],
                        "Marketplaces": ", ".join(t["marketplaces"])} for t in terms])
    st.dataframe(df, use_container_width=True, hide_index=True)

    wl = db.get_watchlist("termo")
    if not wl.empty:
        rm = st.selectbox("Remover termo monitorado (explícito)",
                          ["—"] + wl["ref"].tolist())
        if st.button("Remover termo") and rm != "—":
            wid = int(wl[wl["ref"] == rm]["id"].iloc[0])
            db.remove_watch(wid)
            st.rerun()
else:
    st.info("Nenhum termo monitorado ainda.")

st.divider()

# ------------------------------------------------------------- histórico jobs
st.subheader("Histórico de coletas")
runs = db.list_job_runs(30)
if runs.empty:
    st.info("Sem execuções registradas.")
else:
    runs = runs.copy()
    runs["ok"] = runs["ok"].map({1: "✅", 0: "⚠️"})
    st.dataframe(runs, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------- agendamento
st.subheader("⏱️ Agendar coleta diária (Windows)")
st.markdown(
    """
Para o Radar coletar sozinho todo dia (essencial para tendência e momentum),
registre a tarefa no **Agendador de Tarefas do Windows**. No PowerShell, dentro
da pasta do projeto:

```powershell
# registrar (todo dia às 08:00)
.\\register_task.ps1

# horário/limite personalizados
.\\register_task.ps1 -Time "07:30" -Limit 80

# testar imediatamente
Start-ScheduledTask -TaskName "RadarDeMercado-ColetaDiaria"

# remover
.\\register_task.ps1 -Unregister
```

A tarefa roda `collect_job.py`, que atualiza todos os termos monitorados acima.
"""
)
