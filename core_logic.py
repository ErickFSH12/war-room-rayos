import streamlit as st
import requests
import numpy as np
import pandas as pd
from google import genai

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

def evaluar_trade(mi_roster_ids, rival_roster_ids, pid_dar, pid_recibir, players_db, proy, reales):
    m_new = [p for p in mi_roster_ids if str(p) != str(pid_dar)] + [pid_recibir]
    r_new = [p for p in rival_roster_ids if str(p) != str(pid_recibir)] + [pid_dar]
    
    # Probabilidad antes del trade
    prob_base, _, _, _ = ejecutar_monte_carlo_dual(mi_roster_ids, rival_roster_ids, players_db, proy, reales, 1500)
    # Probabilidad después del trade
    prob_post, _, _, _ = ejecutar_monte_carlo_dual(m_new, r_new, players_db, proy, reales, 1500)
    
    return prob_base, prob_post, round(prob_post - prob_base, 1)

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
def empaquetar_estado_liga_para_gemini(mi_roster, riv_start, riv_nom, prob_win, df_ros, df_heat, fas):
    # Compilar un diccionario de estado global para que la IA lo analice
    mi_ros = df_ros[df_ros['Manager'] == MI_EQUIPO_NOMBRE]['Prob Campeonato %'].values[0] if not df_ros.empty else "N/A"
    
    # Encontrar al manager más vulnerable basado en el Heatmap
    if not df_heat.empty:
        vuln = df_heat.sum(axis=1).idxmin()
        vuln_pts = round(df_heat.sum(axis=1).min(), 1)
    else:
        vuln, vuln_pts = "N/A", 0
        
    top_fas = [f"{f['nom']} ({f['pos']}) EV:{f['ev']}" for f in fas[:3]] if fas else []

    estado = f"""
    ESTADO GLOBAL DE LA LIGA:
    - Mi Equipo: {MI_EQUIPO_NOMBRE}
    - Mi Rival de esta semana: {riv_nom}
    - Mi Probabilidad de Victoria (Monte Carlo): {prob_win}%
    - Mi Fuerza Resto de Temporada (ROS): Top/Probabilidad de campeonato calculada en {mi_ros}%.
    - Mánager más vulnerable hoy (Objetivo de Trade): '{vuln}' (Proy total: {vuln_pts} pts).
    - Mejores Agentes Libres (Waivers) detectados por Modelo EV: {', '.join(top_fas)}.
    """
    return estado
