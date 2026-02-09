import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
import time
import random
import plotly.graph_objects as go
import plotly.express as px
import os
from scipy.optimize import newton
import hashlib

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA E STILI CSS
# ==============================================================================

st.set_page_config(
    page_title="Bond Research Terminal", 
    page_icon="🏛️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* --- STILI GENERALI --- */
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 8px; border: 1px solid #3e445b; margin-bottom: 10px; color: #ffffff !important; }
    
    /* --- SCONTRINO SIMULATORE --- */
    .receipt-box {
        border: 2px dashed rgba(128, 128, 128, 0.3);
        padding: 20px;
        border-radius: 10px;
        background-color: rgba(128, 128, 128, 0.05);
        margin-top: 10px;
    }
    .receipt-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 15px; }
    .receipt-total { display: flex; justify-content: space-between; margin-top: 15px; border-top: 2px solid #00CC96; padding-top: 10px; font-weight: bold; font-size: 18px; color: #00CC96; }
    .receipt-sub { font-size: 12px; color: gray; text-align: right; margin-top: -5px; }

    /* --- ALTRI STILI --- */
    .explanation-box { background-color: rgba(128, 128, 128, 0.1); border-left: 4px solid #00CC96; padding: 15px; border-radius: 5px; margin-bottom: 15px; }
    .explanation-title { font-weight: bold; color: #00CC96; font-size: 16px; margin-bottom: 5px; }
    .explanation-text { font-size: 14px; color: inherit; opacity: 0.9; }
    [data-testid="stSidebar"] div.stButton > button { background-color: transparent; border: none; text-align: left; color: inherit !important; font-weight: 600; }
    [data-testid="stSidebar"] div.stButton > button:hover { padding-left: 10px; background-color: rgba(128, 128, 128, 0.1); border-radius: 5px; }
    .legend-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; color: white; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .gov { background-color: #1a4a2e; border: 1px solid #28a745; }
    .bank { background-color: #2c3e50; border: 1px solid #8e9aaf; }
    .corp { background-color: #1e3a5f; border: 1px solid #17a2b8; }
    .spec { background-color: #581845; border: 1px solid #d63384; }
    .score-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(128,128,128,0.2); }
    .score-good { color: #00CC96; font-weight: bold; }
    .score-bad { color: #FF4B4B; font-weight: bold; }
    .score-neutral { color: #FFAA00; font-weight: bold; }
    .user-box { padding: 10px; background-color: rgba(0, 204, 150, 0.1); border-left: 5px solid #00CC96; border-radius: 5px; margin-bottom: 20px; font-weight: bold; color: inherit; }
    .red-flag { border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .green-flag { border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .warning-flag { border-left: 5px solid #ffa500; background-color: #2d2a1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIGURAZIONE UTENTI & PERSISTENZA
# ==============================================================================

UTENTI_IN_CHIARO = {
    "giulio": "Giulio99mac!",
    "guest": "mifumoleboix"
}

UTENTI_ABILITATI = {
    user: hashlib.sha256(pwd.encode()).hexdigest() 
    for user, pwd in UTENTI_IN_CHIARO.items()
}

DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

def init_session_state():
    query_params = st.query_params
    session_token = query_params.get("session", None)
    
    if 'portfolio' not in st.session_state: st.session_state.portfolio = []
    if 'confronto' not in st.session_state: st.session_state.confronto = None
    if 'logged_in' not in st.session_state: 
        found_user = None
        if session_token:
            for user, pwd_hash in UTENTI_ABILITATI.items():
                if hashlib.sha256((user + "salt").encode()).hexdigest() == session_token:
                    found_user = user; break
        if found_user:
            st.session_state.logged_in = True
            st.session_state.current_user = found_user
        else:
            st.session_state.logged_in = False
            st.session_state.current_user = ""

    if 'connection_status' not in st.session_state: st.session_state.connection_status = "In attesa..."
    if 'page' not in st.session_state: st.session_state.page = "Scanner"
    if 'last_scrape_time' not in st.session_state: st.session_state.last_scrape_time = None
    if 'patrimonio' not in st.session_state: st.session_state.patrimonio = 50000.0
    if 'selected_isin_from_chart' not in st.session_state: st.session_state.selected_isin_from_chart = None

init_session_state()

# ==============================================================================
# 3. MAPPA FONTI
# ==============================================================================

SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# ==============================================================================
# 4. FUNZIONI UTILI & DATABASE
# ==============================================================================

def valida_isin(isin):
    if not isin or len(isin) != 12: return False
    return isin[:2].isalpha() and isin[2:].isalnum()

def get_last_update_time():
    try:
        if not os.path.exists(DB_FOLDER): return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: return None
        latest_file = max(files, key=os.path.getmtime)
        return datetime.fromtimestamp(os.path.getmtime(latest_file))
    except: return None

def check_connection_status():
    try:
        requests.get("https://www.google.com", timeout=3)
        return "🟢 ONLINE"
    except: return "🔴 OFFLINE"

def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

def get_inflazione_ufficiale():
    inflazione_corrente = 2.0 
    fonte_url = "https://www.istat.it/it/archivio/prezzi+al+consumo"
    return inflazione_corrente, fonte_url

def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        c_isin = next((c for c in cols if 'isin' in str(c).lower()), None)
        
        if not all([c_pr, c_sc, c_de]): return None
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        if pr <= 0: return None
        
        sc_str = str(row[c_sc]).strip()
        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: 
            try: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
            except: return None
        if sc <= date.today(): return None
        
        desc = str(row[c_de])
        ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]): taglio = pulisci_taglio(row[c_min])
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating, "isin": isin_val}
    except: return None

def identikit_bond(dati):
    desc = dati['desc'].upper()
    fonte = dati['fonte'].upper()
    risk_msg = ""; chi = ""; tipo = ""

    if "ITALIA" in fonte or "BTP" in desc or "BOT" in desc:
        chi = "🇮🇹 Stato Italiano"
        tipo = "Titolo di Stato (BTP/BOT)"
        risk_msg = "Rischio Paese: Solido ma soggetto a volatilità politica e Spread."
    elif "GERMANIA" in fonte or "BUND" in desc:
        chi = "🇩🇪 Stato Tedesco"
        tipo = "Titolo di Stato (Bund)"
        risk_msg = "Bene Rifugio: Rischio quasi nullo, rendimenti generalmente bassi."
    elif "USA" in fonte or "TREASURY" in desc:
        chi = "🇺🇸 Stati Uniti"
        tipo = "Treasury Bond"
        risk_msg = "Valuta Estera: Attenzione al rischio cambio Euro/Dollaro!"
    elif "BANCHE" in fonte or "INTESA" in desc or "UNICREDIT" in desc:
        chi = "🏦 Settore Bancario"
        tipo = "Obbligazione Bancaria"
        risk_msg = "Rischio Settoriale: Legato alla solidità della banca. Se 'SUB', rischio alto."
    elif "CORP" in fonte or "ENI" in desc or "ENEL" in desc or "STELLANTIS" in desc:
        chi = "🏭 Azienda (Corporate)"
        tipo = "Obbligazione Societaria"
        risk_msg = "Rischio Aziendale: Dipende dai bilanci e dalla salute dell'azienda."
    else:
        chi = "🌍 Emittente Internazionale"
        tipo = "Obbligazione"
        risk_msg = "Verificare il rating specifico dell'emittente."

    diff = (dati['sc'] - date.today())
    anni = diff.days // 365
    mesi = (diff.days % 365) // 30
    tempo = f"{anni} Anni e {mesi} Mesi"
    return chi, tipo, tempo, risk_msg

# ==============================================================================
# 5. RISK ENGINE E SCORECARD
# ==============================================================================

def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    if prezzo <= 0 or freq == 0: return None
    cedola_annua = cedola_pct / 100
    giorni = (scadenza - date.today()).days
    anni = giorni / 365.25
    if anni <= 0: return None
    n_periodi = max(1, int(anni * freq))
    c = (cedola_annua * face_value) / freq
    ytm_guess = (cedola_annua + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
    def price_func(y):
        if y <= -1: return float('inf')
        pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n_periodi + 1)])
        pv += face_value / ((1 + y/freq) ** n_periodi)
        return pv - prezzo
    try:
        ytm = newton(price_func, ytm_guess, maxiter=50)
        return max(0, ytm)
    except: return ytm_guess

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    if prezzo <= 0: return None
    ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq)
    if ytm is None: return None
    cedola = cedola_pct / 100
    anni = (scadenza - date.today()).days / 365.25
    mod_dur = anni / (1 + ytm)
    return {"ytm": ytm * 100, "mod_dur": mod_dur}

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def analizza_bond_quality_dettagliata(dati, risk, tax, patrimonio):
    breakdown = []
    score = 100
    peso_bond = (dati['taglio'] / patrimonio) * 100
    if peso_bond > 20: punti = -30; msg = f"Rischio alto: pesa il {peso_bond:.1f}%"; colore = "score-bad"
    elif peso_bond > 10: punti = -10; msg = f"Taglio impegnativo: pesa il {peso_bond:.1f}%"; colore = "score-neutral"
    else: punti = 0; msg = f"Taglio sostenibile: pesa il {peso_bond:.1f}%"; colore = "score-good"
    score += punti
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{dati['taglio']/1000:.0f}k €", "msg": msg, "pts": punti, "col": colore})

    if dati['pr'] > 110: puntos = -15; msg="Molto sopra la pari"; col="score-bad"
    elif dati['pr'] > 102: puntos = -5; msg="Sopra la pari"; col="score-neutral"
    elif dati['pr'] < 95: puntos = +5; msg="Sotto la pari"; col="score-good"
    else: puntos=0; msg="Prezzo Fair"; col="score-good"
    score += puntos
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{dati['pr']:.2f}", "msg": msg, "pts": puntos, "col": col})

    ytm_net = risk['ytm'] * (1 - tax / 100) if risk else 0
    if ytm_net < 1.5: puntos=-20; msg="Rendimento basso"; col="score-bad"
    elif ytm_net > 3.0: puntos=+15; msg="Ottimo rendimento"; col="score-good"
    else: puntos=0; msg="Rendimento medio"; col="score-neutral"
    score += puntos
    breakdown.append({"cat": "📈 Rendimento", "val": f"{ytm_net:.2f}%", "msg": msg, "pts": puntos, "col": col})

    if tax < 20: puntos=+5; msg="Tassazione agevolata"; col="score-good"
    else: puntos=-5; msg="Tassazione piena"; col="score-neutral"
    score += puntos
    breakdown.append({"cat": "🏛️ Tassazione", "val": f"{tax}%", "msg": msg, "pts": puntos, "col": col})

    flags = []
    if score < 50: flags.append(("red", "Score Basso"))
    return {"score": max(0, min(100, score)), "breakdown": breakdown, "ytm_netto": ytm_net, "flags": flags}

# ==============================================================================
# 6. LOGICHE SMART & DB
# ==============================================================================

def calcola_rendimento_grezzo(prezzo, cedola, scadenza):
    try:
        anni = (scadenza - date.today()).days / 365.25
        if anni <= 0 or prezzo <= 0: return 0
        gain_annuo = (100 - prezzo) / anni
        rendimento = (cedola + gain_annuo) / prezzo * 100
        return round(rendimento, 2)
    except: return 0

@st.cache_data(ttl=3600)
def carica_dati_mercato():
    all_bonds = []
    if not os.path.exists(DB_FOLDER): return pd.DataFrame()
    for filename in os.listdir(DB_FOLDER):
        if filename.endswith(".csv"):
            try:
                path = os.path.join(DB_FOLDER, filename)
                df = pd.read_csv(path)
                cols = df.columns
                c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
                c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
                c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
                c_isin = next((c for c in cols if 'isin' in str(c).lower()), None)
                if all([c_pr, c_sc, c_de, c_isin]):
                    df = df.dropna(subset=[c_pr, c_sc])
                    for _, row in df.iterrows():
                        try:
                            sc_str = str(row[c_sc]).strip()
                            try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
                            except: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
                            if sc <= date.today(): continue
                            pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
                            desc = str(row[c_de])
                            ced = 0.0
                            m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
                            if m: ced = float(m.group(1).replace(',', '.'))
                            isin_v = str(row[c_isin]).strip()
                            all_bonds.append({
                                "ISIN": isin_v, "Desc": desc, "Prezzo": pr, "Scadenza": sc, "Cedola": ced,
                                "YTM_Grezzo": calcola_rendimento_grezzo(pr, ced, sc),
                                "Anni": (sc - date.today()).days / 365.25, "Fonte": filename.replace('.csv', '')
                            })
                        except: continue
            except: continue
    return pd.DataFrame(all_bonds)

def categorizza_rischio(isin, nome, desc):
    nome = nome.upper(); desc = desc.upper(); isin = isin.upper()
    gov_safe = ["GERMANIA", "BUND", "FRANCIA", "OAT", "USA", "TREASURY", "BEI", "EU", "EUROPA"]
    if any(k in nome or k in desc for k in gov_safe): return 1
    gov_mid = ["ITALIA", "BTP", "BOT", "CCT", "SPAGNA", "BONOS"]
    if any(k in nome or k in desc for k in gov_mid): return 2
    if "INTESA" in nome or "UNICREDIT" in nome: return 2
    if isin.startswith("XS"): return 3
    if "SUBORDINAT" in nome or "SUB" in desc: return 4
    if "ROMANIA" in nome or "TURCHIA" in nome: return 4
    return 3 

def trova_alternative_migliori(bond_target, df_mercato):
    if df_mercato.empty: return pd.DataFrame()
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    isin_target = bond_target.get('isin', '')
    rischio_target = categorizza_rischio(isin_target, bond_target['fonte'], bond_target['desc'])
    
    alternative = []
    for _, row in df_mercato.iterrows():
        if not (anni_target - 2 <= row['Anni'] <= anni_target + 2): continue
        if row['Prezzo'] > 108: continue 
        rischio_alt = categorizza_rischio(row['ISIN'], row['Fonte'], row['Desc'])
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        extra = ytm_netto_alt - ytm_netto_target
        tipo_switch = ""
        if rischio_alt == rischio_target and extra > 0.15: tipo_switch = "✅ Gemello Migliore"
        elif rischio_alt == rischio_target + 1 and extra > 0.8: tipo_switch = "⚠️ Boost Rendimento (Rischio+)"
        elif rischio_alt < rischio_target and extra > -0.3: tipo_switch = "🛡️ Rifugio Sicuro"
        if tipo_switch:
            link_isin = f"https://www.google.com/search?q={row['ISIN']}+bond"
            row['Tipologia'] = tipo_switch; row['YTM_Netto'] = ytm_netto_alt; row['Extra'] = extra; row['Link'] = link_isin
            alternative.append(row)
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty: return df_alt.sort_values('Extra', ascending=False).head(5)
    return pd.DataFrame()

def aggiorna_db():
    p = st.progress(0); s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values()); c = 0; ok = 0
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1; s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            p.progress(c/tot)
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
            except: pass
    st.session_state.last_scrape_time = datetime.now()
    s.empty(); p.empty(); st.toast(f"Aggiornati {ok} files"); st.rerun()

def cerca_db(isin, cat):
    if not valida_isin(isin): return None, None
    search_cats = [cat] if cat else list(SOURCES_MAP.keys())
    for c in search_cats:
        for src in SOURCES_MAP.get(c, []):
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): continue
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any(): return df[mask].iloc[0], {"nome": src['nome'], "freq": src['freq'], "cat_reale": c}
            except: continue
    return None, None

def calcola_rateo(dati):
    """Calcola il rateo maturato in percentuale"""
    try:
        today_dt = date.today()
        if dati['freq'] == 0: return 0.0
        giorni_cedola = 365 / dati['freq']
        data_ced = dati['sc']
        # Trova la data di inizio godimento della cedola corrente
        while data_ced > today_dt:
            data_ced -= timedelta(days=int(giorni_cedola))
        
        # data_ced è ora la data di stacco precedente
        giorni_trascorsi = (today_dt - data_ced).days
        
        # Correzione se siamo esattamente sul giorno cedola o calcoli strani
        if giorni_trascorsi < 0: giorni_trascorsi = 0
        
        rateo = (dati['ced'] / dati['freq']) * (giorni_trascorsi / giorni_cedola)
        return max(0.0, rateo)
    except: return 0.0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []
    # 1. Costi
    rateo_pct = calcola_rateo(dati)
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_lordo = (nominale * rateo_pct) / 100
    # Nota: il rateo si paga al netto se l'intermediario è sostituto, ma per semplicità retail qui mostriamo l'impatto fiscale corretto dopo
    # Standard italiano: si paga rateo netto (rateo lordo * (1 - tax))
    costo_rateo_netto = costo_rateo_lordo * (1 - tax_rate/100)
    
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    flussi.append({"Data": date.today(), "Tipo": "USCITA", "Importo": -spesa_totale, "Dettagli": "Acquisto + Rateo + Comm."})
    
    # 2. Cedole
    totale_incassato = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = dati['sc']
        date_cedole = []
        temp = curr
        while temp > date.today():
            date_cedole.append(temp)
            temp -= timedelta(days=int(365 / dati['freq']))
        date_cedole.sort()
        for d in date_cedole:
            if d != dati['sc']:
                flussi.append({"Data": d, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola Netta"})
                totale_incassato += cedola_netta
                
    # 3. Rimborso
    # Tassazione sul Capital Gain (Prezzo Rimborso 100 - Prezzo Acquisto)
    # Se Prezzo Acquisto > 100, genera Minusvalenza (credito fiscale), qui non lo contiamo come cash flow positivo per prudenza
    # Se Prezzo Acquisto < 100, si paga il 12.5% sulla differenza
    gain = max(0, 100 - prezzo_acquisto) 
    tassa_gain = (gain / 100 * nominale) * (tax_rate/100)
    
    rimborso_netto = nominale - tassa_gain
    
    ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    flussi.append({"Data": dati['sc'], "Tipo": "ENTRATA", "Importo": rimborso_netto + ultima_ced, "Dettagli": "Rimborso + Ultima Cedola"})
    totale_incassato += (rimborso_netto + ultima_ced)
    
    return pd.DataFrame(flussi), spesa_totale, totale_incassato, costo_rateo_netto

# ==============================================================================
# 7. INTERFACCIA UTENTE
# ==============================================================================

def login():
    st.title("🔒 Login Terminale")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("---")
        u = st.text_input("Utente", placeholder="es. giulio").strip()
        p = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                token = hashlib.sha256((u + "salt").encode()).hexdigest()
                st.query_params["session"] = token
                st.rerun()
            else: st.error("Errore Credenziali")

def main_app():
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        if st.session_state.current_user:
            st.markdown(f"""<div class="user-box">👤 {st.session_state.current_user.capitalize()}</div>""", unsafe_allow_html=True)
        
        if st.button("🔎 Scanner", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True): st.session_state.page = "SmartAnalysis"; st.rerun()
        if st.button("⚔️ Confronto", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider()
        st.write("💰 **Il tuo Patrimonio**")
        st.session_state.patrimonio = st.number_input("Totale investibile (€)", min_value=10000.0, value=st.session_state.patrimonio, step=5000.0)
        
        st.divider(); st.subheader("⚙️ SISTEMA")
        last = get_last_update_time()
        if last: 
            delta = (datetime.now() - last).total_seconds() / 3600
            color = "green" if delta < 24 else "orange"
            st.markdown(f"📅 Aggiornato: :{color}[{last.strftime('%d/%m %H:%M')}]")
        else: st.error("❌ Nessun Dato")
        
        c1, c2 = st.columns([1, 2])
        if c1.button("📶"): st.session_state.connection_status = check_connection_status()
        c2.markdown(f"**{st.session_state.connection_status}**")
        
        if st.button("🔄 Aggiorna Database", use_container_width=True):
            if "BANNATO" in st.session_state.connection_status: st.error("Sei bannato! Aspetta.")
            else: aggiorna_db()
            
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_sources = sum(len(v) for v in SOURCES_MAP.values())
        st.caption(f"Files: {len(csv_files)}/{tot_sources}")
        
        if st.session_state.current_user in ["giulio", "guest"]:
             if st.button("🗑️ Reset Database", use_container_width=True):
                try:
                    for f in os.listdir(DB_FOLDER): os.remove(os.path.join(DB_FOLDER, f))
                    st.toast("Pulito!", icon="🧹"); time.sleep(1); st.rerun()
                except: pass
        st.divider(); 
        if st.button("🚪 Logout"): 
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Inserisci un ISIN per analizzare il bond.")
        
        l1, l2, l3, l4 = st.columns(4)
        with l1: st.markdown("""<div class="legend-box gov"><span class="legend-title">🏛️ GOVERNATIVI</span><b>Stati</b><br>Italia, Germania, USA, Francia</div>""", unsafe_allow_html=True)
        with l2: st.markdown("""<div class="legend-box bank"><span class="legend-title">🏦 FINANZIARI</span><b>Banche</b><br>Intesa, UniCredit, Subordinate</div>""", unsafe_allow_html=True)
        with l3: st.markdown("""<div class="legend-box corp"><span class="legend-title">🏭 CORPORATE</span><b>Aziende</b><br>Eni, Stellantis, Telecom</div>""", unsafe_allow_html=True)
        with l4: st.markdown("""<div class="legend-box spec"><span class="legend-title">💎 SPECIALI</span><b>Misti</b><br>Zero Coupon, 25y+, Callable</div>""", unsafe_allow_html=True)
        st.divider()
        
        if st.session_state.selected_isin_from_chart:
            isin_default = st.session_state.selected_isin_from_chart
            st.session_state.selected_isin_from_chart = None
        else:
            isin_default = ""

        col_cat, col_isin, col_btn = st.columns([2, 2, 1])
        with col_cat: cat = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
        with col_isin: isin = st.text_input("ISIN", value=isin_default, placeholder="IT...").strip().upper()
        with col_btn: 
            st.write("") 
            st.write("") 
            trigger_search = st.button("🔎 Cerca", use_container_width=True)
        
        if isin and (trigger_search or isin):
            if not valida_isin(isin): st.error("❌ ISIN non valido")
            else:
                row, info = cerca_db(isin, cat if not isin_default else None)
                d = processa_riga(row, info) if row is not None else None
                
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality_dettagliata(d, risk, tax, st.session_state.patrimonio)
                    
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 20px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <h3 style="color:white; margin:0;">{chi}</h3>
                                <div style="color:#b0b3c5; font-size:16px;">{tipo}</div>
                                <div style="color:#00CC96; font-size:12px; margin-top:5px;">ℹ️ {risk_msg}</div>
                            </div>
                            <div style="text-align:right;">
                                <h2 style="color:#00CC96; margin:0;">{d['ced']}%</h2>
                                <div style="color:#b0b3c5; font-size:12px;">Cedola Lorda</div>
                            </div>
                        </div>
                        <hr style="border-color:#3e445b; margin:15px 0;">
                        <div style="display:flex; justify-content:space-between; color:#e0e0e0;">
                            <div>📅 Scadenza: <b>{d['sc'].strftime('%d/%m/%Y')}</b></div>
                            <div>⏳ Mancano: <b>{tempo}</b></div>
                            <div>🧾 Prezzo: <b>{d['pr']}€</b></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.subheader("💡 Analisi in Breve")
                    t1, t2, t3 = st.columns(3)
                    
                    with t1:
                        st.markdown('<div class="explanation-box">', unsafe_allow_html=True)
                        st.markdown('<div class="explanation-title">1. Quanto Rende?</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="explanation-text">Il rendimento annuo netto è del <b>{qual["ytm_netto"]:.2f}%</b>. Questo numero include sia le cedole che ricevi sia il guadagno finale (se compri a sconto) o la perdita (se compri a premio).</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    with t2:
                        st.markdown('<div class="explanation-box">', unsafe_allow_html=True)
                        st.markdown('<div class="explanation-title">2. Soldi in Tasca</div>', unsafe_allow_html=True)
                        cedola_netta_euro = (1000 * (d['ced']/100) * (1 - tax/100))
                        st.markdown(f'<div class="explanation-text">Ogni 1.000€ investiti, riceverai circa <b>{cedola_netta_euro:.2f}€ netti</b> all\'anno sul conto corrente.</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    with t3:
                        st.markdown('<div class="explanation-box">', unsafe_allow_html=True)
                        st.markdown('<div class="explanation-title">3. Rischio Prezzo</div>', unsafe_allow_html=True)
                        volatilita = "BASSA" if risk['mod_dur'] < 3 else "MEDIA" if risk['mod_dur'] < 7 else "ALTA"
                        st.markdown(f'<div class="explanation-text">Volatilità: <b>{volatilita}</b>. Se i tassi BCE salgono, il prezzo di questo bond potrebbe scendere. Più alta è la duration ({risk["mod_dur"]:.1f} anni), più oscilla il prezzo.</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # --- SIMULATORE DI INVESTIMENTO AVANZATO ---
                    st.divider()
                    st.subheader("💰 Simulatore d'Acquisto")
                    
                    c_sim1, c_sim2 = st.columns([1, 2])
                    with c_sim1:
                        investimento = st.number_input("Quanto vuoi investire? (€)", value=10000, step=1000)
                        commissioni = st.number_input("Commissioni Banca (€)", value=5.0, step=1.0, help="Non lo sai? Se hai una banca online (Fineco, Directa) metti 5-10€. Se hai una banca fisica, spesso è lo 0.19% del capitale (es. 19€ su 10k).")
                    
                    df_flussi, spesa_tot, incasso_tot, costo_rateo = genera_flussi_dettagliati(d, investimento, tax, commissioni, d['pr'])
                    guadagno_netto = incasso_tot - spesa_tot
                    anni_durata = (d['sc'] - date.today()).days / 365.25
                    rend_annuo_semplice = (guadagno_netto / spesa_tot / anni_durata) * 100 if anni_durata > 0 else 0
                    
                    with c_sim2:
                        st.markdown(f"""
                        <div class="receipt-box">
                            <div class="receipt-row"><span>Costo Titoli (Prezzo {d['pr']}):</span> <span>{investimento * d['pr'] / 100:.2f} €</span></div>
                            <div class="receipt-row"><span>+ Rateo Interessi (da anticipare):</span> <span>{costo_rateo:.2f} €</span></div>
                            <div class="receipt-row"><span>+ Commissioni Banca:</span> <span>{commissioni:.2f} €</span></div>
                            <div class="receipt-total">
                                <span>TOTALE DA PAGARE OGGI:</span>
                                <span>{spesa_tot:.2f} €</span>
                            </div>
                            <div class="receipt-sub">Hai pagato circa {(spesa_tot/investimento)*100:.1f}% del valore nominale</div>
                            <hr>
                            <div class="receipt-row" style="color:#00CC96; font-weight:bold;">
                                <span>GUADAGNO TOTALE (in {anni_durata:.1f} anni):</span>
                                <span>+{guadagno_netto:.2f} €</span>
                            </div>
                            <div class="receipt-row">
                                <span>Rendimento Annuo Effettivo:</span>
                                <span>{rend_annuo_semplice:.2f}%</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.expander("📅 Vedi tutti i pagamenti futuri (Cedolario)"):
                        st.dataframe(df_flussi[['Data', 'Tipo', 'Importo', 'Dettagli']].style.format({'Importo': '{:+.2f}€'}), use_container_width=True)

                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("📌 Salva per Confronto", use_container_width=True):
                        st.session_state.confronto = d; st.success("Salvato!")
                    if c_btn2.button("💼 Aggiungi a Portafoglio", use_container_width=True):
                        st.session_state.portfolio.append(d)
                        st.success("Aggiunto!")

                else: st.warning("Bond non trovato. Aggiorna il DB.")

    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Fair Value")
        st.caption("Confronto intelligente con il mercato.")
        with st.spinner("Caricamento mercato..."):
            df_market = carica_dati_mercato()
        
        if df_market.empty: st.warning("⚠️ Database vuoto.")
        else:
            col_search, col_kpi = st.columns([1, 3])
            with col_search:
                isin_smart = st.text_input("Analizza ISIN", placeholder="IT...").strip().upper()
                cat_smart = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
                
            if isin_smart and valida_isin(isin_smart):
                row, info = cerca_db(isin_smart, cat_smart)
                d_smart = processa_riga(row, info) if row is not None else None
                
                if d_smart:
                    d_smart['isin'] = isin_smart
                    ytm_s = calcola_rendimento_grezzo(d_smart['pr'], d_smart['ced'], d_smart['sc'])
                    dur_s = (d_smart['sc'] - date.today()).days / 365.25
                    
                    st.divider()
                    st.subheader("📊 Dove si trova il tuo Bond?")
                    
                    range_zoom = 3
                    df_zoom = df_market[
                        (df_market['Anni'] >= dur_s - range_zoom) & 
                        (df_market['Anni'] <= dur_s + range_zoom) &
                        (df_market['YTM_Grezzo'] < ytm_s + 5)
                    ]
                    
                    st.markdown(f"Visualizzo solo bond con scadenza **+/- {range_zoom} anni** dal tuo. Clicca su un punto blu per analizzarlo.")
                    
                    fig = px.scatter(
                        df_zoom, x='Anni', y='YTM_Grezzo', 
                        hover_data=['ISIN', 'Desc', 'Prezzo'],
                        color_discrete_sequence=['#1f77b4'],
                        labels={'Anni': 'Durata (Anni)', 'YTM_Grezzo': 'Rendimento Lordo (%)'}
                    )
                    
                    fig.add_trace(go.Scatter(x=[dur_s], y=[ytm_s], mode='markers+text', name='TUO BOND', text=['📍 TU'], textposition="top center", marker=dict(color='red', size=15, symbol='star')))
                    fig.update_layout(template="plotly_dark", height=450)
                    
                    selected_point = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
                    if selected_point and len(selected_point['selection']['points']) > 0:
                        try:
                            if 'customdata' in selected_point['selection']['points'][0]:
                                clicked_isin = selected_point['selection']['points'][0]['customdata'][0]
                                st.session_state.selected_isin_from_chart = clicked_isin
                                st.session_state.page = "Scanner"
                                st.rerun()
                        except: pass

                    st.divider()
                    st.subheader("🔄 Alternative Migliori (Smart Switch)")
                    st.caption("Confronto intelligente basato su Rischio e Rendimento Netto.")
                    
                    alternative = trova_alternative_migliori(d_smart, df_market)
                    
                    if not alternative.empty:
                        st.dataframe(
                            alternative[['Tipologia', 'ISIN', 'Desc', 'Prezzo', 'YTM_Netto', 'Extra', 'Link']],
                            column_config={
                                "Link": st.column_config.LinkColumn("Scheda", display_text="🔗 Apri"),
                                "YTM_Netto": st.column_config.NumberColumn("YTM Netto", format="%.2f%%"),
                                "Extra": st.column_config.NumberColumn("Delta", format="%+.2f%%"),
                                "Prezzo": st.column_config.NumberColumn("Prezzo", format="%.2f€")
                            },
                            use_container_width=True,
                            hide_index=True
                        )
                    else: st.success("🏆 Il tuo bond è già una delle migliori opzioni per questa scadenza e rischio.")
                else: st.error("ISIN non trovato.")
            else: st.info("Inserisci un ISIN per iniziare.")

    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto")
        if st.session_state.confronto:
            a = st.session_state.confronto
            st.info(f"📌 A: {a['desc']}")
            c1, c2 = st.columns(2)
            cb = c1.selectbox("Cat B", list(SOURCES_MAP.keys()))
            ib = c2.text_input("ISIN B").strip().upper()
            if st.button("VS") and ib:
                rb, info = cerca_db(ib, cb)
                b = processa_riga(rb, info) if rb is not None else None
                if b:
                    diff_anni = abs(((a['sc'] - date.today()).days/365.25) - ((b['sc'] - date.today()).days/365.25))
                    tax_a = determina_tasse(a['fonte'], a['desc'])
                    tax_b = determina_tasse(b['fonte'], b['desc'])
                    
                    if diff_anni > 5: st.warning(f"⚠️ Attenzione: Confronti bond con scadenza molto diversa ({diff_anni:.1f} anni diff).")
                    if tax_a != tax_b: st.info("ℹ️ Nota: Tassazioni diverse. Guarda il YTM Netto.")
                    
                    ra = calcola_metriche_rischio(a['pr'], a['ced'], a['sc'], a['freq'])
                    rb = calcola_metriche_rischio(b['pr'], b['ced'], b['sc'], b['freq'])
                    k1, k2, k3 = st.columns(3)
                    # Usa patrimonio utente
                    k1.metric("A YTM Net", f"{analizza_bond_quality_dettagliata(a, ra, tax_a, st.session_state.patrimonio)['ytm_netto']:.2f}%")
                    k2.markdown("<h2>VS</h2>", unsafe_allow_html=True)
                    k3.metric("B YTM Net", f"{analizza_bond_quality_dettagliata(b, rb, tax_b, st.session_state.patrimonio)['ytm_netto']:.2f}%")
                else: st.error("B non trovato")
        else: st.warning("Salva un bond prima.")

    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            st.dataframe(df)
            if st.button("Reset"): st.session_state.portfolio = []
        else: st.info("Portafoglio vuoto.")

if st.session_state.logged_in: main_app()
else: login()
