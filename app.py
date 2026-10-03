import streamlit as st
from streamlit_autorefresh import st_autorefresh
import seaborn as sns

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="War Room - Rayos de Jalisco", page_icon="⚡", layout="wide")
st_autorefresh(interval=60000, key="data_refresh")
sns.set_theme(style="whitegrid", palette="pastel")

# --- IMPORTAR MÓDULOS DE ARQUITECTURA ---
from core_logic import extraer_datos_sleeper, SLEEPER_USERNAME, MI_EQUIPO_NOMBRE
from ui_tabs import (
    render_tab_live, render_tab_side_by_side, render_tab_roster, 
    render_tab_desempeno, render_tab_tracker, render_tab_pronosticos, 
    render_tab_forense, render_tab_waivers, render_tab_nflverse, 
    render_tab_heatmap, render_tab_oraculo, render_tab_trade_machine, 
    render_tab_lesiones, render_tab_vegas_odds, render_tab_mastermind,
    render_tab_noticias
)

c_title, c_btn = st.columns([4, 1])
with c_title:
    st.title("⚡ WAR ROOM: Rayos de Jalisco")
with c_btn:
    st.write("") # Espaciado
    if st.button("🔄 Sincronizar Sleeper"):
        st.cache_data.clear() # Borra la memoria
        st.rerun() # Recarga la app al instante

datos = extraer_datos_sleeper(SLEEPER_USERNAME)

if datos:
    u_map = {u.get('user_id'): u.get('metadata',{}).get('team_name') or u.get('display_name') for u in datos["users"]}
    mi_r_id = next((r.get('roster_id') for r in datos["rosters"] if u_map.get(r.get('owner_id'),"").lower().strip() == MI_EQUIPO_NOMBRE.lower().strip()), None)
    mi_m_id = next((m.get('matchup_id') for m in datos["matchups"] if m.get('roster_id') == mi_r_id), None)
    riv_r_id = next((m.get('roster_id') for m in datos["matchups"] if m.get('matchup_id') == mi_m_id and m.get('roster_id') != mi_r_id), None)
    riv_nom = u_map.get(next((r.get('owner_id') for r in datos["rosters"] if r.get('roster_id') == riv_r_id), ""), "Rival")
    
    mi_roster = next((r for r in datos["rosters"] if r.get('roster_id') == mi_r_id), None)
    riv_start = next((r.get('starters', []) for r in datos["rosters"] if r.get('roster_id') == riv_r_id), [])
    
    if mi_roster:
        # LAS 16 PESTAÑAS MAESTRAS
        tabs = st.tabs([
            "⚔️ Resumen Live", "⚖️ Side-by-Side", "📋 Mi Roster", 
            "📈 Histórico", "📊 Tracker Liga", "🔮 Predicciones", 
            "🕵‍♂️️ Sabotaje", "🦅 Waivers", "🏈 NFLVerse", 
            "🗺️ Heatmap", "🧠 Oráculo ROS", "🤝 Trade Machine", 
            "🚑 Lesiones", "🎲 Vegas Odds", "🤖 Mastermind", 
            "📰 Noticias Liga"
        ])

        # INYECCIÓN MODULAR ORDENADA
        with tabs[0]: render_tab_live(datos, mi_roster, riv_start, riv_nom)
        with tabs[1]: render_tab_side_by_side(datos, mi_roster, riv_start, riv_nom, mi_r_id, u_map)
        with tabs[2]: render_tab_roster(datos, mi_roster, riv_start, riv_nom)
        with tabs[3]: render_tab_desempeno(datos, mi_roster)
        with tabs[4]: render_tab_tracker(datos, u_map)
        with tabs[5]: render_tab_pronosticos(datos, u_map, mi_r_id)
        with tabs[6]: render_tab_forense(datos, u_map)
        with tabs[7]: render_tab_waivers(datos)
        with tabs[8]: render_tab_nflverse()
        with tabs[9]: render_tab_heatmap(datos, u_map)
        with tabs[10]: render_tab_oraculo(datos, u_map)
        with tabs[11]: render_tab_trade_machine(datos, mi_roster, u_map)
        with tabs[12]: render_tab_lesiones(datos)
        with tabs[13]: render_tab_vegas_odds(datos)
        with tabs[14]: render_tab_mastermind(datos, mi_roster, riv_start, riv_nom, u_map)
        with tabs[15]: render_tab_noticias(datos, u_map)
else:
    st.error("Error conectando a la API de Sleeper. Revisa la conexión.")
