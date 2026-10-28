import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core_logic import (
    ejecutar_monte_carlo_dual, optimizar_alineacion, llamar_gemini, 
    calcular_drift_probabilidad, generar_comparativa_side_by_side, 
    generar_game_scripts, MI_EQUIPO_NOMBRE
)

COLOR_MIO = "#4A90E2"
COLOR_RIV = "#E94B3C"

def render_tab_live(datos, mi_roster, riv_start, riv_nom):
    # (Toda tu lógica Live que hicimos hace un momento)
    m_aseg = sum([datos['reales'][str(p)] for p in mi_roster['starters'] if str(p) in datos['reales']])
    m_rest = sum([datos['proy'].get(str(p), 0.0) for p in mi_roster['starters'] if str(p) not in datos['reales']])
    r_aseg = sum([datos['reales'][str(p)] for p in riv_start if str(p) in datos['reales']])
    r_rest = sum([datos['proy'].get(str(p), 0.0) for p in riv_start if str(p) not in datos['reales']])
    pts_mios, pts_riv = round(m_aseg + m_rest, 1), round(r_aseg + r_rest, 1)
    
    opt_start, cambios = optimizar_alineacion(mi_roster['starters'], [p for p in mi_roster['players'] if p not in mi_roster['starters']], datos['players_db'], datos['proy'], datos['reales'])
    prob, med, sm, sr = ejecutar_monte_carlo_dual(opt_start, riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)

    st.markdown(f"<h1 style='text-align: center; color: white; background-color: #111111; padding: 20px; border-radius: 10px; border: 2px solid {COLOR_MIO};'>🔥 GAMEDAY WARS: SEMANA {datos['semana']} 🔥</h1>", unsafe_allow_html=True)
    st.write("")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.markdown(f"<h3 style='text-align: center; color: {COLOR_MIO}; margin-bottom: 0px;'>{MI_EQUIPO_NOMBRE}</h3>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; font-size: 70px; margin-top: 0px;'>{pts_mios}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: gray;'>Asegurados: {round(m_aseg, 1)} pts</p>", unsafe_allow_html=True)
        
    with c2:
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta", value = prob,
            delta = {'reference': 50, 'position': "top", 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
            title = {'text': "⚡ PROBABILIDAD DE VICTORIA ⚡", 'font': {'size': 20, 'color': "gray"}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "white"},
                'bar': {'color': COLOR_MIO},
                'bgcolor': "rgba(0,0,0,0.1)", 'borderwidth': 2, 'bordercolor': "gray",
                'steps': [{'range': [0, 45], 'color': "rgba(233, 75, 60, 0.4)"}, {'range': [45, 55], 'color': "rgba(255, 204, 0, 0.4)"}, {'range': [55, 100], 'color': "rgba(74, 144, 226, 0.4)"}],
                'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': prob}
            }
        ))
        fig_gauge.update_layout(height=350, margin=dict(l=20, r=20, t=50, b=10), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)

    with c3:
        st.markdown(f"<h3 style='text-align: center; color: {COLOR_RIV}; margin-bottom: 0px;'>{riv_nom}</h3>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='text-align: center; font-size: 70px; margin-top: 0px;'>{pts_riv}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: gray;'>Asegurados: {round(r_aseg, 1)} pts</p>", unsafe_allow_html=True)

    st.divider()
    col_mc, col_ai = st.columns([3, 2])
    
    with col_mc:
        st.markdown("### 🧬 Simulación de Escenarios")
        fig_mc = go.Figure()
        fig_mc.add_trace(go.Histogram(x=sm, name='Rayos', marker_color=COLOR_MIO, opacity=0.75, nbinsx=45))
        fig_mc.add_trace(go.Histogram(x=sr, name=riv_nom, marker_color=COLOR_RIV, opacity=0.75, nbinsx=45))
        fig_mc.update_layout(barmode='overlay', plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01), margin=dict(t=10))
        st.plotly_chart(fig_mc, use_container_width=True)

    with col_ai:
        st.markdown("### 📡 Central Táctica")
        if cambios: 
            st.error("⚠️ **¡ALERTA DE ALINEACIÓN!**")
            for c in cambios: st.warning(c)
        else: st.success("✅ **Sistemas Óptimos**")
            
        st.markdown("#### 🚨 Auditoría de Fugas")
        if st.button("🧠 ¿Por qué mi banca suma más?"):
            with st.spinner("Diagnosticando fuga..."):
                tit_str = [f"{datos['players_db'].get(str(pid), {}).get('last_name', '')}: {round(datos['reales'].get(str(pid), datos['proy'].get(str(pid), 0.0)),1)}" for pid in mi_roster['starters'] if str(pid) != "0"]
                ban_str = [f"{datos['players_db'].get(str(pid), {}).get('last_name', '')}: {round(datos['reales'].get(str(pid), datos['proy'].get(str(pid), 0.0)),1)}" for pid in mi_roster['players'] if pid not in mi_roster['starters']]
                prompt = f"TITULARES: {', '.join(tit_str)}. BANCA: {', '.join(ban_str)}. Hay fuga de puntos. Dame Diagnóstico, Veredicto y Solución Táctica agresiva."
                st.warning(llamar_gemini(prompt))

        st.markdown("#### 🎙️ Narrador IA")
        if st.button("Generar Comentario En Vivo"):
            with st.spinner("Analizando..."): st.info("🎙️ " + llamar_gemini(f"RedZone en vivo: Rayos ({pts_mios}) vs {riv_nom} ({pts_riv}). Probabilidad: {prob}%. Haz un comentario emocionante corto."))
                
        with st.expander("📺 Hype Cam", expanded=False):
            st.video("https://www.youtube.com/watch?v=s5RzL57cibM") 

