import streamlit as st
import requests
import numpy as np
import pandas as pd
from google import genai
import xml.etree.ElementTree as ET

# --- CONSTANTES GLOBALES ---
API_GEMINI = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else ""
SLEEPER_USERNAME = "ericks1207"
MI_EQUIPO_NOMBRE = "Los Rayos de Jalisco"
client = genai.Client(api_key=API_GEMINI)

ESTADIOS_COORDS = {"KC": (39.0997, -94.5786), "LV": (36.0909, -115.1833), "DEN": (39.7439, -105.0201), "NYJ": (40.8135, -74.0744), "MIN": (44.9738, -93.2581), "SF": (37.4033, -121.9694), "ARI": (33.5276, -112.2626), "BUF": (42.7738, -78.7870), "BAL": (39.2779, -76.6227), "PHI": (39.9008, -75.1675), "PIT": (40.4468, -80.0158), "JAX": (30.3239, -81.6373), "NO": (29.9511, -90.0812), "IND": (39.7601, -86.1639), "TEN": (36.1665, -86.7713), "LAR": (33.9535, -118.3390)}
HC_EQUIPOS_REALES = {"KC": {"hc": "Andy Reid", "inf": 4}, "LV": {"hc": "Antonio Pierce", "inf": 3}, "DEN": {"hc": "Sean Payton", "inf": 3}, "NYJ": {"hc": "Aaron Glenn", "inf": 2}, "MIN": {"hc": "Kevin O'Connell", "inf": 4}, "SF": {"hc": "Kyle Shanahan", "inf": 4}, "ARI": {"hc": "Jonathan Gannon", "inf": 2}, "BUF": {"hc": "Sean McDermott", "inf": 4}, "BAL": {"hc": "John Harbaugh", "inf": 4}, "PHI": {"hc": "Nick Sirianni", "inf": 4}, "PIT": {"hc": "Mike Tomlin", "inf": 3}, "JAX": {"hc": "Doug Pederson", "inf": 3}, "NO": {"hc": "Dennis Allen", "inf": 2}, "IND": {"hc": "Shane Steichen", "inf": 3}, "TEN": {"hc": "Brian Callahan", "inf": 3}, "LAR": {"hc": "Sean McVay", "inf": 4}}

def obtener_info_hc(eq): return HC_EQUIPOS_REALES.get(eq, {"hc": "Estándar", "inf": 3})
def get_proy(pid, pos, dict_p): return round(dict_p[pid], 1) if pid in dict_p and dict_p[pid]>0 else {"QB":17.5, "RB":13.5, "WR":13.0, "TE":8.8, "K":8.0, "DEF":7.5}.get(pos, 10.0)
def calc_prob(inf, cli, inj): return 0.0 if inj in ['Out', 'Doubtful', 'IR'] else round(max(25.0, min(95.0, (inf * 20.0) - (cli * 7.5))), 1)

@st.cache_data(ttl=3600)
def consultar_clima(eq):
    lat, lon = ESTADIOS_COORDS.get(eq, (39.0997, -94.5786))
    try:
        res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m", timeout=3).json()
        pr, vi = res.get("current", {}).get("precipitation", 0.0), res.get("current", {}).get("wind_speed_10m", 10.0)
        return f"{res.get('current', {}).get('temperature_2m', 20.0)}°C, V:{vi}km/h", 3 if (pr>4 or vi>35) else (2 if (pr>1 or vi>20) else (1 if vi>12 else 0))
    except: return "Domo", 0

