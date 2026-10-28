import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import math

from core_logic import (
    get_proy, ejecutar_monte_carlo_dual, 
    llamar_gemini, formatear_roster_df, cargar_nflverse, 
    MI_EQUIPO_NOMBRE, generar_heatmap_vulnerabilidad, 
    simular_oraculo_ros, evaluar_trade, escanear_handcuffs, 
    obtener_mejores_waivers, obtener_noticias_nfl, 
    empaquetar_estado_liga_para_gemini, evaluar_trade_interactivo
)

COLOR_MIO = "#4A90E2"
COLOR_RIV = "#E94B3C"

def render_tab_forense(datos, u_map):
    st.header("🕵️‍♂️ Matriz de Sabotaje y Auditoría")
    cnt = {r.get('roster_id'): {'adds': 0, 'faab': 0, 'trades': 0} for r in datos.get('rosters', [])}
    for t in datos.get('trades', []):
        for rid in t.get('roster_ids', []):
            if rid in cnt: cnt[rid]['trades'] += 1
            
    drops_p = []
    for w in datos.get('waivers', []):
        rid = w.get('creator') 
        if not rid and w.get('roster_ids'): rid = w.get('roster_ids')[0]
        if rid in cnt:
            cnt[rid]['adds'] += 1
            settings = w.get('settings') or {}
            faab_spent = settings.get('waiver_bid', 0)
            if faab_spent: cnt[rid]['faab'] += faab_spent
            
        drops = w.get('drops') or {}
        for pid, roster_id_drop in drops.items():
            p_data = datos['players_db'].get(str(pid), {})
            pos = p_data.get('position', 'N/A')
            pr = round(datos['proy'].get(str(pid), 0.0), 1)
            if pr >= 8.0:
                mgr_drop = "Desconocido"
                for r in datos.get('rosters', []):
                    if r.get('roster_id') == roster_id_drop:
                        mgr_drop = u_map.get(r.get('owner_id'), "Eq")
                        break
                nom_jugador = f"{p_data.get('first_name', '')} {p_data.get('last_name', '')}".strip()
                drops_p.append(f"🚨 **{mgr_drop}** soltó a **{nom_jugador}** ({pos} - Proy: {pr} pts)")

    c_f1, c_f2 = st.columns(2)
    with c_f1:
        st.subheader("🔫 Gatillo Fácil (Actividad)")
        actividad = []
        for rid, d in cnt.items():
            mgr_name = "Manager Desconocido"
            for r in datos.get('rosters', []):
                if r.get('roster_id') == rid:
                    mgr_name = u_map.get(r.get('owner_id'), "Eq")
                    break
            actividad.append({"Manager": mgr_name, "Trades": d['trades'], "Waivers": d['adds'], "FAAB Gastado": f"${d['faab']}"})
        df_act = pd.DataFrame(actividad).sort_values(by=["Trades", "Waivers"], ascending=[False, False])
        st.dataframe(df_act, hide_index=True, use_container_width=True)
        
    with c_f2:
        st.subheader("😱 Panic Drops")
        if drops_p:
            for d in drops_p: st.error(d)
        else: st.success("Nadie ha entrado en pánico botando jugadores valiosos aún.")

def render_tab_waivers(datos):
    st.header("🦅 Agencia Libre Dinámica (Waivers + NFLVerse)")
    df_nfl = cargar_nflverse()
    fas = obtener_mejores_waivers(datos['rosters'], datos['players_db'], datos['proy'], df_nfl)
    
    if not fas:
        st.warning("No hay agentes libres destacables.")
        return
        
    df_fa = pd.DataFrame(fas)
    df_fa = df_fa.rename(columns={'nombre_completo': 'Jugador', 'pos': 'Pos', 'eq': 'Equipo', 'ev': 'EV_adj', 'proy': 'Proyección', 'hist_avg': 'Media NFLVerse', 'inj': 'Salud'})
    
    c1, c2 = st.columns([1, 3])
    with c1:
        filtro_pos = st.selectbox("Posición", ["Todas", "QB", "RB", "WR", "TE", "K", "DEF"])
        if filtro_pos != "Todas": df_fa = df_fa[df_fa['Pos'] == filtro_pos]
    with c2:
        if not df_fa.empty:
            fig = px.scatter(df_fa.head(40), x="Proyección", y="EV_adj", color="Pos", hover_name="Jugador")
            st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_fa[['Jugador', 'Pos', 'Equipo', 'EV_adj', 'Proyección', 'Media NFLVerse', 'Salud']].head(50), hide_index=True, use_container_width=True)

