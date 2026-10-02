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
