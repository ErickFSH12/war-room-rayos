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

    # --- PARTE 2: MULTIVERSO MASTERMIND ---
    st.subheader("🧠 Piloto Automático: Multiverso Táctico")
    st.write("El sistema generará 3 alineaciones posibles, cruzará reportes de lesiones y matchups, y te dirá exactamente qué hacer.")
    
    if st.button("🚀 Simular Universos y Generar Reporte", use_container_width=True):
        with st.spinner("Mastermind simulando 6,000 iteraciones (3 escenarios)..."):
            
            # ESCENARIO A: ACTUAL
            L_A = mi_roster['starters']
            
            # ESCENARIO B: ÓPTIMO (Máximo EV)
            L_B, cambios = optimizar_alineacion(mi_roster['starters'], banca_ids, datos['players_db'], datos['proy'], datos['reales'])
            
            # ESCENARIO C: TRAMPA DE TECHO (Reemplazar el peor titular FLEX por el mejor banca FLEX)
            L_C = list(L_B)
            flex_pos = ['RB', 'WR', 'TE']
            banca_flex = [p for p in banca_ids if datos['players_db'].get(str(p), {}).get('position') in flex_pos]
            banca_ord = sorted(banca_flex, key=lambda x: datos['proy'].get(str(x), 0.0), reverse=True)
            
            if banca_ord:
                mejor_banca = banca_ord[0]
                titulares_flex = [p for p in L_B if str(p) != "0" and datos['players_db'].get(str(p), {}).get('position') in flex_pos]
                titulares_ord = sorted(titulares_flex, key=lambda x: datos['proy'].get(str(x), 0.0))
                if titulares_ord:
                    peor_titular = titulares_ord[0]
                    L_C[L_C.index(peor_titular)] = mejor_banca

            # CALCULAR PROBABILIDADES
            prob_A, _, _, _ = ejecutar_monte_carlo_dual(L_A, riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)
            prob_B, _, _, _ = ejecutar_monte_carlo_dual(L_B, riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)
            prob_C, _, _, _ = ejecutar_monte_carlo_dual(L_C, riv_start, datos['players_db'], datos['proy'], datos['reales'], 2000)

            # RENDERIZAR CUADRO COMPARATIVO
            st.markdown("### 📊 Cuadro Comparativo de Probabilidades")
            c1, c2, c3 = st.columns(3)
            
            def renderizar_lista(alineacion):
                return "<br>".join([f"• {datos['players_db'].get(str(p),{}).get('last_name','')}" for p in alineacion if str(p) != "0"])

            c1.info(f"<h4 style='text-align: center;'>Escenario A<br>(Tu Actual)</h4><h1 style='text-align: center;'>{prob_A}%</h1><div style='font-size: 12px;'>{renderizar_lista(L_A)}</div>", unsafe_allow_html=True)
            c2.success(f"<h4 style='text-align: center;'>Escenario B<br>(Óptimo IA)</h4><h1 style='text-align: center;'>{prob_B}%</h1><div style='font-size: 12px;'>{renderizar_lista(L_B)}</div>", unsafe_allow_html=True)
            c3.warning(f"<h4 style='text-align: center;'>Escenario C<br>(Alternativo)</h4><h1 style='text-align: center;'>{prob_C}%</h1><div style='font-size: 12px;'>{renderizar_lista(L_C)}</div>", unsafe_allow_html=True)

            st.divider()

            # EXTRAER CONTEXTO (LESIONES Y EQUIPOS) PARA GEMINI
            ids_unicos = set(L_A + L_B + L_C)
            info_jugadores = []
            for pid in ids_unicos:
                if str(pid) != "0":
                    p = datos['players_db'].get(str(pid), {})
                    nom = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                    eq = p.get('team', 'FA')
                    inj = p.get('injury_status', 'Sano')
                    if not inj: inj = 'Sano'
                    proy = round(datos['proy'].get(str(pid), 0.0), 1)
                    info_jugadores.append(f"- {nom} (Eq: {eq}) | Proy: {proy} | Salud: {inj}")
            contexto_medico = "\n".join(info_jugadores)

            def nombrar_crudo(alineacion):
                return ", ".join([datos['players_db'].get(str(p),{}).get('last_name','') for p in alineacion if str(p) != "0"])

            prompt = f"""
            Eres el Analista Jefe y Director Médico de mi War Room de Fantasy.
            He simulado 3 alineaciones distintas mediante Monte Carlo (2000 iteraciones c/u):
            
            - ESCENARIO A (Mi alineación actual): Probabilidad {prob_A}%. (Jugadores: {nombrar_crudo(L_A)})
            - ESCENARIO B (Óptimo Matemático): Probabilidad {prob_B}%. (Jugadores: {nombrar_crudo(L_B)})
            - ESCENARIO C (Alternativa de riesgo): Probabilidad {prob_C}%. (Jugadores: {nombrar_crudo(L_C)})
            
            CONTEXTO DE JUGADORES (Salud y Equipos para matchups):
            {contexto_medico}
            
            Redacta un REPORTE EJECUTIVO TÁCTICO Y MÉDICO dirigido al Head Coach.
            Estructura requerida:
            1. 📉 **¿Por qué las otras opciones fallan?:** Destroza los Escenarios con menor probabilidad. Menciona específicamente las lesiones ('Salud') y los enfrentamientos de la vida real de los equipos ('Eq') que los hacen una trampa.
            2. 🏆 **El Camino a la Victoria:** Defiende por qué el Escenario ganador es el mejor. Justifica con la probabilidad de victoria y el contexto médico de sus jugadores.
            3. ⚔️ **Veredicto Final:** La instrucción exacta de a quién iniciar y a quién sentar en Sleeper.
            """

            with st.spinner("Cruzando reportes médicos, defensas rivales y probabilidad matemática..."):
                reporte_ia = llamar_gemini(prompt)
                st.markdown("### 📝 Diagnóstico de IA: Lesiones & Matchups")
                st.info(reporte_ia)

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
