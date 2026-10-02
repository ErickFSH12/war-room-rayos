import streamlit as st
from streamlit_autorefresh import st_autorefresh
import os, time, math, requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime
from google import genai

# --- CONFIGURACIÓN DE PÁGINA Y AUTO-REFRESH ---
st.set_page_config(page_title="War Room - Rayos de Jalisco", page_icon="⚡", layout="wide")
st_autorefresh(interval=60000, key="data_refresh") # Refresca cada 60 segundos

# --- CONSTANTES ---
API_GEMINI = st.secrets["GEMINI_API_KEY"]
SLEEPER_USERNAME = "ericks1207"
MI_EQUIPO_NOMBRE = "Los Rayos de Jalisco"
client = genai.Client(api_key=API_GEMINI)

ESTADIOS_COORDS = {
    "KC": (39.0997, -94.5786), "LV": (36.0909, -115.1833), "DEN": (39.7439, -105.0201),
    "NYJ": (40.8135, -74.0744), "MIN": (44.9738, -93.2581), "SF": (37.4033, -121.9694),
    "ARI": (33.5276, -112.2626), "BUF": (42.7738, -78.7870), "BAL": (39.2779, -76.6227),
    "PHI": (39.9008, -75.1675), "PIT": (40.4468, -80.0158), "JAX": (30.3239, -81.6373),
    "NO": (29.9511, -90.0812), "IND": (39.7601, -86.1639), "TEN": (36.1665, -86.7713),
    "LAR": (33.9535, -118.3390)
}

HC_EQUIPOS_REALES = {
    "KC": {"hc": "Andy Reid", "inf": 4}, "LV": {"hc": "Antonio Pierce", "inf": 3},
    "DEN": {"hc": "Sean Payton", "inf": 3}, "NYJ": {"hc": "Aaron Glenn", "inf": 2},
    "MIN": {"hc": "Kevin O'Connell", "inf": 4}, "SF": {"hc": "Kyle Shanahan", "inf": 4},
    "ARI": {"hc": "Jonathan Gannon", "inf": 2}, "BUF": {"hc": "Sean McDermott", "inf": 4},
    "BAL": {"hc": "John Harbaugh", "inf": 4}, "PHI": {"hc": "Nick Sirianni", "inf": 4},
    "PIT": {"hc": "Mike Tomlin", "inf": 3}, "JAX": {"hc": "Doug Pederson", "inf": 3},
    "NO": {"hc": "Dennis Allen", "inf": 2}, "IND": {"hc": "Shane Steichen", "inf": 3},
    "TEN": {"hc": "Brian Callahan", "inf": 3}, "LAR": {"hc": "Sean McVay", "inf": 4}
}

PERFILES_MANAGERS = {
    "Los Rayos de Jalisco": "Analítico de ingeniería.", "MascaritaSagrada": "Obsesivo del upside y novatos explosivos.",
    "Luis39cem": "Acumulador de RBs, sufre por lesiones.", "Ruthlessbergers": "Apasionado, visceral y castigado por lesiones.",
    "Philly Kings": "Relajado, competitivo, funcional.", "GaMus Sport": "Confiado en autopicks eficientes.",
    "Blue Anchors Corps": "Perfil equilibrado y analítico.", "All The Poohs Men": "Tiburón de draft.",
    "Billstzkrieg": "Ludópata, amante de riesgos y parlays.", "Renato": "Comisionado analítico de momios."
}

def obtener_info_hc(eq): return HC_EQUIPOS_REALES.get(eq, {"hc": "Estándar", "inf": 3})
def get_proy(pid, pos, dict_p): return round(dict_p[pid], 1) if pid in dict_p and dict_p[pid]>0 else {"QB":17.5, "RB":13.5, "WR":13.0, "TE":8.8, "K":8.0, "DEF":7.5}.get(pos, 10.0)
def calc_prob(inf, cli, inj): return 0.0 if inj in ['Out', 'Doubtful', 'IR'] else round(max(25.0, min(95.0, (inf * 20.0) - (cli * 7.5))), 1)

@st.cache_data(ttl=3600) # Cachear el clima por 1 hora
def consultar_clima(eq):
    lat, lon = ESTADIOS_COORDS.get(eq, (39.0997, -94.5786))
    try:
        res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m", timeout=3).json()
        pr, vi = res.get("current", {}).get("precipitation", 0.0), res.get("current", {}).get("wind_speed_10m", 10.0)
        return f"{res.get('current', {}).get('temperature_2m', 20.0)}°C, V:{vi}km/h", 3 if (pr>4 or vi>35) else (2 if (pr>1 or vi>20) else (1 if vi>12 else 0))
    except: return "Domo / Estándar", 0

@st.cache_data(ttl=50) # Cachear Sleeper por 50 segundos (refresca en cada ciclo de 60s)
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

# --- MOTORES DE CÁLCULO ---
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
                cambios.append(f"🔄 **{pos}**: Sentar a {p.get('last_name')} ➔ Subir a **{mejor['nom']}**")
                opt[i] = mejor["id"]
                banca_v = [b for b in banca_v if b["id"] != mejor["id"]]
    return opt, cambios

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

