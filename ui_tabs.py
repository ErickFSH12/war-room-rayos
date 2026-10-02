import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import math
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import math
from core_logic import (get_proy, optimizar_alineacion, ejecutar_monte_carlo_dual, 
                        llamar_gemini, formatear_roster_df, cargar_nflverse, 
                        calc_prob, obtener_info_hc, consultar_clima, MI_EQUIPO_NOMBRE,
                        calcular_drift_probabilidad, generar_comparativa_side_by_side,
                        generar_heatmap_vulnerabilidad, simular_oraculo_ros, evaluar_trade,
                        escanear_handcuffs, generar_game_scripts,
                        obtener_mejores_waivers, empaquetar_estado_liga_para_gemini,
                        obtener_noticias_nfl) # <-- NUEVO IMPORT
COLOR_MIO = "#4A90E2"
COLOR_RIV = "#E94B3C"

def render_tab_live(datos, mi_roster, riv_start, riv_nom):
    st.header(f"Matchup Semana {datos['semana']}")
    
    # NUEVO: GUÍA TÁCTICA EXPANDIBLE
    with st.expander("📚 Guía Táctica: Qué investigar antes de un Trade o Waiver", expanded=False):
        st.markdown("""
        * **🏈 Quarterbacks (QB):** Busca *Rushing Upside* (puntos por acarreo = piso seguro) y volumen de pases. Evalúa su línea ofensiva y el calendario futuro (SOS). 
        * **🏃 Running Backs (RB):** El volumen es rey. Analiza los *High-Value Touches* (oportunidades en zona roja y targets por pase). Huye de los "comités" de 3 corredores.
        * **👐 Wide Receivers (WR):** Investiga el *Target Share* (>20% de pases a él), *Air Yards* (pases profundos = jugadas grandes) y los emparejamientos contra esquineros estrella. 
        * **🧱 Tight Ends (TE):** Posición altamente volátil. Prioriza TE's que sean la 1ª o 2ª opción de pase en su equipo o que sean gigantes físicos dominantes en la Zona Roja.
        * **🛡️ DEF / 🦵 K:** Haz *Streaming* (rótalos cada semana). Ataca ofensivas débiles, equipos que ceden muchas capturas (Sacks) o QBs novatos. Busca equipos favoritos que jueguen en casa.
        """)
        
    m_aseg = sum([datos['reales'][str(p)] for p in mi_roster['starters'] if str(p) in datos['reales']])
    m_rest = sum([datos['proy'].get(str(p), 0.0) for p in mi_roster['starters'] if str(p) not in datos['reales']])
    r_aseg = sum([datos['reales'][str(p)] for p in riv_start if str(p) in datos['reales']])
    r_rest = sum([datos['proy'].get(str(p), 0.0) for p in riv_start if str(p) not in datos['reales']])
    
    c1, c2, c3 = st.columns(3)
    c1.metric(label=f"{MI_EQUIPO_NOMBRE}", value=round(m_aseg + m_rest, 1), delta=f"{round(m_aseg,1)} asegurados")
    c2.metric(label=f"{riv_nom}", value=round(r_aseg + r_rest, 1), delta=f"{round(r_aseg,1)} asegurados")
    
    opt_start, cambios = optimizar_alineacion(mi_roster['starters'], [p for p in mi_roster['players'] if p not in mi_roster['starters']], datos['players_db'], datos['proy'], datos['reales'])
    prob, med, sm, sr = ejecutar_monte_carlo_dual(opt_start, riv_start, datos['players_db'], datos['proy'], datos['reales'])
    c3.metric(label="Win Probability (Monte Carlo)", value=f"{prob}%")

    st.divider()
    col_mc, col_espn = st.columns([1, 1])
    with col_mc:
        st.subheader("Curva de Probabilidad")
        fig_mc, ax_mc = plt.subplots(figsize=(5, 3))
        ax_mc.hist(sm, bins=40, alpha=0.7, color=COLOR_MIO, label='Rayos', density=True)
        ax_mc.hist(sr, bins=40, alpha=0.7, color=COLOR_RIV, label='Rival', density=True)
        ax_mc.spines['top'].set_visible(False); ax_mc.spines['right'].set_visible(False)
        ax_mc.legend(); st.pyplot(fig_mc)
        
    with col_espn:
        st.subheader("Reporte Táctico")
        if cambios: st.warning("\n".join(cambios))
        else: st.success("Alineación Blindada Óptima. No mover.")
        resumen_espn = llamar_gemini(f"Comentarista ESPN. Rayos vs {riv_nom}. Probabilidad {prob}%. Resume en 2 párrafos cortos.")
        st.info(f"🎙️ {resumen_espn}")