def render_tab_side_by_side(datos, mi_roster, riv_start, riv_nom, mi_r_id, u_map):
    st.header("⚖️ Análisis Side-by-Side en Tiempo Real")
    prob_base, prob_live, delta_prob = calcular_drift_probabilidad(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pronóstico Inicial", f"{prob_base}%")
    c2.metric("Probabilidad Actual", f"{prob_live}%")
    c3.metric("Variación (Δ)", f"{'+' if delta_prob >= 0 else ''}{delta_prob}%", delta=f"{delta_prob}%")

    df_sbs = generar_comparativa_side_by_side(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'])
    st.dataframe(df_sbs, hide_index=True, use_container_width=True)

def render_tab_tracker(datos, u_map):
    st.header("📊 Tracker Liga: Enfrentamientos y Análisis de Rosters")
    datos_barras = [{"Manager": u_map.get(r['owner_id'], 'Eq'), "Jugador": datos['players_db'].get(str(pid), {}).get('last_name', str(pid)), "Puntos": datos['reales'].get(str(pid), 0.0)} for r in datos['rosters'] for pid in r.get('starters', []) if datos['reales'].get(str(pid), 0.0) > 0]
    if datos_barras:
        df_barras = pd.DataFrame(datos_barras)
        fig_bar = px.bar(df_barras, x="Puntos", y="Manager", color="Jugador", orientation='h', category_orders={"Manager": df_barras.groupby("Manager")["Puntos"].sum().sort_values().index}, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_bar.update_layout(height=400, showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.subheader("⚔️ Duelos de la Semana")
    m_agr = {}
    for m in datos['matchups']: m_agr.setdefault(m.get('matchup_id'), []).append(m)
    for m_id, eqs in m_agr.items():
        if len(eqs) != 2: continue
        r1 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[0].get('roster_id'))
        r2 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[1].get('roster_id'))
        
        with st.expander(f"🏈 {u_map.get(r1.get('owner_id'), 'Eq1')} vs {u_map.get(r2.get('owner_id'), 'Eq2')}", expanded=False):
            st.info("Desarrollo en progreso para optimizar vista.")

def render_tab_pronosticos(datos, u_map, mi_r_id):
    st.header("🔮 Cartelera de Pronósticos (Monte Carlo)")
    if st.button("🎙️ Generar Previa de la Semana con Gemini"):
        resumen_duelos = []
        m_agr_ai = {}
        for m in datos['matchups']: m_agr_ai.setdefault(m.get('matchup_id'), []).append(m)
        for m_id, eqs in m_agr_ai.items():
            if len(eqs) == 2:
                r1, r2 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[0].get('roster_id')), next(r for r in datos['rosters'] if r.get('roster_id') == eqs[1].get('roster_id'))
                p_w, _, _, _ = ejecutar_monte_carlo_dual(r1.get('starters',[]), r2.get('starters',[]), datos['players_db'], datos['proy'], datos['reales'], 1000)
                resumen_duelos.append(f"{u_map.get(r1.get('owner_id'))} ({p_w}%) vs {u_map.get(r2.get('owner_id'))} ({round(100-p_w, 1)}%)")
        with st.spinner("Analizando..."): st.info(llamar_gemini(f"Eres experto NFL. Probabilidades: {', '.join(resumen_duelos)}. Haz un artículo corto (Juego de semana, paliza, upset)."))
    
    st.divider()
    m_agr = {}
    for m in datos['matchups']: m_agr.setdefault(m.get('matchup_id'), []).append(m)
    for m_id, eqs in m_agr.items():
        if len(eqs) != 2: continue
        r1, r2 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[0].get('roster_id')), next(r for r in datos['rosters'] if r.get('roster_id') == eqs[1].get('roster_id'))
        p1, _, _, _ = ejecutar_monte_carlo_dual(r1.get('starters',[]), r2.get('starters',[]), datos['players_db'], datos['proy'], datos['reales'], 1500)
        p2 = round(100.0 - p1, 1)
        tag = "🚨 PALIZA" if p1>=75 or p2>=75 else ("🪙 MONEDA AL AIRE" if 40<=p1<=60 else "⚖️ FAVORITO")
        
        st.markdown(f"**{tag}**")
        c1, c2, c3 = st.columns([3, 2, 3])
        c1.markdown(f"<h3 style='text-align: right;'>{u_map.get(r1.get('owner_id'))} - {p1}%</h3>", unsafe_allow_html=True)
        c2.progress(p1 / 100.0)
        c3.markdown(f"<h3 style='text-align: left;'>{u_map.get(r2.get('owner_id'))} - {p2}%</h3>", unsafe_allow_html=True)
        st.markdown("---")

def render_tab_vegas_odds(datos):
    st.header("🎲 Game Script & Vegas Odds")
    df_vegas = generar_game_scripts(datos['players_db'], datos['proy'])
    st.dataframe(df_vegas.head(12), hide_index=True, use_container_width=True)
