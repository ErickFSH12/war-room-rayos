import streamlit as st
import pandas as pd
import plotly.express as px
from core_logic import generar_heatmap_vulnerabilidad, generar_game_scripts

def render_tab_market_dynamics(datos, u_map):
    st.header("📈 Dinámicas de Mercado & Game Script")
    st.write("Identifica vulnerabilidades en los rosters rivales y mapea qué ofensivas NFL producirán más puntos esta semana.")
    
    col_heat, col_vegas = st.columns([3, 2])
    
    with col_heat:
        st.subheader("🗺️ Heatmap Global de Vulnerabilidad")
        st.write("¿Quién tiene el peor grupo de receptores o corredores? Ataca esas debilidades con ofertas de Trade.")
        df_heat = generar_heatmap_vulnerabilidad(datos['rosters'], datos['players_db'], datos['proy'], u_map)
        fig_heat = px.imshow(df_heat, text_auto=".1f", aspect="auto", color_continuous_scale="RdYlGn", origin='lower')
        fig_heat.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20))
        st.plotly_chart(fig_heat, use_container_width=True)
        
    with col_vegas:
        st.subheader("🎲 Game Script (Vegas Odds)")
        st.write("Suma total de proyección (Sleeper) por ofensiva NFL. Apunta a jugadores en los equipos Top 5.")
        df_vegas = generar_game_scripts(datos['players_db'], datos['proy'])
        st.dataframe(df_vegas.head(15), hide_index=True, use_container_width=True)