def render_tab_nflverse(datos):
    st.header("🏈 Análisis Científico: Sleeper vs NFLVerse")
    df_nfl = cargar_nflverse()
    if df_nfl.empty:
        st.warning("Base de datos NFLVerse no disponible en este momento.")
        return
        
    jugadores_opciones, equipos_opciones, nom_a_id = [], set(), {}
    for pid, p in datos['players_db'].items():
        pos, eq = p.get('position', ''), p.get('team', '')
        if eq and eq != 'FA': equipos_opciones.add(eq)
        if pos in ['QB', 'RB', 'WR', 'TE'] and p.get('status') != 'Inactive':
            pr = datos['proy'].get(str(pid), 0.0)
            if pr > 2.0: 
                nom = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                jugadores_opciones.append(nom)
                nom_a_id[nom] = pid
                
    c1, c2 = st.columns(2)
    with c1: jug_sel = st.selectbox("🔍 Análisis por Jugador", sorted(list(set(jugadores_opciones))), index=0)
    with c2: eq_sel = st.selectbox("🛡️ Análisis por Ofensiva", sorted(list(equipos_opciones)), index=0)
        
    st.divider()
    col_jug, col_eq = st.columns(2)
    
    with col_jug:
        st.subheader(f"👤 {jug_sel}")
        pid = str(nom_a_id.get(jug_sel, ''))
        proy_actual = round(datos['proy'].get(pid, 0.0), 1)
        real_actual = datos['reales'].get(pid, None)
        col_name = 'player_display_name' if 'player_display_name' in df_nfl.columns else 'player_name'
        df_j = df_nfl[df_nfl[col_name] == jug_sel]
        
        if not df_j.empty:
            media_hist = round(df_j['fantasy_points_ppr'].mean(), 1)
            m1, m2, m3 = st.columns(3)
            m1.metric("Media Histórica", f"{media_hist} pts")
            m2.metric("Proy. Sleeper", f"{proy_actual} pts", delta=f"{round(proy_actual - media_hist, 1)} vs Hist")
            m3.metric("Real de Hoy", f"{real_actual} pts" if real_actual is not None else "Pendiente")
            
            df_j_sort = df_j.sort_values(['season', 'week'])
            df_j_sort['Semana'] = df_j_sort['season'].astype(str) + " W" + df_j_sort['week'].astype(str)
            fig_j = px.line(df_j_sort, x='Semana', y='fantasy_points_ppr', markers=True, color_discrete_sequence=[COLOR_MIO])
            fig_j.add_hline(y=proy_actual, line_dash="dot", line_color=COLOR_RIV)
            fig_j.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_j, use_container_width=True)
        else:
            st.warning("Sin historial para este jugador.")
            
    with col_eq:
        st.subheader(f"🛡️ Ofensiva Global: {eq_sel}")
        proy_eq = sum([datos['proy'].get(str(p_id), 0.0) for p_id, p in datos['players_db'].items() if p.get('team') == eq_sel and p.get('position') in ['QB', 'RB', 'WR', 'TE']])
        df_eq = df_nfl[df_nfl['recent_team'] == eq_sel]
        
        if not df_eq.empty:
            df_eq_grp = df_eq.groupby(['season', 'week'])['fantasy_points_ppr'].sum().reset_index()
            media_eq_hist = round(df_eq_grp['fantasy_points_ppr'].mean(), 1)
            em1, em2 = st.columns(2)
            em1.metric("Media Histórica", f"{media_eq_hist} pts")
            em2.metric("Proy. Acumulada", f"{round(proy_eq, 1)} pts", delta=f"{round(proy_eq - media_eq_hist, 1)} vs Hist")
            
            top_cont = df_eq.groupby(col_name)['fantasy_points_ppr'].sum().sort_values(ascending=False).head(5).reset_index()
            fig_pie = px.pie(top_cont, values='fantasy_points_ppr', names=col_name, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("Sin historial para este equipo.")

def render_tab_oraculo(datos, u_map):
    st.header("🧠 El Oráculo: Rest of Season (ROS)")
    df_ros = simular_oraculo_ros(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    st.dataframe(df_ros[['Manager', 'Prob Campeonato %']], hide_index=True, use_container_width=True)

def render_tab_trade_machine(datos, mi_roster, u_map):
    st.header("🤝 La Máquina de Trades (Math + AI Notebook)")
    mis_jugadores_opciones = {f"{datos['players_db'].get(str(p), {}).get('last_name')} ({datos['players_db'].get(str(p), {}).get('position')})": p for p in mi_roster['players']}
    rivales_opciones = {}
    for r in datos['rosters']:
        if r['roster_id'] != mi_roster['roster_id']:
            mgr_nom = u_map.get(r['owner_id'], 'Eq')
            for p in r.get('players', []):
                nom = f"{datos['players_db'].get(str(p), {}).get('last_name')} ({datos['players_db'].get(str(p), {}).get('position')}) - {mgr_nom}"
                rivales_opciones[nom] = {'pid': p, 'rid': r['roster_id'], 'starters': r.get('starters', [])}

    c1, c2 = st.columns(2)
    with c1:
        dar_seleccion = st.selectbox("Dar a (Tu jugador):", list(mis_jugadores_opciones.keys()))
        recibir_seleccion = st.selectbox("Recibir a (Jugador Rival):", list(rivales_opciones.keys()))
    with c2:
        fuentes_input = st.text_area("📚 Contexto Externo", height=110)
        
    if st.button("⚖️ Ejecutar Simulación", use_container_width=True):
        pid_dar, pid_recibir = mis_jugadores_opciones[dar_seleccion], rivales_opciones[recibir_seleccion]['pid']
        rival_starters = rivales_opciones[recibir_seleccion]['starters']
        nom_dar, nom_recibir = dar_seleccion.split(" (")[0], recibir_seleccion.split(" (")[0]
        
        with st.spinner("Simulando Monte Carlo y conectando Gemini..."):
            pb, pp, delta = evaluar_trade(mi_roster['starters'], rival_starters, pid_dar, pid_recibir, datos['players_db'], datos['proy'], datos['reales'])
            noticias = obtener_noticias_nfl([nom_dar.lower(), nom_recibir.lower()])
            noticias_str = "- " + "\n- ".join([n['titulo'] for n in noticias]) if noticias else "Sin reportes recientes."
            
            analisis = evaluar_trade_interactivo(nom_dar, nom_recibir, delta, fuentes_input, round(datos['proy'].get(str(pid_dar), 0.0), 1), round(datos['proy'].get(str(pid_recibir), 0.0), 1), noticias_str)
            
        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("Prob Pre-Trade", f"{pb}%")
        c_res2.metric("Prob Post-Trade", f"{pp}%")
        c_res3.metric("Impacto Matemático", f"{'+' if delta >= 0 else ''}{delta}%")
        st.info(analisis)

def render_tab_mastermind(datos, mi_roster, riv_start, riv_nom, u_map):
    st.header("🧠 El Cerebro: Mastermind & Central Médico")
    
    # 1. TABLA DE LESIONES INCORPORADA AL CEREBRO
    st.subheader("🚑 Alertas Críticas de Lesión y Handcuffs")
    st.write("Mapeo de titulares caídos y suplentes libres para alimentar la IA táctica.")
    df_les = escanear_handcuffs(datos['rosters'], datos['players_db'])
    
    if not df_les.empty:
        st.dataframe(df_les, hide_index=True, use_container_width=True)
        # Construimos el texto médico para inyectarlo en el Prompt
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