@st.cache_data(ttl=50)
def extraer_datos_sleeper(user):
    base = "https://api.sleeper.app/v1"
    uid = requests.get(f"{base}/user/{user}").json().get("user_id")
    state = requests.get(f"{base}/state/nfl").json()
    ssn, wk = str(state.get("season", "2026")), state.get("week", 1)
    
    lgs = requests.get(f"{base}/user/{uid}/leagues/nfl/{ssn}").json()
    if not lgs: lgs = requests.get(f"{base}/user/{uid}/leagues/nfl/{str(int(ssn)-1)}").json()
    lid = lgs[0].get("league_id")
    
    proy, reals = {}, {}
    try:
        for pid, d in requests.get(f"https://api.sleeper.com/v1/projections/nfl/regular/{ssn}/{wk}").json().items():
            if isinstance(d, dict): proy[str(pid)] = float(d.get("pts_ppr", 0.0))
        for pid, d in requests.get(f"https://api.sleeper.com/v1/stats/nfl/regular/{ssn}/{wk}").json().items():
            if isinstance(d, dict) and ("pts_ppr" in d or d.get("gp", 0) > 0):
                reals[str(pid)] = float(d.get("pts_ppr", 0.0))
    except: pass

    trs, wvs = [], []
    for w in range(1, wk + 1):
        try:
            for t in requests.get(f"{base}/league/{lid}/transactions/{w}").json():
                if t.get("status") == "complete":
                    if t.get("type") == "trade": trs.append(t)
                    elif t.get("type") in ["waiver", "free_agent"]: wvs.append(t)
        except: pass
    return {"users": requests.get(f"{base}/league/{lid}/users").json(), "rosters": requests.get(f"{base}/league/{lid}/rosters").json(), "matchups": requests.get(f"{base}/league/{lid}/matchups/{wk}").json(), "players_db": requests.get(f"{base}/players/nfl").json(), "proy": proy, "reales": reals, "semana": wk, "trades": trs, "waivers": wvs}

@st.cache_data(ttl=86400)
def cargar_nflverse():
    try: return pd.read_csv("https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv", low_memory=False).query("season >= 2024").copy()
    except: return pd.DataFrame()

def ejecutar_monte_carlo_dual(m_ids, r_ids, players_db, proyecciones, reales, n_sims=5000):
    def simular(ids):
        sims = np.zeros(n_sims)
        for pid in ids:
            if str(pid) in reales: sims += reales[str(pid)]
            else:
                p = players_db.get(str(pid), {})
                if p.get('injury_status') in ['Out', 'IR']: continue
                prob = calc_prob(obtener_info_hc(p.get('team', 'FA'))['inf'], consultar_clima(p.get('team', 'FA'))[1], p.get('injury_status'))
                proy = get_proy(str(pid), p.get('position', 'N/A'), proyecciones)
                sims += np.clip(np.random.normal(proy, (100-prob)*0.08 + 3.0, n_sims), 0, None)
        return sims
    sm, sr = simular(m_ids), simular(r_ids) if r_ids else np.zeros(n_sims)
    return round((np.sum(sm > sr)/n_sims)*100, 1), round(float(np.mean(sm)),1), sm, sr

def optimizar_alineacion(starters, bench, players_db, proyecciones, reales):
    opt, cambios = list(starters), []
    banca_v = [{"id": b, "pos": players_db.get(str(b),{}).get('position'), "nom": players_db.get(str(b),{}).get('last_name'), "ev": get_proy(str(b), players_db.get(str(b),{}).get('position'), proyecciones) * (calc_prob(obtener_info_hc(players_db.get(str(b),{}).get('team'))['inf'], 0, None)/100)} for b in bench if str(b) not in reales and players_db.get(str(b),{}).get('injury_status') not in ['Out','IR']]
    for i, s in enumerate(opt):
        if str(s) in reales: continue
        p = players_db.get(str(s), {})
        pos, inj = p.get('position'), p.get('injury_status')
        prob = calc_prob(obtener_info_hc(p.get('team'))['inf'], 0, inj)
        ev_s = get_proy(str(s), pos, proyecciones) * (prob/100)
        
        if prob < 50 or inj == 'Questionable':
            cand = [b for b in banca_v if b["pos"] == pos and b["ev"] > ev_s]
            if cand:
                mejor = max(cand, key=lambda x: x["ev"])
                cambios.append(f"🔄 **{pos}**: Sale {p.get('last_name')} ➔ Entra **{mejor['nom']}**")
                opt[i] = mejor["id"]
                banca_v = [b for b in banca_v if b["id"] != mejor["id"]]
    return opt, cambios