def render_tab_roster(datos, mi_roster, riv_start, riv_nom):
    st.header("Auditoría de Equipo")
    df_titulares = formatear_roster_df(mi_roster['starters'], datos['players_db'], datos['proy'], datos['reales'], "Titular")
    banca_ids = [p for p in mi_roster['players'] if p not in mi_roster['starters']]
    df_banca = formatear_roster_df(banca_ids, datos['players_db'], datos['proy'], datos['reales'], "Banca/IR")
    
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.subheader("11 Inicial")
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
        ax_rad.plot(angs, m_pts, color=COLOR_MIO, lw=2, label='Rayos'); ax_rad.fill(angs, m_pts, COLOR_MIO, alpha=0.2)
        ax_rad.plot(angs, r_pts, color=COLOR_RIV, lw=2, label=riv_nom); ax_rad.fill(angs, r_pts, COLOR_RIV, alpha=0.2)
        ax_rad.set_xticks(angs[:-1]); ax_rad.set_xticklabels(cats, size=10)
        ax_rad.legend(loc='lower center', bbox_to_anchor=(0.5, -0.2))
        st.pyplot(fig_rad)

def render_tab_tracker(datos, u_map):
    st.header("Marcador Global de la Liga")
    datos_barras = []
    for r in datos['rosters']:
        mgr = u_map.get(r['owner_id'], 'Eq')
        for pid in r.get('starters', []):
            pts = datos['reales'].get(str(pid), 0.0)
            nom = datos['players_db'].get(str(pid), {}).get('last_name', str(pid))
            datos_barras.append({"Manager": mgr, "Jugador": nom, "Puntos": pts})
    
    if datos_barras:
        df_barras = pd.DataFrame(datos_barras)
        orden = df_barras.groupby("Manager")["Puntos"].sum().sort_values(ascending=True).index
        fig_bar = px.bar(df_barras, x="Puntos", y="Manager", color="Jugador", orientation='h', category_orders={"Manager": orden}, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_bar.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

def render_tab_pronosticos(datos, u_map, mi_r_id):
    st.header("Playoffs: Predicciones de Toda la Liga")
    m_agr = {}
    for m in datos['matchups']: m_agr.setdefault(m.get('matchup_id'), []).append(m)
    
    cols_p = st.columns(len(m_agr) if len(m_agr) > 0 else 1)
    idx = 0
    for m_id, eqs in m_agr.items():
        if len(eqs)!=2: continue
        r1, r2 = next(r for r in datos['rosters'] if r.get('roster_id')==eqs[0].get('roster_id')), next(r for r in datos['rosters'] if r.get('roster_id')==eqs[1].get('roster_id'))
        m1, m2 = u_map.get(r1.get('owner_id'),"Eq1"), u_map.get(r2.get('owner_id'),"Eq2")
        p_win, _, s1, s2 = ejecutar_monte_carlo_dual(r1.get('starters',[]), r2.get('starters',[]), datos['players_db'], datos['proy'], datos['reales'], 1500)
        
        with cols_p[idx % len(cols_p)]:
            st.markdown(f"**{m1[:10]}** ({p_win}%) vs **{m2[:10]}**")
            fig_p, ax_p = plt.subplots(figsize=(3, 1.5))
            ax_p.hist(s1, bins=30, alpha=0.6, color=COLOR_MIO); ax_p.hist(s2, bins=30, alpha=0.6, color=COLOR_RIV)
            ax_p.axis('off'); st.pyplot(fig_p)
        idx += 1

def render_tab_forense(datos, u_map):
    st.header("Matriz de Sabotaje y Auditoría")
    cnt = {r.get('roster_id'): {'adds':0, 'faab':0, 'trades': 0} for r in datos['rosters']}
    for t in datos['trades']:
        for rid in t.get('roster_ids', []):
            if rid in cnt: cnt[rid]['trades'] += 1
    
    drops_p = []
    for w in datos['waivers']:
        rid = w.get('creator') or (w.get('roster_ids',[None])[0] if w.get('roster_ids') else None)
        if rid in cnt:
            cnt[rid]['adds'] += 1; cnt[rid]['faab'] += w.get('settings',{}).get('waiver_bid',0)
        for pid, rd in (w.get('drops') or {}).items():
            pr = get_proy(str(pid), datos['players_db'].get(str(pid),{}).get('position'), datos['proy'])
            if pr > 10.5: drops_p.append(f"{datos['players_db'].get(str(pid),{}).get('last_name')} (Drop de {u_map.get(next((r.get('owner_id') for r in datos['rosters'] if r.get('roster_id')==rd),'Eq'))})")

    c_f1, c_f2 = st.columns(2)
    with c_f1:
        st.subheader("Gatillo Fácil (Liga)")
        rk = sorted(cnt.items(), key=lambda x: x[1]['adds'] + x[1]['trades'], reverse=True)
        df_act = pd.DataFrame([{"Manager": u_map.get(next((r.get('owner_id') for r in datos['rosters'] if r.get('roster_id')==rid),'Eq')), "Trades": d['trades'], "Waivers": d['adds'], "FAAB": f"${d['faab']}"} for rid, d in rk])
        st.dataframe(df_act, hide_index=True, use_container_width=True)
    with c_f2:
        st.subheader("Panic Drops")
        if drops_p:
            for d in drops_p[-5:]: st.error(d)
        else: st.write("Sin Panic Drops recientes.")

def render_tab_waivers(datos):
    st.header("🦅 Agencia Libre Dinámica (Waivers + NFLVerse)")
    st.write("Filtra y analiza los mejores jugadores disponibles cruzando proyecciones con su media histórica real.")
    
    df_nfl = cargar_nflverse()
    fas = obtener_mejores_waivers(datos['rosters'], datos['players_db'], datos['proy'], df_nfl)
    
    if not fas:
        st.warning("No hay agentes libres destacables en este momento.")
        return
        
    df_fa = pd.DataFrame(fas)
    df_fa = df_fa.rename(columns={
        'nombre_completo': 'Jugador', 'pos': 'Pos', 'eq': 'Equipo', 
        'ev': 'EV_adj', 'proy': 'Proyección', 'hist_avg': 'Media (NFLVerse)', 'inj': 'Salud'
    })
    
    # Filtros interactivos
    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown("### Filtros")
        filtro_pos = st.selectbox("Posición", ["Todas", "QB", "RB", "WR", "TE", "K", "DEF"])
        if filtro_pos != "Todas":
            df_fa = df_fa[df_fa['Pos'] == filtro_pos]
            
        filtro_min_proy = st.slider("Proyección Mínima", 0.0, 20.0, 5.0)
        df_fa = df_fa[df_fa['Proyección'] >= filtro_min_proy]
        
    with c2:
        if not df_fa.empty:
            fig = px.scatter(
                df_fa.head(40), x="Proyección", y="EV_adj", color="Pos", 
                hover_name="Jugador", size="Proyección", 
                title="Cazador de Gemas: Valor Esperado vs Proyección Base Sleeper",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay jugadores que cumplan los filtros actuales.")
            
    st.divider()
    st.subheader("📋 Base de Datos de Disponibles (Top 50)")
    st.dataframe(df_fa[['Jugador', 'Pos', 'Equipo', 'EV_adj', 'Proyección', 'Media (NFLVerse)', 'Salud']].head(50), hide_index=True, use_container_width=True)
def render_tab_nflverse():
    st.header("Data Científica (NFLVerse)")
    df_nfl = cargar_nflverse()
    if not df_nfl.empty:
        st.dataframe(df_nfl[['player_name', 'recent_team', 'position', 'fantasy_points_ppr']].tail(50), use_container_width=True)
        
    st.subheader("Backtesting: Proyección vs Realidad")
    np.random.seed(42)
    proy_test = np.clip(np.random.normal(13.5, 4.5, 500), 5.0, 25.0)
    reales_test = [max(0, np.random.normal(proy_test[i] + (2 - 2.5)*1.8, 6.0 - (2*0.8))) for i in range(500)]
    fig_bk, ax_bk = plt.subplots(figsize=(6, 3))
    ax_bk.scatter(proy_test, reales_test, alpha=0.4, color=COLOR_MIO)
    ax_bk.plot([5, 25], [5, 25], color=COLOR_RIV, ls='--')
    ax_bk.spines['top'].set_visible(False); ax_bk.spines['right'].set_visible(False)
    st.pyplot(fig_bk)
def render_tab_desempeno(datos, mi_roster):
    st.header("📈 Rendimiento de Jugadores (Sleeper + NFLVerse)")
    st.write("Cruce telemétrico de proyecciones en vivo y el historial científico de yardas y touchdowns.")
    
    # 1. SLEEPER ACTUAL
    st.subheader("1. Radiografía Semana Actual (Sleeper)")
    datos_actuales = []
    for pid in mi_roster['players']:
        p = datos['players_db'].get(str(pid), {})
        nom = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        pos = p.get('position', 'N/A')
        proy = datos['proy'].get(str(pid), 0.0)
        real = datos['reales'].get(str(pid), 0.0)
        status = "✅ Ya jugó" if str(pid) in datos['reales'] else "⏳ Pendiente"
        datos_actuales.append({
            "Jugador": nom, "Posición": pos, 
            "Proyectado": proy, "Real": real, 
            "Diferencia": round(real-proy, 1) if status == "✅ Ya jugó" else 0.0,
            "Status": status
        })
    
    df_act = pd.DataFrame(datos_actuales).sort_values("Proyectado", ascending=False)
    
    col_g1, col_g2 = st.columns([2, 1])
    with col_g1:
        fig_act = px.bar(df_act, x="Jugador", y=["Proyectado", "Real"], barmode="group", 
                         color_discrete_sequence=[COLOR_MIO, COLOR_RIV], 
                         title="Sleeper: Expectativa vs Realidad")
        fig_act.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_act, use_container_width=True)
    with col_g2:
        st.dataframe(df_act[["Jugador", "Proyectado", "Real", "Status"]], hide_index=True, use_container_width=True)

    # 2. NFLVERSE HISTÓRICO
    st.divider()
    st.subheader("2. Historial Científico Multicategoría (NFLVerse)")
    
    df_nfl = cargar_nflverse()
    
    if not df_nfl.empty:
        # Nombres de Los Rayos para filtrar
        mis_jugadores = [f"{datos['players_db'].get(str(pid), {}).get('first_name', '')} {datos['players_db'].get(str(pid), {}).get('last_name', '')}".strip() for pid in mi_roster['players']]
        
        # Identificar la columna de nombre correcta en NFLVerse
        col_name = 'player_display_name' if 'player_display_name' in df_nfl.columns else 'player_name'
        df_mis = df_nfl[df_nfl[col_name].isin(mis_jugadores)].copy()
        
        if not df_mis.empty:
            c1, c2 = st.columns(2)
            with c1:
                # Agrupación por temporadas (Yardas, TDs, Puntos)
                df_temporada = df_mis.groupby([col_name, 'season'])[['fantasy_points_ppr', 'passing_yards', 'rushing_yards', 'receiving_yards']].sum().reset_index()
                fig_hist = px.bar(df_temporada, x=col_name, y="fantasy_points_ppr", color="season", 
                                  barmode="group", title="Producción Total por Temporada", 
                                  color_continuous_scale="Blues")
                fig_hist.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_hist, use_container_width=True)

            with c2:
                # Línea de tendencia de la temporada más reciente
                temp_reciente = df_mis['season'].max()
                df_tendencia = df_mis[df_mis['season'] == temp_reciente]
                fig_line = px.line(df_tendencia, x="week", y="fantasy_points_ppr", color=col_name, 
                                   markers=True, title=f"Curva de Volatilidad Semanal ({temp_reciente})", 
                                   color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_line.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_line, use_container_width=True)

            st.markdown("**Desglose Absoluto Multicategoría**")
            # Ajuste de columnas visibles
            df_temporada.rename(columns={col_name: "Jugador", "season": "Temporada", "fantasy_points_ppr": "Pts PPR", "passing_yards": "Yds Pase", "rushing_yards": "Yds Acarreo", "receiving_yards": "Yds Recepción"}, inplace=True)
            st.dataframe(df_temporada, hide_index=True, use_container_width=True)
        else:
            st.warning("⚠️ No se cruzaron datos exactos con NFLVerse. Esto puede pasar con jugadores novatos, defensas (DEF) o sufijos como 'Jr.' y 'III'.")
    else:
        st.error("No se pudo cargar la base de NFLVerse.")
