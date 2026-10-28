import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import math
from core_logic import (
    get_proy, ejecutar_monte_carlo_dual, formatear_roster_df, 
    cargar_nflverse, COLOR_MIO, COLOR_RIV
)

def render_tab_scouting(datos, mi_roster, riv_start):
    st.header("📋 Auditoría de Roster & Histórico")
    
    # --- PARTE 1: FOTO ACTUAL DEL ROSTER ---
    df_titulares = formatear_roster_df(mi_roster['starters'], datos['players_db'], datos['proy'], datos['reales'], "Titular")
    banca_ids = [p for p in mi_roster['players'] if p not in mi_roster['starters']]
    df_banca = formatear_roster_df(banca_ids, datos['players_db'], datos['proy'], datos['reales'], "Banca/IR")
    
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.subheader("11 Inicial Actual")
        st.dataframe(df_titulares, use_container_width=True, hide_index=True)
        st.subheader("Profundidad (Banca)")
        st.dataframe(df_banca, use_container_width=True, hide_index=True)
    
    with col_t2:
        st.subheader("Radar Posicional")
        cats = ['QB', 'RB', 'WR', 'TE', 'K/DEF']
        def agrup(st_ids):
            pts = {c: 0 for c in cats}
            for pid in st_ids:
                pos = datos['players_db'].get(str(pid), {}).get('position', 'N/A')
                p = datos['reales'].get(str(pid), get_proy(str(pid), pos, datos['proy']))
                if pos in ['K', 'DEF']: pts['K/DEF'] += p
                elif pos in pts: pts[pos] += p
                elif pos == 'FB': pts['RB'] += p
            return [pts[c] for c in cats]
        m_pts, r_pts = agrup(mi_roster['starters']), agrup(riv_start)
        m_pts += m_pts[:1]; r_pts += r_pts[:1]
        angs = [n / float(len(cats)) * 2 * math.pi for n in range(len(cats))] + [0]
        
        fig_rad, ax_rad = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
        ax_rad.plot(angs, m_pts, color=COLOR_MIO, lw=2); ax_rad.fill(angs, m_pts, COLOR_MIO, alpha=0.2)
        ax_rad.plot(angs, r_pts, color=COLOR_RIV, lw=2); ax_rad.fill(angs, r_pts, COLOR_RIV, alpha=0.2)
        ax_rad.set_xticks(angs[:-1]); ax_rad.set_xticklabels(cats, size=10)
        st.pyplot(fig_rad)

    st.divider()

    # --- PARTE 2: SIMULADOR DE ALINEACIÓN ---
    st.subheader("🧪 Simulador de Alineación (Monte Carlo)")
    opciones_jugadores = {}
    for pid in mi_roster['players']:
        p = datos['players_db'].get(str(pid), {})
        proy = round(datos['proy'].get(str(pid), 0.0), 1)
        nom = f"{p.get('last_name', str(pid))} ({p.get('position', 'FLEX')}) - {proy} pts"
        opciones_jugadores[nom] = pid
        
    titulares_actuales = [nom for nom, pid in opciones_jugadores.items() if pid in mi_roster['starters'] and str(pid) != "0"]
    nuevos_titulares = st.multiselect("Arma tu alineación simulada:", options=list(opciones_jugadores.keys()), default=titulares