def formatear_roster_df(ids, players_db, proy, reales, etiqueta):
    data = []
    for pid in ids:
        p = players_db.get(str(pid), {})
        nom = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        pos, eq, inj = p.get('position', 'N/A'), p.get('team', 'FA'), p.get('injury_status')
        estatus = f"🏥 {inj}" if inj in ['Out', 'IR', 'Questionable'] else "✅ Activo"
        pts_proy = get_proy(str(pid), pos, proy)
        pts_real = reales.get(str(pid))
        trk = f"{pts_real} (Final)" if pts_real is not None else f"{pts_proy} (Proy)"
        data.append({"Jugador": nom, "Pos": f"{pos}-{eq}", "Rol": etiqueta, "Estatus": estatus, "Tracking": trk})
    return pd.DataFrame(data)

@st.cache_data(ttl=1800)
def llamar_gemini(prompt):
    try: return client.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt).text
    except: return "Conexión a ESPN interrumpida."
# --- NUEVA TELEMETRÍA: CÁLCULO DE DRIFT Y EMPAREJAMIENTO SIDE-BY-SIDE ---
def calcular_drift_probabilidad(m_ids, r_ids, players_db, proyecciones, reales, n_sims=3000):
    # 1. Simulación Base (Sin datos reales, como estaba antes de iniciar la semana)
    _, _, sm_base, sr_base = ejecutar_monte_carlo_dual(m_ids, r_ids, players_db, proyecciones, {}, n_sims)
    prob_base = round((np.sum(sm_base > sr_base) / n_sims) * 100.0, 1) if r_ids else 100.0
    
    # 2. Simulación Live (Congelando datos reales)
    _, _, sm_live, sr_live = ejecutar_monte_carlo_dual(m_ids, r_ids, players_db, proyecciones, reales, n_sims)
    prob_live = round((np.sum(sm_live > sr_live) / n_sims) * 100.0, 1) if r_ids else 100.0
    
    delta = round(prob_live - prob_base, 1)
    return prob_base, prob_live, delta

def generar_comparativa_side_by_side(m_ids, r_ids, players_db, proy, reales):
    filas = []
    max_len = max(len(m_ids), len(r_ids))
    for i in range(max_len):
        # Mi jugador
        if i < len(m_ids):
            pid_m = str(m_ids[i])
            pm = players_db.get(pid_m, {})
            nom_m = f"{pm.get('first_name','')[:1]}. {pm.get('last_name','')}".strip()
            pos_m = pm.get('position', 'FLEX')
            pts_m = reales.get(pid_m, get_proy(pid_m, pos_m, proy))
            st_m = "🔒 Final" if pid_m in reales else "⏳ Proy"
        else:
            nom_m, pos_m, pts_m, st_m = "-", "-", 0.0, "-"
            
        # Jugador rival
        if i < len(r_ids):
            pid_r = str(r_ids[i])
            pr = players_db.get(pid_r, {})
            nom_r = f"{pr.get('first_name','')[:1]}. {pr.get('last_name','')}".strip()
            pos_r = pr.get('position', 'FLEX')
            pts_r = reales.get(pid_r, get_proy(pid_r, pos_r, proy))
            st_r = "🔒 Final" if pid_r in reales else "⏳ Proy"
        else:
            nom_r, pos_r, pts_r, st_r = "-", "-", 0.0, "-"

        filas.append({
            "Pos (Rayos)": pos_m,
            "Rayos de Jalisco": nom_m,
            "Pts (Rayos)": pts_m,
            "Estado Rayos": st_m,
            "VS": "⚔️",
            "Estado Rival": st_r,
            "Pts (Rival)": pts_r,
            "Rival": nom_r,
            "Pos (Rival)": pos_r
        })
    return pd.DataFrame(filas)
# =====================================================================
# MOTORES PARA LOS 5 MÓDULOS AVANZADOS
# =====================================================================