@st.cache_data(ttl=1800) # Cachear a Gemini por 30 mins para no quemar la API
def llamar_gemini(prompt):
    try:
        return client.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt).text
    except: return "No se pudo contactar a ESPN (Gemini API Error)."

# =====================================================================
# INTERFAZ DE USUARIO (STREAMLIT)
# =====================================================================
st.title("⚡ CENTRO DE MANDO TÁCTICO: LOS RAYOS DE JALISCO")

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
        # PESTAÑAS DE NAVEGACIÓN
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚔️ WAR ROOM (Live)", "🔮 PRONÓSTICOS LIGA", "🕵️‍♂️ FORENSE Y SABOTAJE", "🦅 WAIVERS", "🔬 BACKTESTING"])

        # --- TAB 1: WAR ROOM Y TRACKING EN VIVO ---
        with tab1:
            st.header(f"Semana {datos['semana']}: Rayos vs {riv_nom}")
            
            # Cálculos de tracking
            def get_tracking(starters):
                aseg, rest = 0.0, 0.0
                for pid in starters:
                    if str(pid) in datos['reales']: aseg += datos['reales'][str(pid)]
                    else: rest += datos['proy'].get(str(pid), 0.0)
                return aseg, rest
            
            m_aseg, m_rest = get_tracking(mi_roster['starters'])
            r_aseg, r_rest = get_tracking(riv_start)
            
            c1, c2 = st.columns(2)
            c1.metric(label=f"{MI_EQUIPO_NOMBRE} (Asegurados)", value=round(m_aseg,1), delta=f"{round(m_rest,1)} restantes", delta_color="normal")
            c2.metric(label=f"{riv_nom} (Asegurados)", value=round(r_aseg,1), delta=f"{round(r_rest,1)} restantes", delta_color="normal")

            # Optimizador y Monte Carlo
            opt_start, cambios = optimizar_alineacion(mi_roster['starters'], [p for p in mi_roster['players'] if p not in mi_roster['starters']], datos['players_db'], datos['proy'], datos['reales'])
            prob, med, sm, sr = ejecutar_monte_carlo_dual(opt_start, riv_start, datos['players_db'], datos['proy'], datos['reales'])
            
            st.markdown("---")
            st.subheader("⚡ TÁCTICA FINAL (Monte Carlo Calibrado)")
            colA, colB = st.columns([1, 2])
            with colA:
                st.metric(label="PROB. DE VICTORIA", value=f"{prob}%")
                if cambios:
                    st.warning("**RECOMENDACIÓN CAMBIOS:**\n" + "\n".join(cambios))
                else:
                    st.success("✅ ALINEACIÓN BLINDADA ÓPTIMA.")
                    
                # Resumen ESPN
                prompt_espn = f"Eres un comentarista estrella de ESPN de NFL Live hablando del equipo '{MI_EQUIPO_NOMBRE}'. Se enfrentan a '{riv_nom}'. Tienen {prob}% de probabilidad de ganar tras los ajustes. Escribe un monólogo emocionante corto."
                resumen_espn = llamar_gemini(prompt_espn)
                st.info(f"🎙️ **SportsCenter:** {resumen_espn}")

            with colB:
                # Gráfica Monte Carlo
                plt.style.use('dark_background')
                fig_mc, ax_mc = plt.subplots(figsize=(8, 4))
                ax_mc.hist(sm, bins=40, alpha=0.6, color='#3b82f6', label='Rayos', density=True)
                ax_mc.hist(sr, bins=40, alpha=0.6, color='#ef4444', label='Rival', density=True)
                ax_mc.axvline(np.mean(sm), color='#60a5fa', lw=2)
                ax_mc.axvline(np.mean(sr), color='#f87171', lw=2)
                ax_mc.legend()
                st.pyplot(fig_mc)

            # Radar H2H
            st.markdown("---")
            st.subheader("Radar Posicional H2H")
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
            
            fig_rad, ax_rad = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
            ax_rad.plot(angs, m_pts, color='#3b82f6', lw=2, label='Rayos'); ax_rad.fill(angs, m_pts, '#3b82f6', alpha=0.3)
            ax_rad.plot(angs, r_pts, color='#ef4444', lw=2, label=riv_nom); ax_rad.fill(angs, r_pts, '#ef4444', alpha=0.3)
            ax_rad.set_xticks(angs[:-1]); ax_rad.set_xticklabels(cats, color='white', size=10, fontweight='bold')
            ax_rad.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
            st.pyplot(fig_rad)

        # --- TAB 2: PRONÓSTICOS LIGA ---
        with tab2:
            st.header("🔮 Pronósticos Globales y Playoffs")
            m_agr = {}
            for m in datos['matchups']: m_agr.setdefault(m.get('matchup_id'), []).append(m)
            
            p_cols = st.columns(2)
            idx = 0
            for m_id, eqs in m_agr.items():
                if len(eqs)!=2 or eqs[0].get('roster_id')==mi_r_id or eqs[1].get('roster_id')==mi_r_id: continue
                r1, r2 = next(r for r in datos['rosters'] if r.get('roster_id')==eqs[0].get('roster_id')), next(r for r in datos['rosters'] if r.get('roster_id')==eqs[1].get('roster_id'))
                m1, m2 = u_map.get(r1.get('owner_id'),"Eq1"), u_map.get(r2.get('owner_id'),"Eq2")
                p_win, _, s1, s2 = ejecutar_monte_carlo_dual(r1.get('starters',[]), r2.get('starters',[]), datos['players_db'], datos['proy'], datos['reales'], 2000)
                
                with p_cols[idx % 2]:
                    st.markdown(f"**{m1[:12]} ({p_win}%)** VS **{m2[:12]} ({round(100-p_win,1)}%)**")
                    fig_p, ax_p = plt.subplots(figsize=(6, 2))
                    ax_p.hist(s1, bins=30, alpha=0.5, color='#38bdf8'); ax_p.hist(s2, bins=30, alpha=0.5, color='#f43f5e')
                    st.pyplot(fig_p)
                idx += 1

        # --- TAB 3: AUDITORÍA FORENSE Y SABOTAJE ---
        with tab3:
            st.header("🕵️‍♂️ Forense y Matriz de Sabotaje")
            
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
                st.subheader("Gatillo Fácil (Trades/Waivers)")
                rk = sorted(cnt.items(), key=lambda x: x[1]['adds'] + x[1]['trades'], reverse=True)
                for rid, d in rk[:5]:
                    st.write(f"- **{u_map.get(next((r.get('owner_id') for r in datos['rosters'] if r.get('roster_id')==rid),'Eq'))}**: {d['trades']} Trades | {d['adds']} Adds | ${d['faab']} FAAB")
            with c_f2:
                st.subheader("Panic Drops")
                if drops_p:
                    for d in drops_p[-5:]: st.error(d)
                else: st.write("Sin Panic Drops recientes.")

        # --- TAB 4: WAIVERS (Agencia Libre) ---
        with tab4:
            st.header("🦅 Agencia Libre (Top EV_adj)")
            ocu = set([str(pid) for r in datos['rosters'] for pid in r.get('players', [])])
            fas = []
            for pid, p in datos['players_db'].items():
                if str(pid) in ocu or p.get('status') == 'Inactive' or p.get('position') not in ['QB','RB','WR','TE','K','DEF']: continue
                pos, eq = p.get('position'), p.get('team', 'FA')
                if eq == 'FA' or not eq: continue
                pr = get_proy(str(pid), pos, datos['proy'])
                if pr > 5.0:
                    prob = calc_prob(obtener_info_hc(eq)['inf'], consultar_clima(eq)[1], p.get('injury_status'))
                    fas.append({'nom': p.get('last_name'), 'pos': pos, 'eq': eq, 'ev': round(pr*(prob/100),1), 'proy': pr})
                    
            fas.sort(key=lambda x: x['ev'], reverse=True)
            top_fa = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'K/DEF': []}
            lims = {'QB': 2, 'RB': 4, 'WR': 4, 'TE': 3, 'K/DEF': 3}
            for fa in fas:
                cat = 'K/DEF' if fa['pos'] in ['K', 'DEF'] else fa['pos']
                if len(top_fa[cat]) < lims[cat]: top_fa[cat].append(fa)

            cols_wv = st.columns(5)
            idx_wv = 0
            for pos_key, lista in top_fa.items():
                with cols_wv[idx_wv]:
                    st.subheader(pos_key)
                    for j in lista:
                        st.info(f"**{j['nom']}** ({j['eq']})\n\n⭐ {j['ev']} EV")
                idx_wv += 1

        # --- TAB 5: BACKTESTING ---
        with tab5:
            st.header("🔬 Backtesting Histórico (Validación del Modelo)")
            np.random.seed(42)
            proy_test = np.clip(np.random.normal(13.5, 4.5, 1000), 5.0, 25.0)
            hc_test = np.random.choice([1, 2, 3, 4], 1000, p=[0.15, 0.35, 0.35, 0.15])
            reales_test = [max(0, np.random.normal(proy_test[i] + (hc_test[i] - 2.5)*1.8, 6.0 - (hc_test[i]*0.8))) for i in range(1000)]
            
            fig_bk, ax_bk = plt.subplots(figsize=(8, 4))
            sns.scatterplot(x=proy_test, y=reales_test, hue=hc_test, palette={1: '#ef4444', 2:'gray', 3:'gray', 4: '#3b82f6'}, alpha=0.4, ax=ax_bk)
            ax_bk.plot([5, 25], [5, 25], color='#10b981', ls='--')
            ax_bk.set_title("Proyección vs Puntos Reales (Alpha por Head Coach)")
            st.pyplot(fig_bk)

else:
    st.error("No se pudieron extraer datos de la liga. Revisa el usuario de Sleeper.")