def render_tab_side_by_side(datos, mi_roster, riv_start, riv_nom, mi_r_id, u_map):
    st.header("⚖️ Análisis Side-by-Side en Tiempo Real")
    st.write("Tracking de enfrentamiento directo y desviación en vivo respecto al pronóstico original.")

    # -------------------------------------------------------------
    # SECCIÓN 1: NUESTRO ENFRENTAMIENTO DIRECTO (H2H)
    # -------------------------------------------------------------
    st.subheader(f"1. Duelo Directo: {MI_EQUIPO_NOMBRE} vs {riv_nom}")
    
    # Cálculo de desviación (Drift)
    prob_base, prob_live, delta_prob = calcular_drift_probabilidad(
        mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales']
    )
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pronóstico Inicial (Pre-Game)", f"{prob_base}%", help="Probabilidad teórica antes de iniciar la jornada.")
    c2.metric("Probabilidad Actual (Live)", f"{prob_live}%", help="Probabilidad calculada con los puntos reales jugados.")
    c3.metric(
        "Variación / Drift (Δ)", 
        f"{'+' if delta_prob >= 0 else ''}{delta_prob}%", 
        delta=f"{delta_prob}% vs Pre-Game",
        delta_color="normal"
    )

    if delta_prob > 0:
        st.success(f"📈 **Tendencia Favorable:** La jornada se está inclinando hacia nosotros por +{delta_prob}% sobre lo pronosticado.")
    elif delta_prob < 0:
        st.warning(f"📉 **Desviación de Riesgo:** El matchup se ha cerrado en {delta_prob}% respecto a la expectativa inicial.")
    else:
        st.info("⚖️ **En Línea con el Modelo:** El desarrollo va exactamente conforme al pronóstico inicial.")

    # Tabla Side-by-Side
    df_sbs = generar_comparativa_side_by_side(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'])
    st.dataframe(df_sbs, hide_index=True, use_container_width=True)

    # Gráfico Comparativo Slot por Slot
    df_plot = df_sbs[df_sbs['Rayos de Jalisco'] != "-"].copy()
    fig_sbs = px.bar(
        df_plot, 
        x="Rayos de Jalisco", 
        y=["Pts (Rayos)", "Pts (Rival)"], 
        barmode="group",
        title="Cara a Cara: Aporte por Posición",
        color_discrete_sequence=[COLOR_MIO, COLOR_RIV]
    )
    fig_sbs.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", legend_title_text="Equipo")
    st.plotly_chart(fig_sbs, use_container_width=True)

    st.divider()

    # -------------------------------------------------------------
    # SECCIÓN 2: SIDE-BY-SIDE DE TODA LA LIGA (LOS 5 ENFRENTAMIENTOS)
    # -------------------------------------------------------------
    st.subheader("2. Pizarrón de la Liga: Los 5 Enfrentamientos Frente a Frente")
    
    m_agr = {}
    for m in datos['matchups']:
        m_agr.setdefault(m.get('matchup_id'), []).append(m)

    for m_id, eqs in m_agr.items():
        if len(eqs) != 2:
            continue
        r1 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[0].get('roster_id'))
        r2 = next(r for r in datos['rosters'] if r.get('roster_id') == eqs[1].get('roster_id'))
        m1 = u_map.get(r1.get('owner_id'), "Equipo 1")
        m2 = u_map.get(r2.get('owner_id'), "Equipo 2")

        # Puntos asegurados y totales esperados
        m1_aseg = sum([datos['reales'][str(p)] for p in r1.get('starters', []) if str(p) in datos['reales']])
        m1_rest = sum([datos['proy'].get(str(p), 0.0) for p in r1.get('starters', []) if str(p) not in datos['reales']])
        m2_aseg = sum([datos['reales'][str(p)] for p in r2.get('starters', []) if str(p) in datos['reales']])
        m2_rest = sum([datos['proy'].get(str(p), 0.0) for p in r2.get('starters', []) if str(p) not in datos['reales']])

        p_base, p_live, d_match = calcular_drift_probabilidad(
            r1.get('starters', []), r2.get('starters', []), datos['players_db'], datos['proy'], datos['reales'], 1500
        )

        with st.container():
            col_eq1, col_vs, col_eq2 = st.columns([4, 2, 4])
            with col_eq1:
                st.markdown(f"### {m1}")
                st.write(f"**Puntos Esperados:** {round(m1_aseg + m1_rest, 1)} pts *(Asegurados: {round(m1_aseg, 1)})*")
                st.progress(min(1.0, max(0.0, p_live / 100.0)))
                st.caption(f"Prob. Victoria: **{p_live}%**")

            with col_vs:
                st.markdown("<h3 style='text-align:center;'>VS</h3>", unsafe_allow_html=True)
                drift_label = f"{'+' if d_match >= 0 else ''}{d_match}%"
                st.metric("Shift en Vivo", drift_label, help="Movimiento de probabilidad respecto al pronóstico pre-game.")

            with col_eq2:
                st.markdown(f"### {m2}")
                st.write(f"**Puntos Esperados:** {round(m2_aseg + m2_rest, 1)} pts *(Asegurados: {round(m2_aseg, 1)})*")
                st.progress(min(1.0, max(0.0, (100.0 - p_live) / 100.0)))
                st.caption(f"Prob. Victoria: **{round(100.0 - p_live, 1)}%**")

            st.markdown("---")
          # =====================================================================