def generar_heatmap_vulnerabilidad(rosters, players_db, proy, u_map):
    datos = []
    for r in rosters:
        mgr = u_map.get(r['owner_id'], 'Eq')
        pts = {'QB': 0.0, 'RB': 0.0, 'WR': 0.0, 'TE': 0.0}
        for pid in r.get('players', []):
            pos = players_db.get(str(pid), {}).get('position', '')
            if pos in pts: pts[pos] += get_proy(str(pid), pos, proy)
        datos.append({'Manager': mgr, 'QB': pts['QB'], 'RB': pts['RB'], 'WR': pts['WR'], 'TE': pts['TE']})
    return pd.DataFrame(datos).set_index('Manager')

def simular_oraculo_ros(rosters, players_db, proy, u_map):
    # Proxy de simulación Rest of Season (ROS) basado en el EV total del roster y profundidad
    datos_ros = []
    for r in rosters:
        mgr = u_map.get(r['owner_id'], 'Eq')
        ev_total = sum([get_proy(str(p), players_db.get(str(p), {}).get('position', 'FA'), proy) for p in r.get('players', [])])
        starters_ev = sum([get_proy(str(p), players_db.get(str(p), {}).get('position', 'FA'), proy) for p in r.get('starters', [])])
        profundidad = ev_total - starters_ev
        
        # Fórmula interna ponderada: 70% titulares, 30% profundidad
        poder_ros = (starters_ev * 0.7) + (profundidad * 0.3)
        datos_ros.append({'Manager': mgr, 'Poder ROS': poder_ros, 'EV Titulares': starters_ev, 'EV Banca': profundidad})
    
    df_ros = pd.DataFrame(datos_ros).sort_values('Poder ROS', ascending=False)
    # Normalizar a % de campeonato (aproximación)
    df_ros['Prob Campeonato %'] = round((df_ros['Poder ROS'] / df_ros['Poder ROS'].sum()) * 100, 1)
    return df_ros

def evaluar_trade_interactivo(jugador_dar, jugador_recibir, delta_math, contexto_fuentes, proy_dar, proy_recibir, noticias_jugadores):
    prompt = f"""
    Eres un experto analista de Fantasy Football (Nivel Conserje / Asesor Personal).
    Estoy evaluando este trade exacto en mi liga:
    - DOY A: {jugador_dar} (Proy actual: {proy_dar} pts)
    - RECIBO A: {jugador_recibir} (Proy actual: {proy_recibir} pts)
    
    IMPACTO MATEMÁTICO (MONTE CARLO):
    Si hago este trade, mis probabilidades de ganar el duelo de esta semana cambian en: {delta_math}%
    
    INTERCEPTACIÓN RSS (NOTICIAS EN VIVO):
    {noticias_jugadores}
    
    FUENTES DE CONTEXTO ADICIONAL (ESTILO NOTEBOOK LM):
    {contexto_fuentes if contexto_fuentes else "No se proveyeron fuentes externas."}
    
    Dame un análisis rápido, crudo y directo dividido en estas 3 secciones precisas:
    1. 🔍 SCOUTING: ¿Cuál es el verdadero valor de mercado de ambos jugadores? ¿Estoy comprando bajo o vendiendo alto?
    2. ⚖️ ANÁLISIS DEL TRADE: Analiza el cruce de las proyecciones, el impacto matemático estricto ({delta_math}%) y las noticias/fuentes. ¿Tiene sentido estratégico a largo plazo?
    3. 🎯 VEREDICTO FINAL: Aceptar, Rechazar, o sugiere una Contraoferta exacta.
    """
    return llamar_gemini(prompt)

def escanear_handcuffs(rosters, players_db):
    lesionados = []
    ocu = set([str(pid) for r in rosters for pid in r.get('players', [])])
    
    for r in rosters:
        for pid in r.get('players', []):
            p = players_db.get(str(pid), {})
            if p.get('position') in ['RB', 'WR'] and p.get('injury_status') in ['Out', 'IR', 'Doubtful']:
                eq = p.get('team', 'FA')
                # Buscar el reemplazo en el mismo equipo que esté Libre (FA)
                suplentes_libres = []
                for spid, sp in players_db.items():
                    if sp.get('team') == eq and sp.get('position') == p.get('position') and str(spid) not in ocu and sp.get('status') != 'Inactive':
                        suplentes_libres.append(f"{sp.get('last_name')} (FA)")
                
                lesionados.append({
                    "Titular Caído": f"{p.get('first_name', '')[:1]}. {p.get('last_name')} ({p.get('position')})",
                    "Equipo": eq,
                    "Estatus": p.get('injury_status'),
                    "Handcuffs Libres": ", ".join(suplentes_libres[:2]) if suplentes_libres else "Ninguno valioso"
                })
    return pd.DataFrame(lesionados)

