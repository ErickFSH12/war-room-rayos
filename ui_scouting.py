import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import math
from core_logic import (
    get_proy, ejecutar_monte_carlo_dual, formatear_roster_df, 
    cargar_nflverse, optimizar_alineacion, llamar_gemini
)

COLOR_MIO = "#4A90E2"
COLOR_RIV = "#E94B3C"

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

    # --- PARTE 2: MASTERMIND AUTO-OPTIMIZADOR ---
    st.subheader("🧠 Piloto Automático Mastermind (Monte Carlo)")
    st.write("Deja que la IA escanee tu banca y encuentre la alineación matemáticamente perfecta.")
    
    col_btn, col_res = st.columns([1, 2])
    
    with col_btn:
        st.info("El algoritmo iterará sobre todas las combinaciones posibles de tu roster actual.")
        auto_simular = st.button("🚀 Ejecutar Optimización Máxima", use_container_width=True)

    with col_res:
        if auto_simular:
            with st.spinner("Mastermind calculando permutaciones de roster..."):
                # 1. Encontrar la mejor alineación matemática
                opt_start, cambios = optimizar_alineacion(mi_roster['starters'], banca_ids, datos['players_db'], datos['proy'], datos['reales'])
                
                if not cambios:
                    st.success("✅ **Sistemas Óptimos:** Tu alineación actual es la mejor configuración matemática posible. No toques tu app de Sleeper.")
                else:
                    # 2. Correr Monte Carlo para medir el impacto real
                    prob_base, _, _, _ = ejecutar_monte_carlo_dual(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)
                    prob_sim, _, _, _ = ejecutar_monte_carlo_dual(opt_start, riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)
                    delta = round(prob_sim - prob_base, 1)
                    
                    st.error("🚨 **Se encontraron fugas de probabilidad en tu alineación inicial.**")
                    
                    c_m1, c_m2, c_m3 = st.columns(3)
                    c_m1.metric("Probabilidad Original", f"{prob_base}%")
                    c_m2.metric("Nueva Probabilidad", f"{prob_sim}%")
                    c_m3.metric("Impacto Neto", f"{'+' if delta >= 0 else ''}{delta}%", delta=f"{delta}%")
                    
                    # 3. Gemini redacta la orden de ejecución
                    cambios_texto = "\n".join(cambios)
                    prompt = f"""
                    Soy el mánager de un equipo de Fantasy Football. 
                    Mi motor matemático detectó que debo hacer estos cambios urgentes en mi alineación titular:
                    {cambios_texto}
                    
                    Al hacer estos cambios, mi probabilidad de ganar sube {delta}%.
                    Redacta una instrucción militar, corta y directa ordenándome que abra la app de Sleeper y haga estos cambios ahora mismo para asegurar la victoria. Máximo 3 líneas.
                    """
                    orden_ia = llamar_gemini(prompt)
                    st.warning(f"🤖 **ORDEN DE EJECUCIÓN:** {orden_ia}")
                    
                    st.markdown("**👇 Cambios requeridos en Sleeper:**")
                    for c in cambios:
                        st.write(f"- {c}")

    st.divider()

    # --- PARTE 3: DESEMPEÑO HISTÓRICO (NFLVerse) ---
    st.header("📈 Desempeño Histórico (Mi Equipo)")
    df_nfl = cargar_nflverse()
    if not df_nfl.empty:
        mis_jugadores = [f"{datos['players_db'].get(str(pid), {}).get('first_name', '')} {datos['players_db'].get(str(pid), {}).get('last_name', '')}".strip() for pid in mi_roster['players']]
        col_name = 'player_display_name' if 'player_display_name' in df_nfl.columns else 'player_name'
        df_mis = df_nfl[df_nfl[col_name].isin(mis_jugadores)].copy()
        
        if not df_mis.empty:
            df_temporada = df_mis.groupby([col_name, 'season'])[['fantasy_points_ppr', 'passing_yards', 'rushing_yards', 'receiving_yards']].sum().reset_index()
            jugadores_con_datos = df_temporada[col_name].unique()
            cols = st.columns(2)
            
            for i, jugador in enumerate(jugadores_con_datos):
                df_jugador = df_temporada[df_temporada[col_name] == jugador]
                with cols[i % 2]:
                    st.subheader(f"🏈 {jugador}")
                    fig = px.bar(df_jugador, x="season", y="fantasy_points_ppr", text_auto=".1f", color_discrete_sequence=[COLOR_MIO])
                    fig.update_xaxes(type='category', title="")
                    fig.update_yaxes(title="Puntos PPR")
                    fig.update_layout(title="Producción Histórica", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=40, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    df_tabla = df_jugador.rename(columns={"season": "Temp", "fantasy_points_ppr": "Pts PPR", "passing_yards": "Yds Pase", "rushing_yards": "Yds Tierra", "receiving_yards": "Yds Aire"}).drop(columns=[col_name])
                    st.dataframe(df_tabla, hide_index=True, use_container_width=True)
                    st.divider()
        else:
            st.info("Sin datos históricos de NFLVerse para tus jugadores.")
