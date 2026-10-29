import streamlit as st
import pandas as pd
from core_logic import (
    ejecutar_monte_carlo_dual, llamar_gemini, simular_oraculo_ros, 
    generar_heatmap_vulnerabilidad, obtener_mejores_waivers, 
    obtener_noticias_nfl, empaquetar_estado_liga_para_gemini,
    escanear_handcuffs
)

def render_tab_mastermind(datos, mi_roster, riv_start, riv_nom, u_map):
    st.header("🧠 El Cerebro: Mastermind & Central Médico")
    
    # 1. TABLA DE LESIONES INCORPORADA AL CEREBRO
    st.subheader("🚑 Alertas Críticas de Lesión y Handcuffs")
    st.write("Mapeo de titulares caídos y suplentes libres para alimentar la IA táctica.")
    df_les = escanear_handcuffs(datos['rosters'], datos['players_db'])
    
    if not df_les.empty:
        st.dataframe(df_les, hide_index=True, use_container_width=True)
        texto_lesiones = "REPORTE MÉDICO ACTUAL:\n" + "\n".join([f"- {row['Titular Caído']} ({row['Equipo']}) está {row['Estatus']}. Handcuffs libres: {row['Handcuffs Libres']}." for index, row in df_les.iterrows()])
    else:
        st.success("No hay lesiones críticas con Handcuffs disponibles.")
        texto_lesiones = "REPORTE MÉDICO: Sin lesiones críticas que explotar en este momento."

    st.divider()
    
    # 2. FÓRMULAS
    with st.expander("📊 Ver Matemáticas y Modelos Activos bajo el capó", expanded=False):
        c_m1, c_m2 = st.columns(2)
        c_m3, c_m4 = st.columns(2)
        with c_m1:
            st.markdown("### 1. Valor Esperado ($EV_{adj}$)")
            st.latex(r"EV_{adj} = \mu \times P(E) - \delta_{clima}")
        with c_m2:
            st.markdown("### 2. Varianza de Jugador ($\sigma$)")
            st.latex(r"\sigma = (100 - P_{E}) \times 0.08 + 3.0")
        with c_m3:
            st.markdown("### 3. Simulación Monte Carlo")
            st.latex(r"P(Win) = \frac{\sum_{i=1}^{5000} [S_M > S_R]}{5000}")
        with c_m4:
            st.markdown("### 4. Inferencia Bayesiana")
            st.latex(r"P(\mu|News) = \frac{P(News|\mu)P(\mu)}{P(News)}")

    # 3. CONTEXTO PARA GEMINI
    prob_win, _, _, _ = ejecutar_monte_carlo_dual(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'], 1000)
    df_ros = simular_oraculo_ros(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    df_heat = generar_heatmap_vulnerabilidad(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    fas_unificados = obtener_mejores_waivers(datos['rosters'], datos['players_db'], datos['proy'], pd.DataFrame())

    nombres_roster = []
    for r in datos['rosters']:
        for pid in r.get('players', []):
            p = datos['players_db'].get(str(pid), {})
            if p.get('position') in ['QB', 'RB', 'WR', 'TE']:
                nombres_roster.append((f"{p.get('first_name', '')} {p.get('last_name', '')}").strip().lower())
                
    with st.spinner("Compilando telemetría deportiva y partes médicos..."):
        noticias = obtener_noticias_nfl(nombres_roster)
        contexto_liga = empaquetar_estado_liga_para_gemini(mi_roster, riv_start, riv_nom, prob_win, df_ros, df_heat, fas_unificados, noticias)

    # 4. EL NUEVO PROMPT SÚPER CARGADO
    prompt = f"""
    Eres el analista de datos jefe y director médico de mi War Room de Fantasy Football. 
    Analiza esta telemetría cruzada:
    
    --- ESTADO GLOBAL DE LA LIGA ---
    {contexto_liga}
    
    --- CENTRAL MÉDICA ---
    {texto_lesiones}
    
    Con base en la estadística y los lesionados, elabora un Plan Maestro:
    1. DIAGNÓSTICO MATEMÁTICO: ¿Cómo vamos para el campeonato?
    2. SHOCK DEL MERCADO (BAYES Y LESIONES): ¿Qué impacto brutal y oportunidades directas generan las lesiones y noticias actuales?
    3. PLAN DE ACCIÓN: Dime qué jugador lesionado de mi rival debo aprovechar, o qué handcuff debo robar inmediatamente.
    """
    if st.button("🧠 Generar Plan Maestro (Predictivo + Médico)"):
        with st.spinner("Cruzando algoritmos y reportes médicos..."):
            st.info(llamar_gemini(prompt))

def render_tab_noticias(datos, u_map):
    st.header("📰 Central de Noticias (ESPN & Yahoo)")
    jugador_a_manager = {}
    for r in datos['rosters']:
        mgr = u_map.get(r['owner_id'], 'Eq')
        for pid in r.get('players', []):
            p = datos['players_db'].get(str(pid), {})
            if p.get('position') in ['QB', 'RB', 'WR', 'TE']:
                nom = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                if nom: jugador_a_manager[nom.lower()] = mgr
                    
    with st.spinner("Interceptando feeds RSS..."):
        noticias = obtener_noticias_nfl(list(jugador_a_manager.keys()))
        
    if noticias:
        for i, n in enumerate(noticias):
            afectados = [f"{jug_lower.title()} (Roster: {jugador_a_manager.get(jug_lower)})" for jug_lower in n['jugadores'] if jugador_a_manager.get(jug_lower)]
            st.info(f"🏈 **Impacto:** {', '.join(afectados)}")
            st.markdown(f"#### [{n['titulo']}]({n['link']})")
            if st.button("🧠 Analizar impacto", key=f"btn_news_{i}"):
                prompt = f"Analiza la noticia '{n['titulo']}'. Afecta a: {', '.join(afectados)}. ¿Qué deberían hacer?"
                st.success(llamar_gemini(prompt))
            st.divider()
    else:
        st.success("Sin alertas críticas.")