def generar_game_scripts(players_db, proy):
    # Simula el Over/Under de Las Vegas sumando las proyecciones de los Skill Players por equipo
    eq_pts = {}
    for pid, p in players_db.items():
        eq = p.get('team')
        if eq and eq != 'FA' and p.get('position') in ['QB', 'RB', 'WR', 'TE']:
            eq_pts[eq] = eq_pts.get(eq, 0) + proy.get(str(pid), 0.0)
            
    df_vegas = pd.DataFrame([{"Equipo NFL": k, "Proy Ofensiva Total": round(v, 1)} for k, v in eq_pts.items() if v > 20])
    return df_vegas.sort_values("Proy Ofensiva Total", ascending=False)
    # --- NUEVA TELEMETRÍA: GEMINI MASTERMIND ---
# --- TELEMETRÍA CORREGIDA PARA GEMINI MASTERMIND ---
def empaquetar_estado_liga_para_gemini(mi_roster, riv_start, riv_nom, prob_win, df_ros, df_heat, lista_fas, noticias_rss):
    mi_ros = df_ros[df_ros['Manager'] == MI_EQUIPO_NOMBRE]['Prob Campeonato %'].values[0] if not df_ros.empty else "N/A"
    
    if not df_heat.empty:
        vuln = df_heat.sum(axis=1).idxmin()
        vuln_pts = round(df_heat.sum(axis=1).min(), 1)
    else:
        vuln, vuln_pts = "N/A", 0
        
    top_fas_str = ", ".join([f"{f['nombre_completo']} ({f['pos']} - {f['eq']})" for f in lista_fas[:15]])

    # Procesamiento Bayesiano (NLP Básico) de Noticias
    impactos_bayes = []
    catastrofe = ['tear', 'torn', 'out for season', 'carted off', 'fracture', 'surgery', 'out']
    duda = ['questionable', 'limited', 'hamstring', 'sprain', 'protocol', 'concussion', 'missed practice']
    oportunidad = ['named starter', 'first team reps', 'promoted', 'cleared']
    
    if noticias_rss:
        for n in noticias_rss:
            txt = (n['titulo'] + " " + n['desc']).lower()
            jugadores_afectados = ", ".join(n['jugadores']).title()
            
            if any(w in txt for w in catastrofe):
                impactos_bayes.append(f"🚨 ALERTA ROJA (Colapso Bayesiano): {jugadores_afectados} con posible lesión severa. Su proyección matemática y EV caen a 0. Mánager dueño requiere reemplazo inmediato.")
            elif any(w in txt for w in duda):
                impactos_bayes.append(f"⚠️ ALERTA AMARILLA (Aumento de Varianza): {jugadores_afectados} con riesgo físico. La campana de Gauss de este jugador se ensancha, volviéndolo muy riesgoso de alinear.")
            elif any(w in txt for w in oportunidad):
                impactos_bayes.append(f"📈 ALERTA VERDE (Boost de EV): {jugadores_afectados} tiene nueva oportunidad confirmada. Su valor esperado sube por encima de su proyección base.")

    alertas_str = "\n- ".join(impactos_bayes) if impactos_bayes else "Sin anomalías mediáticas (Prior = Posterior)."

    estado = f"""
    ESTADO GLOBAL DE LA LIGA:
    - Mi Equipo: {MI_EQUIPO_NOMBRE}
    - Mi Rival de esta semana: {riv_nom}
    - Mi Probabilidad de Victoria (Monte Carlo): {prob_win}%
    - Mi Fuerza Resto de Temporada (ROS): Probabilidad de campeonato en {mi_ros}%.
    - Mánager más vulnerable hoy (Objetivo de Trade): '{vuln}' (Proy total: {vuln_pts} pts).
    - MEJORES AGENTES LIBRES (WAIVERS) DISPONIBLES: {top_fas_str}.
    
    VECTORES DE RIESGO BAYESIANO (IMPACTO DE NOTICIAS EN VIVO):
    - {alertas_str}
    
    REGLA DE ORO: 
    Cruza los Vectores de Riesgo con el Mánager Vulnerable. Tienes PROHIBIDO sugerir un Agente Libre que no esté explícitamente en la lista de arriba.
    """
    return estado
