import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import math

from core_logic import (
    get_proy, optimizar_alineacion, ejecutar_monte_carlo_dual, 
    llamar_gemini, formatear_roster_df, cargar_nflverse, 
    calc_prob, obtener_info_hc, consultar_clima, MI_EQUIPO_NOMBRE,
    calcular_drift_probabilidad, generar_comparativa_side_by_side,
    generar_heatmap_vulnerabilidad, simular_oraculo_ros, evaluar_trade,
    escanear_handcuffs, generar_game_scripts, obtener_mejores_waivers,
    obtener_noticias_nfl, empaquetar_estado_liga_para_gemini, evaluar_trade_interactivo
)

COLOR_MIO = "#4A90E2"
COLOR_RIV = "#E94B3C"

def render_tab_roster(datos, mi_roster, riv_start, riv_nom):
    st.header("📋 Mi Roster y Auditoría Táctica")
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
        m_pts, r_