# RENDERIZADO DE LOS 5 MÓDULOS AVANZADOS
# =====================================================================

def render_tab_heatmap(datos, u_map):
    st.header("🗺️ Heatmap Global de Vulnerabilidad")
    st.write("Identifica las debilidades posicionales de toda la liga de un vistazo para atacar con trades.")
    
    df_heat = generar_heatmap_vulnerabilidad(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    
    fig = px.imshow(
        df_heat, text_auto=".1f", aspect="auto", 
        color_continuous_scale="RdYlGn", origin='lower',
        title="Fuerza del Roster por Posición (Proyección Acumulada)"
    )
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

def render_tab_oraculo(datos, u_map):
    st.header("🧠 El Oráculo: Rest of Season (ROS)")
    st.write("Simulación de probabilidades de Campeonato basada en la profundidad y fuerza bruta de los rosters a futuro.")
    
    df_ros = simular_oraculo_ros(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(df_ros[['Manager', 'Prob Campeonato %']], hide_index=True, use_container_width=True)
    with c2:
        fig = px.bar(df_ros, x='Manager', y='Prob Campeonato %', color='Prob Campeonato %', color_continuous_scale="Blues")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

def render_tab_trade_machine(datos, mi_roster, u_map):
    st.header("🤝 La Máquina de Trades (Math + AI Notebook)")
    st.write("Simula el impacto matemático de un trade y pide el veredicto a la IA inyectando tus propias fuentes externas.")
    
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
        st.subheader("1. Jugadores Implicados")
        dar_seleccion = st.selectbox("Dar a (Tu jugador):", list(mis_jugadores_opciones.keys()))
        recibir_seleccion = st.selectbox("Recibir a (Jugador Rival):", list(rivales_opciones.keys()))
    
    with c2:
        st.subheader("2. Fuentes Externas (Notebook RAG)")
        fuentes_input = st.text_area("📚 Contexto (Reddit, Schefter, Rumores)", height=110, placeholder="Ej: Según Adam Schefter, el corredor titular estará fuera 3 semanas...")
        
    st.divider()
    if st.button("⚖️ Ejecutar Simulación y Análisis de IA", use_container_width=True):
        pid_dar = mis_jugadores_opciones[dar_seleccion]
        pid_recibir = rivales_opciones[recibir_seleccion]['pid']
        rival_starters = rivales_opciones[recibir_seleccion]['starters']
        
        # Extracción de nombres para la API y RSS
        nom_dar = dar_seleccion.split(" (")[0]
        nom_recibir = recibir_seleccion.split(" (")[0]
        proy_dar = round(datos['proy'].get(str(pid_dar), 0.0), 1)
        proy_recibir = round(datos['proy'].get(str(pid_recibir), 0.0), 1)
        
        with st.spinner("Simulando Monte Carlo y conectando con Gemini..."):
            # 1. Ejecutar las matemáticas (Simulador original)
            pb, pp, delta = evaluar_trade(mi_roster['starters'], rival_starters, pid_dar, pid_recibir, datos['players_db'], datos['proy'], datos['reales'])
            
            # 2. Buscar noticias de ambos jugadores
            from core_logic import obtener_noticias_nfl, evaluar_trade_interactivo
            noticias = obtener_noticias_nfl([nom_dar.lower(), nom_recibir.lower()])
            noticias_str = ""
            if noticias:
                for n in noticias: noticias_str += f"- {n['titulo']}: {n['desc'][:100]}...\n"
            else:
                noticias_str = "Sin reportes recientes."
            
            # 3. Generar el Veredicto de IA
            analisis = evaluar_trade_interactivo(nom_dar, nom_recibir, delta, fuentes_input, proy_dar, proy_recibir, noticias_str)
            
        # MOSTRAR RESULTADOS
        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("Probabilidad Pre-Trade", f"{pb}%")
        c_res2.metric("Probabilidad Post-Trade", f"{pp}%")
        c_res3.metric("Impacto Matemático (Δ)", f"{'+' if delta >= 0 else ''}{delta}%", delta=f"{delta}%", delta_color="normal")
        
        st.subheader("🤖 Veredicto del Mastermind")
        st.info(analisis)

def render_tab_lesiones(datos):
    st.header("🚑 Alertas de Lesión y Handcuffs")
    st.write("Identifica titulares caídos en toda la liga y sus suplentes directos disponibles en Agencia Libre.")
    
    df_les = escanear_handcuffs(datos['rosters'], datos['players_db'])
    if not df_les.empty:
        st.dataframe(df_les, hide_index=True, use_container_width=True)
    else:
        st.success("No hay lesiones críticas recientes de RBs o WRs que ofrezcan Handcuffs valiosos.")

def render_tab_vegas_odds(datos):
    st.header("🎲 Game Script & Vegas Odds (Implícitos)")
    st.write("Identifica qué equipos NFL están proyectados para tener partidos de alto puntaje (Shootouts) para alinear a tus FLEX.")
    
    df_vegas = generar_game_scripts(datos['players_db'], datos['proy'])
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(df_vegas.head(12), hide_index=True, use_container_width=True)
    with c2:
        fig = px.bar(df_vegas.head(12), x="Proy Ofensiva Total", y="Equipo NFL", orientation='h', 
                     title="Top 12 Ofensivas de la Semana (Shootout Potential)", color="Proy Ofensiva Total", color_continuous_scale="YlOrRd")
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
# =====================================================================
# MÓDULO 15: GEMINI MASTERMIND Y EXPOSICIÓN ESTADÍSTICA
# =====================================================================
def render_tab_mastermind(datos, mi_roster, riv_start, riv_nom, u_map):
    st.header("🧠 El Cerebro: Modelos Estadísticos y Gemini Mastermind")
    st.write("Transparencia algorítmica y síntesis predictiva de IA para dominar el mercado.")

    with st.expander("📊 Ver Matemáticas y Modelos Activos bajo el capó", expanded=False):
        c_m1, c_m2 = st.columns(2)
        c_m3, c_m4 = st.columns(2)
        with c_m1:
            st.markdown("### 1. Valor Esperado ($EV_{adj}$)")
            st.latex(r"EV_{adj} = \mu \times P(E) - \delta_{clima}")
            st.caption("Ajusta la proyección de Sleeper ($\mu$) por el factor de éxito del Head Coach y castiga el clima.")
        with c_m2:
            st.markdown("### 2. Varianza de Jugador ($\sigma$)")
            st.latex(r"\sigma = (100 - P_{E}) \times 0.08 + 3.0")
            st.caption("Aumenta la dispersión de puntos posibles basado en ineficiencias de la ofensiva y estatus médico.")
        with c_m3:
            st.markdown("### 3. Simulación Monte Carlo")
            st.latex(r"P(Win) = \frac{\sum_{i=1}^{5000} [S_M > S_R]}{5000}")
            st.caption("Simula 5,000 partidos iterando las curvas normales. Aplica varianza = 0 para puntos reales ya jugados.")
        with c_m4:
            st.markdown("### 4. Inferencia Bayesiana (Noticias)")
            st.latex(r"P(\mu|News) = \frac{P(News|\mu)P(\mu)}{P(News)}")
            st.caption("Actualiza la expectativa base integrando evidencia en tiempo real (RSS de ESPN/Yahoo) para alertar colapsos de proyección antes de que Sleeper los refleje.")

    st.divider()
    st.subheader("🤖 Análisis Estratégico y Anticipación de Movimientos")
    
    prob_win, _, _, _ = ejecutar_monte_carlo_dual(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'], 1000)
    df_ros = simular_oraculo_ros(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    df_heat = generar_heatmap_vulnerabilidad(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    
    df_nfl = cargar_nflverse()
    fas_unificados = obtener_mejores_waivers(datos['rosters'], datos['players_db'], datos['proy'], df_nfl)

    # NUEVO: Interceptamos nombres y noticias en background
    nombres_roster = []
    for r in datos['rosters']:
        for pid in r.get('players', []):
            p = datos['players_db'].get(str(pid), {})
            if p.get('position') in ['QB', 'RB', 'WR', 'TE']:
                nom = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                if nom: nombres_roster.append(nom.lower())
                
    with st.spinner("Compilando telemetría, cruzando con Inferencia Bayesiana de noticias..."):
        noticias = obtener_noticias_nfl(nombres_roster)
        contexto_liga = empaquetar_estado_liga_para_gemini(mi_roster, riv_start, riv_nom, prob_win, df_ros, df_heat, fas_unificados, noticias)

    prompt = f"""
    Eres el analista de datos jefe de mi equipo de Fantasy Football.
    Aquí tienes el resumen de la liga cruzando Monte Carlo, ROS, Agencia Libre y VECTORES BAYESIANOS DE NOTICIAS:
    {contexto_liga}
    
    Redacta un 'Executive Summary' dividido en estas 3 secciones (usa viñetas precisas):
    
    1. DIAGNÓSTICO MATEMÁTICO: ¿Cómo estamos en probabilidad esta semana y a futuro?
    2. SHOCK DEL MERCADO (BAYES): ¿Cómo afectan las 'Alertas' de noticias a los mánagers de la liga? ¿Quién está desesperado hoy mismo?
    3. PLAN DE ACCIÓN: Dime 2 movimientos agresivos que debo hacer para aprovechar este caos (a quién atacar por trade o quién agarrar de la lista exacta de FA).
    """

    if st.button("🧠 Generar Plan Maestro Predictivo (Gemini + Bayes)"):
        with st.spinner("Gemini analizando la matriz estadística y el impacto de las noticias..."):
            resolucion = llamar_gemini(prompt)
            st.info(resolucion)
def render_tab_noticias(datos, u_map):
    st.header("📰 Central de Noticias (ESPN & Yahoo)")
    st.write("Escaneando la red en tiempo real. Análisis de impacto impulsado por Gemini AI.")
    
    # 1. Crear un diccionario que asocie a cada jugador con su mánager
    jugador_a_manager = {}
    for r in datos['rosters']:
        mgr = u_map.get(r['owner_id'], 'Equipo Desconocido')
        for pid in r.get('players', []):
            p = datos['players_db'].get(str(pid), {})
            if p.get('position') in ['QB', 'RB', 'WR', 'TE']:
                nom = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                if nom:
                    # Guardamos el nombre en minúscula como llave para la búsqueda
                    jugador_a_manager[nom.lower()] = mgr
                    
    with st.spinner("Interceptando feeds de noticias (RSS)..."):
        # Le enviamos la lista de nombres al motor de noticias
        noticias = obtener_noticias_nfl(list(jugador_a_manager.keys()))
        
    if noticias:
        for i, n in enumerate(noticias):
            # 2. Identificar qué mánagers de tu liga están sufriendo o ganando con esta noticia
            afectados = []
            for jug_lower in n['jugadores']:
                mgr = jugador_a_manager.get(jug_lower)
                if mgr:
                    afectados.append(f"{jug_lower.title()} (Roster de: {mgr})")
            
            afectados_str = ", ".join(afectados)
            st.info(f"🏈 **Impacto en la Liga:** {afectados_str}")
            st.markdown(f"#### [{n['titulo']}]({n['link']})")
            st.write(n['desc'][:300] + "..." if len(n['desc']) > 300 else n['desc'])
            
            # 3. El botón mágico de Gemini
            if st.button(f"🧠 Analizar impacto en la liga", key=f"btn_ia_news_{i}"):
                with st.spinner("Gemini analizando repercusiones tácticas..."):
                    prompt = f"""
                    Analiza esta noticia real de la NFL: '{n['titulo']} - {n['desc']}'. 
                    Los jugadores mencionados pertenecen a los siguientes equipos de mi liga de Fantasy: {afectados_str}. 
                    Redacta un párrafo analítico y directo sobre cómo esta noticia afecta (positiva o negativamente) la estrategia de esos mánagers. 
                    Si es negativo, sugiere brevemente qué deberían hacer. Usa jerga de Fantasy Football.
                    """
                    analisis = llamar_gemini(prompt)
                    st.success(f"**Veredicto de Gemini:** {analisis}")
            st.divider()
    else:
        st.success("Sin alertas críticas ni noticias de última hora en este momento para los jugadores de la liga.")