def render_tab_mastermind(datos, mi_roster, riv_start, riv_nom, u_map):
    st.header("🧠 El Cerebro: Modelos Estadísticos y Gemini Mastermind")
    st.write("Transparencia algorítmica y síntesis predictiva de IA para dominar el mercado.")

    # 1. TRANSPARENCIA ESTADÍSTICA (EXPOSICIÓN DE LOS MODELOS)
    with st.expander("📊 Ver Matemáticas y Modelos Activos bajo el capó", expanded=False):
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.markdown("### 1. Valor Esperado ($EV_{adj}$)")
            st.latex(r"EV_{adj} = \mu \times P(E) - \delta_{clima}")
            st.caption("Ajusta la proyección de Sleeper ($\mu$) por el factor de éxito del Head Coach y castiga condiciones climáticas adversas.")
        with c_m2:
            st.markdown("### 2. Varianza de Jugador ($\sigma$)")
            st.latex(r"\sigma = (100 - P_{E}) \times 0.08 + 3.0")
            st.caption("Los jugadores en ofensivas poco confiables o con estatus 'Questionable' reciben una campana de Gauss más ancha (mayor riesgo).")
        with c_m3:
            st.markdown("### 3. Simulación Monte Carlo")
            st.latex(r"P(Win) = \frac{\sum_{i=1}^{5000} [S_M > S_R]}{5000}")
            st.caption("Se simulan 5,000 partidos iterando las curvas normales. Los puntos que ya sucedieron el jueves asumen $\sigma = 0$ (varianza nula).")

    st.divider()

    # 2. SÍNTESIS DE GEMINI (EL PLAN MAESTRO)
    st.subheader("🤖 Análisis Estratégico y Anticipación de Movimientos")
    
    # Recolectar datos en background para alimentar a la IA
    prob_win, _, _, _ = ejecutar_monte_carlo_dual(mi_roster['starters'], riv_start, datos['players_db'], datos['proy'], datos['reales'], 1000)
    
    # Importar funciones de otros módulos de forma segura
    from core_logic import simular_oraculo_ros, generar_heatmap_vulnerabilidad
    df_ros = simular_oraculo_ros(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    df_heat = generar_heatmap_vulnerabilidad(datos['rosters'], datos['players_db'], datos['proy'], u_map)
    
    fas = []
    ocu = set([str(pid) for r in datos['rosters'] for pid in r.get('players', [])])
    for pid, p in datos['players_db'].items():
        if str(pid) not in ocu and p.get('status') != 'Inactive' and p.get('team') != 'FA' and p.get('position') in ['RB','WR']:
            pr = get_proy(str(pid), p.get('position'), datos['proy'])
            if pr > 6.0: fas.append({'nom': p.get('last_name'), 'pos': p.get('position'), 'ev': pr})
    fas.sort(key=lambda x: x['ev'], reverse=True)

    # Empaquetar
    from core_logic import empaquetar_estado_liga_para_gemini
    contexto_liga = empaquetar_estado_liga_para_gemini(mi_roster, riv_start, riv_nom, prob_win, df_ros, df_heat, fas)

    prompt = f"""
    Eres el analista de datos jefe (Data Scientist) de mi equipo de Fantasy Football.
    Aquí tienes el resumen estadístico de la liga cruzando Monte Carlo, modelos ROS y Agencia Libre:
    {contexto_liga}
    
    Necesito que redactes un 'Executive Summary' dividido estrictamente en estas 3 secciones (usa viñetas precisas, sin introducciones largas):
    
    1. DIAGNÓSTICO ESTADÍSTICO: ¿Cómo estamos realmente en probabilidad de esta semana y a futuro?
    2. ANTICIPACIÓN DE MERCADO: ¿Qué movimientos desesperados van a hacer los demás mánagers basándote en la vulnerabilidad actual de la liga?
    3. PLAN DE ACCIÓN RECOMENDADO: Dime exactamente 2 movimientos que debo hacer (a quién atacar por trade o quién agarrar de FA) para aprovechar las matemáticas a mi favor.
    """

    if st.button("🧠 Procesar Telemetría y Generar Plan Maestro (Gemini API)"):
        with st.spinner("Conectando con la IA... analizando vectores de probabilidad..."):
            resolucion = llamar_gemini(prompt)
            st.info(resolucion)
# --- NUEVO MOTOR UNIFICADO DE AGENCIA LIBRE (WAIVERS) ---
def obtener_mejores_waivers(rosters, players_db, proy, df_nfl=None):
    if df_nfl is None: df_nfl = pd.DataFrame()
    ocu = set([str(pid) for r in rosters for pid in r.get('players', [])])
    fas = []
    
    for pid, p in players_db.items():
        if str(pid) in ocu or p.get('status') == 'Inactive' or p.get('position') not in ['QB','RB','WR','TE','K','DEF']: 
            continue
            
        pos, eq = p.get('position'), p.get('team', 'FA')
        if eq == 'FA' or not eq: continue
        pr = get_proy(str(pid), pos, proy)
        
        if pr > 5.0:
            prob = calc_prob(obtener_info_hc(eq)['inf'], consultar_clima(eq)[1], p.get('injury_status'))
            ev = round(pr*(prob/100), 1)
            
            # Cruce dinámico con NFLVerse para obtener Media Histórica real
            hist_avg = 0.0
            if not df_nfl.empty and pos in ['QB', 'RB', 'WR', 'TE']:
                nom_completo = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
                try:
                    col_name = 'player_display_name' if 'player_display_name' in df_nfl.columns else 'player_name'
                    match = df_nfl[df_nfl[col_name] == nom_completo]
                    if not match.empty:
                        hist_avg = round(match['fantasy_points_ppr'].mean(), 1)
                except: pass
                    
            fas.append({
                'id': pid, 'nom': p.get('last_name'), 
                'nombre_completo': f"{p.get('first_name','')} {p.get('last_name')}",
                'pos': pos, 'eq': eq, 'ev': ev, 'proy': pr, 
                'hist_avg': hist_avg, 'inj': p.get('injury_status') or 'Sano'
            })
            
    fas.sort(key=lambda x: x['ev'], reverse=True)
    return fas
# --- MÓDULO DE NOTICIAS RSS (ESPN Y YAHOO) ---
@st.cache_data(ttl=3600) # Cachear noticias 1 hora
def obtener_noticias_nfl(nombres_jugadores):
    urls = [
        "https://www.espn.com/espn/rss/nfl/news",
        "https://sports.yahoo.com/nfl/rss/"
    ]
    noticias = []
    
    for url in urls:
        try:
            resp = requests.get(url, timeout=5)
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ""
                desc = item.find('description').text if item.find('description') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                
                texto_full = (title + " " + desc).lower()
                # Filtrar solo si se menciona un jugador de la liga
                mencionados = [nom for nom in nombres_jugadores if nom.lower() in texto_full]
                
                if mencionados:
                    noticias.append({
                        "titulo": title,
                        "desc": desc,
                        "link": link,
                        "jugadores": mencionados
                    })
        except: pass
    
    # Eliminar noticias duplicadas
    vistos = set()
    noticias_unicas = []
    for n in noticias:
        if n['titulo'] not in vistos:
            vistos.add(n['titulo'])
            noticias_unicas.append(n)
            
    return noticias_unicas
