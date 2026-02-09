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
import json
from typing import Dict, List, Optional
import plotly.figure_factory as ff

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
    
    /* --- LEGEND CARD --- */
    .cat-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: white; 
    }
    .cat-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; }
    .cat-desc { font-size: 14px; opacity: 0.95; margin-bottom: 8px; line-height: 1.4; }
    .cat-meta { font-size: 12px; font-weight: bold; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
    
    .bg-gov { background: linear-gradient(135deg, #1a4a2e 0%, #28a745 100%); }
    .bg-bank { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); }
    .bg-corp { background: linear-gradient(135deg, #1e3a5f 0%, #17a2b8 100%); }
    .bg-spec { background: linear-gradient(135deg, #581845 0%, #d63384 100%); }

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
    
    .score-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(128,128,128,0.2); }
    .score-good { color: #00CC96; font-weight: bold; }
    .score-bad { color: #FF4B4B; font-weight: bold; }
    .score-neutral { color: #FFAA00; font-weight: bold; }
    
    .user-box { padding: 10px; background-color: rgba(0, 204, 150, 0.1); border-left: 5px solid #00CC96; border-radius: 5px; margin-bottom: 20px; font-weight: bold; color: inherit; }
    
    [data-testid="stSidebar"] div.stButton > button { background-color: transparent; border: none; text-align: left; color: inherit !important; font-weight: 600; }
    [data-testid="stSidebar"] div.stButton > button:hover { padding-left: 10px; background-color: rgba(128, 128, 128, 0.1); border-radius: 5px; }
    
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
    if 'alerts' not in st.session_state: st.session_state.alerts = []
    
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
# 3. MAPPA FONTI (ESTESA - 29 DATASETS) & MAPPING CATEGORIE UI
# ==============================================================================

SOURCES_MAP = {
    "🏛️ GOV - ITALIA": [
        {"nome": "BTP_FISSI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BTP_ITALIA_INF", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=btpitalia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CCT_VARIABILI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cct&yieldtype=G&timescale=DUR", "freq": 2}
    ],
    "🇪🇺 GOV - EUROPA CORE": [
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUSTRIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=austria&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BELGIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=belgio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OLANDA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=olanda&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏖️ GOV - EUROPA PERIFERIA": [
        {"nome": "SPAGNA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=spagna&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "PORTOGALLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=portogallo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 GOV - MONDO & EMERGENTI": [
        {"nome": "USA_TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TURCHIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=turchia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BRASILE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=brasile&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNGHERIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=ungheria&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇪🇺 SOVRANAZIONALI (SUPRA)": [
        {"nome": "EU_BEI_ESM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovranazionali&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbonds&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI & BANCHE": [
        {"nome": "BANCHE_SENIOR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE_TIER2", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ASSICURATIVI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=assicurazioni&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE (AZIENDE)": [
        {"nome": "CORP_IG_EUROPE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "HIGH_YIELD_EUR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=highyield&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# Mapping per l'interfaccia utente semplificata
MACRO_CATEGORIES = {
    "🌐 TUTTE": [],
    "🏛️ GOVERNATIVI": ["🏛️ GOV - ITALIA", "🇪🇺 GOV - EUROPA CORE", "🏖️ GOV - EUROPA PERIFERIA", "🌍 GOV - MONDO & EMERGENTI", "🇪🇺 SOVRANAZIONALI (SUPRA)"],
    "🏦 BANCARI": ["🏦 FINANZIARI & BANCHE"],
    "🏭 CORPORATE": ["🏭 CORPORATE (AZIENDE)"],
    "💎 SPECIALI": ["💎 SPECIALI"]
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
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU", "ROMANIA", "UNGHERIA", "TURCHIA"]
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
                            
                            # Assegna categoria per colore
                            cat = "Altro"
                            if any(x in desc.upper() for x in ["BTP", "BOT", "BUND", "TREASURY", "OAT", "SPAGNA", "PORTOGALLO"]): cat = "Governativo"
                            elif any(x in desc.upper() for x in ["INTESA", "UNICREDIT", "BANCA", "B.", "MEDIOBANCA"]): cat = "Bancario"
                            elif any(x in desc.upper() for x in ["ENI", "ENEL", "STELLANTIS", "FERRARI", "TELECOM"]): cat = "Corporate"
                            
                            all_bonds.append({
                                "ISIN": isin_v, "Desc": desc, "Prezzo": pr, "Scadenza": sc, "Cedola": ced,
                                "YTM_Grezzo": calcola_rendimento_grezzo(pr, ced, sc),
                                "Anni": (sc - date.today()).days / 365.25, "Fonte": filename.replace('.csv', ''),
                                "Categoria": cat
                            })
                        except: continue
            except: continue
    return pd.DataFrame(all_bonds)

def categorizza_rischio(isin, nome, desc):
    # Semplificato per robustezza
    return 3 # Default medio

def trova_alternative_migliori(bond_target, df_mercato, categoria_obbligatoria=None):
    if df_mercato.empty: return pd.DataFrame()
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    
    if not categoria_obbligatoria:
        categoria_obbligatoria = bond_target.get('Categoria', 'Governativo' if tax_target==12.5 else 'Corporate')

    alternative = []
    for _, row in df_mercato.iterrows():
        # Filtro Rigido Categoria
        if categoria_obbligatoria == "Governativo" and row['Categoria'] != "Governativo": continue
        
        if not (anni_target - 2 <= row['Anni'] <= anni_target + 2): continue
        if row['Prezzo'] > 108: continue 
        
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        extra = ytm_netto_alt - ytm_netto_target
        tipo_switch = ""
        
        if extra > 0.15: tipo_switch = "✅ Miglior Rendimento"
        elif extra > 0.05 and row['Prezzo'] < bond_target['pr']: tipo_switch = "📉 Prezzo più basso"
        
        if tipo_switch:
            link_isin = f"https://www.google.com/search?q={row['ISIN']}+bond"
            row['Tipologia'] = tipo_switch; row['YTM_Netto'] = ytm_netto_alt; row['Extra'] = extra; row['Link'] = link_isin
            alternative.append(row)
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty: return df_alt.sort_values('Extra', ascending=False).head(5)
    return pd.DataFrame()

def aggiorna_db():
    # 1. PULIZIA: Cancella tutto il contenuto della cartella prima di scaricare
    if os.path.exists(DB_FOLDER):
        for f in os.listdir(DB_FOLDER):
            file_path = os.path.join(DB_FOLDER, f)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass # Ignora errori di cancellazione
    
    # 2. DOWNLOAD: Scarica i nuovi file con PAUSA ANTI-BAN
    p = st.progress(0)
    s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values())
    c = 0
    ok = 0
    
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1
            
            # --- MODIFICA ANTI-BAN: Pausa casuale tra 1.5 e 3.5 secondi ---
            # Simula il tempo di "lettura" umano tra un click e l'altro
            sleep_time = random.uniform(1.5, 3.5)
            s.text(f"⏳ Attesa prudenziale ({sleep_time:.1f}s) -> Scarico {src['nome']} ({c}/{tot})...")
            time.sleep(sleep_time) 
            # ---------------------------------------------------------------

            p.progress(c/tot)
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}, timeout=15)
                
                # Forza il parsing delle tabelle
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    # Cerca la tabella giusta
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1
                        break
            except Exception as e:
                # Se fallisce, aspetta un po' di più prima di riprovare col prossimo
                time.sleep(2)
                pass
                
    st.session_state.last_scrape_time = datetime.now()
    s.empty()
    p.empty()
    st.toast(f"Database Rigenerato in sicurezza: {ok}/{tot} files.", icon="🛡️")
    time.sleep(1)
    st.rerun()

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): return None, None
    
    # Recupera le sottocategorie dalla mappatura
    # Se cat_macro è "🌐 TUTTE" (o simile), target_subcats sarà [] (lista vuota)
    target_subcats = MACRO_CATEGORIES.get(cat_macro, [])
    
    # Se la lista è vuota (es. TUTTE) o None, cerchiamo in TUTTE le chiavi di SOURCES_MAP
    if not target_subcats:
        search_keys = list(SOURCES_MAP.keys())
    else:
        search_keys = target_subcats

    # Itera sulle chiavi selezionate
    for key in search_keys:
        sources = SOURCES_MAP.get(key, [])
        for src in sources:
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): continue
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any(): 
                        row = df[mask].iloc[0]
                        cat_reale = "Governativo" if "BTP" in str(row) or "BOT" in str(row) else "Corporate"
                        return row, {"nome": src['nome'], "freq": src['freq'], "cat_reale": key}
            except: continue
    return None, None

def calcola_rateo(dati):
    try:
        today_dt = date.today()
        if dati['freq'] == 0: return 0.0
        giorni_cedola = 365 / dati['freq']
        data_ced = dati['sc']
        while data_ced > today_dt:
            data_ced -= timedelta(days=int(giorni_cedola))
        if data_ced > today_dt: data_ced -= timedelta(days=int(giorni_cedola))
        
        giorni_trascorsi = (today_dt - data_ced).days
        rateo = (dati['ced'] / dati['freq']) * (giorni_trascorsi / giorni_cedola)
        return max(0.0, rateo)
    except: return 0.0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []
    # 1. Costi
    rateo_pct = calcola_rateo(dati)
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_lordo = (nominale * rateo_pct) / 100
    costo_rateo_netto = costo_rateo_lordo * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    
    # Flusso iniziale negativo
    flussi.append({"Data": date.today(), "Tipo": "USCITA", "Importo": -spesa_totale, "Dettagli": "Acquisto + Rateo + Comm."})
    
    totale_cedole_nette = 0
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
                totale_cedole_nette += cedola_netta
                
    gain = max(0, 100 - prezzo_acquisto)
    gain_euro = (gain / 100) * nominale
    tassa_gain = gain_euro * (tax_rate/100)
    plusvalenza_netta = gain_euro - tassa_gain
    rimborso_netto = nominale - tassa_gain
    ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    flussi.append({"Data": dati['sc'], "Tipo": "ENTRATA", "Importo": rimborso_netto + ultima_ced, "Dettagli": "Rimborso + Ultima Cedola"})
    
    incasso_totale = totale_cedole_nette + rimborso_netto + ultima_ced
    totale_cedole_nette += ultima_ced

    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza_netta

# -----------------------------------------------------------------------------
# 🆕 FUNZIONALITÀ RETAIL AVANZATE
# -----------------------------------------------------------------------------

# 1. BOND SCREENER INTELLIGENTE
def bond_screener_ui():
    """Interfaccia Bond Screener con filtri avanzati"""
    st.title("🎯 Bond Screener Intelligente")
    st.caption("Trova i bond perfetti per te con filtri combinati")
    
    # Carica mercato
    with st.spinner("Caricamento database..."):
        df_market = carica_dati_mercato()
        if df_market.empty:
            st.error("❌ Database vuoto. Aggiorna dalla sidebar.")
            return
        
    st.divider()
    
    # === FILTRI ===
    st.subheader("🔧 I Tuoi Filtri")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📊 Rendimento**")
        ytm_min = st.number_input("YTM Minimo %", value=0.0, step=0.5)
        ytm_max = st.number_input("YTM Massimo %", value=15.0, step=0.5)
        
    with col2:
        st.markdown("**⏰ Scadenza**")
        anni_min = st.number_input("Scadenza Min (anni)", value=0.0, step=0.5)
        anni_max = st.number_input("Scadenza Max (anni)", value=30.0, step=1.0)
        
    with col3:
        st.markdown("**💰 Prezzo**")
        prezzo_min = st.number_input("Prezzo Min", value=50.0, step=5.0)
        prezzo_max = st.number_input("Prezzo Max", value=150.0, step=5.0)

    # Filtri categoria
    col4, col5 = st.columns(2)
    
    with col4:
        categorie_sel = st.multiselect(
            "🏷️ Categorie",
            options=df_market['Categoria'].unique().tolist(),
            default=df_market['Categoria'].unique().tolist()
        )
    with col5:
        ordinamento = st.selectbox(
            "📊 Ordina per",
            ["YTM_Grezzo (Decrescente)", "YTM_Grezzo (Crescente)", 
             "Prezzo (Decrescente)", "Prezzo (Crescente)",
             "Scadenza (Più vicina)", "Scadenza (Più lontana)"]
        )

    # === APPLICAZIONE FILTRI ===
    if st.button("🔍 Cerca Bond", type="primary"):
        filtered = df_market[
            (df_market['YTM_Grezzo'] >= ytm_min) &
            (df_market['YTM_Grezzo'] <= ytm_max) &
            (df_market['Anni'] >= anni_min) &
            (df_market['Anni'] <= anni_max) &
            (df_market['Prezzo'] >= prezzo_min) &
            (df_market['Prezzo'] <= prezzo_max) &
            (df_market['Categoria'].isin(categorie_sel))
        ]
        
        # Ordinamento
        if "Decrescente" in ordinamento:
            filtered = filtered.sort_values(ordinamento.split()[0], ascending=False)
        elif "Crescente" in ordinamento:
            filtered = filtered.sort_values(ordinamento.split()[0], ascending=True)
        elif "vicina" in ordinamento:
            filtered = filtered.sort_values('Anni', ascending=True)
        else:
            filtered = filtered.sort_values('Anni', ascending=False)
            
        # === RISULTATI ===
        if filtered.empty:
            st.warning("⚠️ Nessun bond trovato. Rilassa i filtri.")
        else:
            st.success(f"✅ Trovati **{len(filtered)}** bond!")
            
            # Mostra risultati
            st.dataframe(
                filtered[['ISIN', 'Desc', 'Prezzo', 'YTM_Grezzo', 'Anni', 'Categoria']].head(50).style.format({
                    'Prezzo': '{:.2f}€',
                    'YTM_Grezzo': '{:.2f}%',
                    'Anni': '{:.1f}'
                }),
                use_container_width=True
            )
            
            # Export CSV
            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                "💾 Scarica Risultati (CSV)",
                csv,
                f"bond_screener_{date.today()}.csv",
                "text/csv"
            )
            
            # Grafico distribuzione
            fig = px.scatter(
                filtered.head(100), 
                x='Anni', 
                y='YTM_Grezzo',
                color='Categoria',
                size='Prezzo',
                hover_data=['ISIN', 'Desc'],
                title="📊 Distribuzione Risultati"
            )
            st.plotly_chart(fig, use_container_width=True)

# 2. DASHBOARD MERCATO
def dashboard_mercato_ui():
    """Dashboard con vista mercato completa"""
    st.title("📊 Dashboard Mercato Bond")
    st.caption("Vista d'insieme del mercato obbligazionario oggi")
    
    with st.spinner("Caricamento dati mercato..."):
        df = carica_dati_mercato()
        if df.empty:
            st.error("❌ Database vuoto.")
            return
    
    # === KPI GLOBALI ===
    st.subheader("📈 Statistiche Mercato")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bond Disponibili", len(df))
    col2.metric("YTM Medio", f"{df['YTM_Grezzo'].mean():.2f}%")
    col3.metric("Prezzo Medio", f"{df['Prezzo'].mean():.2f}€")
    col4.metric("Scadenza Media", f"{df['Anni'].mean():.1f} anni")
    
    st.divider()
    
    # === TOP 10 RENDIMENTI ===
    st.subheader("🏆 Top 10 Rendimenti (YTM Lordo)")
    
    top10 = df.nlargest(10, 'YTM_Grezzo')
    col_tab, col_chart = st.columns([1, 1])
    with col_tab:
        st.dataframe(
            top10[['ISIN', 'Desc', 'YTM_Grezzo', 'Prezzo']].style.format({
                'YTM_Grezzo': '{:.2f}%',
                'Prezzo': '{:.2f}€'
            }),
            use_container_width=True,
            hide_index=True
        )
    with col_chart:
        fig_top = px.bar(
            top10,
            x='YTM_Grezzo',
            y='Desc',
            orientation='h',
            color='YTM_Grezzo',
            color_continuous_scale='RdYlGn'
        )
        fig_top.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_top, use_container_width=True)
    
    st.divider()
    
    # === RENDIMENTI PER CATEGORIA ===
    st.subheader("📊 Rendimenti per Categoria")
    
    df_cat = df.groupby('Categoria').agg({
        'YTM_Grezzo': 'mean',
        'ISIN': 'count'
    }).reset_index()
    df_cat.columns = ['Categoria', 'YTM Medio', 'Numero Bond']
    
    fig_cat = px.bar(
        df_cat,
        x='Categoria',
        y='YTM Medio',
        text='YTM Medio',
        color='YTM Medio',
        color_continuous_scale='Viridis'
    )
    fig_cat.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
    st.plotly_chart(fig_cat, use_container_width=True)
    
    st.divider()
    
    # === HEATMAP SCADENZA vs RENDIMENTO ===
    st.subheader("🔥 Heatmap: Scadenza vs Rendimento")
    
    # Crea bucket
    df['Bucket_Scadenza'] = pd.cut(df['Anni'], bins=[0, 2, 5, 10, 15, 30], labels=['0-2y', '2-5y', '5-10y', '10-15y', '15-30y'])
    
    pivot = df.pivot_table(
        values='YTM_Grezzo',
        index='Categoria',
        columns='Bucket_Scadenza',
        aggfunc='mean'
    ).fillna(0)
    
    fig_heat = px.imshow(
        pivot,
        text_auto='.2f',
        color_continuous_scale='RdYlGn',
        labels={'color': 'YTM %'}
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# 3. CALCOLATORE DIVERSIFICAZIONE
def diversificazione_portfolio_ui():
    """Calcolatore diversificazione automatica"""
    st.title("🧮 Calcolatore Diversificazione Portafoglio")
    st.caption("Costruisci un portafoglio bilanciato automaticamente")
    
    st.info("""
    **💡 Cos'è la Diversificazione?**
    
    È la strategia di **NON mettere tutte le uova nello stesso paniere**.
    
    Questo strumento ti aiuta a:
    - Distribuire il capitale su più bond
    - Evitare concentrazione su un singolo emittente
    - Bilanciare scadenze (Bond Ladder)
    - Ottimizzare rendimento/rischio
    """)
    
    st.divider()
    
    # === INPUT UTENTE ===
    col1, col2, col3 = st.columns(3)
    
    with col1:
        capitale_tot = st.number_input(
            "💰 Capitale Totale (€)",
            min_value=5000.0,
            value=50000.0,
            step=5000.0
        )
    with col2:
        num_bond = st.slider(
            "🎯 Numero Bond",
            min_value=3,
            max_value=10,
            value=5
        )
    with col3:
        profilo = st.selectbox(
            "⚠️ Profilo Rischio",
            ["Conservativo", "Moderato", "Aggressivo"]
        )
    
    # Preferenze avanzate
    with st.expander("⚙️ Opzioni Avanzate"):
        solo_gov = st.checkbox("Solo Governativi", value=True)
        max_per_bond_pct = st.slider("Max % per singolo bond", 10, 50, 25)
        anni_target = st.slider("Scadenza target (anni)", 1, 15, 5)
    
    # === COSTRUZIONE PORTAFOGLIO ===
    if st.button("🚀 Costruisci Portafoglio", type="primary"):
        with st.spinner("Ottimizzazione in corso..."):
            df_market = carica_dati_mercato()
            
            if df_market.empty:
                st.error("Database vuoto")
                return
            
            # Filtra per profilo rischio
            if profilo == "Conservativo":
                df_filt = df_market[df_market['Categoria'] == 'Governativo']
            elif profilo == "Moderato":
                df_filt = df_market[df_market['Categoria'].isin(['Governativo', 'Bancario'])]
            else:
                df_filt = df_market
            
            if solo_gov:
                df_filt = df_filt[df_filt['Categoria'] == 'Governativo']
            
            # Crea ladder scadenze
            df_filt = df_filt[
                (df_filt['Anni'] >= anni_target * 0.5) &
                (df_filt['Anni'] <= anni_target * 1.5)
            ]
            
            if len(df_filt) < num_bond:
                st.warning(f"Trovati solo {len(df_filt)} bond. Rilassa i filtri.")
                return
            
            # Seleziona bond
            step_anni = (df_filt['Anni'].max() - df_filt['Anni'].min()) / num_bond
            
            portfolio = []
            capitale_per_bond = capitale_tot / num_bond
            max_capitale_per_bond = (capitale_tot * max_per_bond_pct) / 100
            
            for i in range(num_bond):
                anni_min_bucket = df_filt['Anni'].min() + (i * step_anni)
                anni_max_bucket = anni_min_bucket + step_anni
                
                bucket = df_filt[
                    (df_filt['Anni'] >= anni_min_bucket) &
                    (df_filt['Anni'] < anni_max_bucket)
                ]
                
                if not bucket.empty:
                    # Seleziona migliore per YTM
                    best = bucket.nlargest(1, 'YTM_Grezzo').iloc[0]
                    
                    alloc = min(capitale_per_bond, max_capitale_per_bond)
                    
                    portfolio.append({
                        'ISIN': best['ISIN'],
                        'Desc': best['Desc'],
                        'Categoria': best['Categoria'],
                        'YTM': best['YTM_Grezzo'],
                        'Scadenza': best['Scadenza'],
                        'Anni': best['Anni'],
                        'Allocazione': alloc,
                        'Peso %': (alloc / capitale_tot) * 100
                    })
            
            df_port = pd.DataFrame(portfolio)
            
            # === RISULTATI ===
            st.success(f"✅ Portafoglio costruito con {len(df_port)} bond!")
            
            # Metriche
            m1, m2, m3, m4 = st.columns(4)
            
            m1.metric("Capitale Allocato", f"{df_port['Allocazione'].sum():,.0f}€")
            m2.metric("YTM Medio Ponderato", f"{(df_port['YTM'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum():.2f}%")
            m3.metric("Scadenza Media", f"{(df_port['Anni'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum():.1f} anni")
            m4.metric("Diversificazione", f"{len(df_port['Categoria'].unique())} categorie")
            
            st.divider()
            
            # Tabella
            st.subheader("📋 Il Tuo Portafoglio")
            
            st.dataframe(
                df_port.style.format({
                    'YTM': '{:.2f}%',
                    'Anni': '{:.1f}',
                    'Allocazione': '{:,.0f}€',
                    'Peso %': '{:.1f}%'
                }),
                use_container_width=True
            )
            
            # Grafici
            col_pie, col_bar = st.columns(2)
            
            with col_pie:
                fig_pie = px.pie(
                    df_port,
                    values='Allocazione',
                    names='Desc',
                    title='Allocazione Capitale'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_bar:
                fig_bar = px.bar(
                    df_port,
                    x='Anni',
                    y='Allocazione',
                    color='YTM',
                    title='Distribuzione Scadenze'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Verifica concentrazione
            st.divider()
            st.subheader("🛡️ Verifica Rischi")
            
            max_peso = df_port['Peso %'].max()
            
            if max_peso > 30:
                st.error(f"⚠️ ATTENZIONE: Un bond pesa il {max_peso:.1f}% (troppo!). Riduci a <25%")
            elif max_peso > 25:
                st.warning(f"⚠️ Un bond pesa il {max_peso:.1f}%. OK, ma attenzione.")
            else:
                st.success(f"✅ Massimo peso: {max_peso:.1f}%. Diversificazione ottima!")

# 4. SIMULATORE GUADAGNO FINALE
def simulatore_guadagno_ui():
    """Simulatore 'Quanto avrò tra X anni?'"""
    st.title("💰 Simulatore: Quanto Guadagno DAVVERO?")
    st.caption("Calcolo esatto del guadagno finale")
    
    st.info("""
    **🎯 A cosa serve?**
    
    Ti dice **ESATTAMENTE** quanti euro avrai tra X anni, considerando:
    - ✅ Tutte le cedole nette
    - ✅ Il rimborso finale
    - ✅ Le tasse (12.5% o 26%)
    - ✅ Le commissioni
    - ✅ L'inflazione
    """)
    
    st.divider()
    
    # Input ISIN
    isin_sim = st.text_input("ISIN da Simulare", placeholder="IT...").strip().upper()
    
    if isin_sim and valida_isin(isin_sim):
        row, info = cerca_db(isin_sim, "🌐 TUTTE")
        bond = processa_riga(row, info) if row is not None else None
        
        if bond:
            st.success(f"✅ {bond['desc']}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                inv = st.number_input("Investimento (€)", value=10000, step=1000)
            
            with col2:
                comm = st.number_input("Commissioni (€)", value=5.0, step=1.0)
            
            with col3:
                infl, _ = get_inflazione_ufficiale()
                infl_sim = st.number_input("Inflazione %", value=infl, step=0.5)
            
            if st.button("📊 Calcola", type="primary"):
                # Calcoli
                tax = determina_tasse(bond['fonte'], bond['desc'])
                df_flussi, spesa, incasso, _, ced_tot, plus = genera_flussi_dettagliati(
                    bond, inv, tax, comm, bond['pr']
                )
                
                guadagno = incasso - spesa
                anni = (bond['sc'] - date.today()).days / 365.25
                
                # Inflazione
                valore_reale = incasso / ((1 + infl_sim/100) ** anni)
                perdita_infl = spesa - valore_reale
                
                st.divider()
                
                # === BOX RISULTATO FINALE ===
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #00CC96, #00AA76); padding: 30px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 8px 16px rgba(0,0,0,0.3);">
                    <h1 style="margin: 0; font-size: 48px;">€ {incasso:,.2f}</h1>
                    <p style="margin: 5px 0; font-size: 18px;">Avrai questa cifra alla scadenza ({bond['sc'].strftime('%d/%m/%Y')})</p>
                    <hr style="border-color: rgba(255,255,255,0.3); margin: 15px 0;">
                    <div style="display: flex; justify-content: space-around; font-size: 16px;">
                        <div>
                            <div style="opacity: 0.8;">Investito Oggi</div>
                            <div style="font-size: 24px; font-weight: bold;">€ {spesa:,.2f}</div>
                        </div>
                        <div>
                            <div style="opacity: 0.8;">Guadagno Netto</div>
                            <div style="font-size: 24px; font-weight: bold;">+€ {guadagno:,.2f}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.divider()
                
                # Breakdown
                st.subheader("🧾 Breakdown Dettagliato")
                
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**📥 USCITE**")
                    st.write(f"Costo bond: {inv * bond['pr'] / 100:,.2f}€")
                    st.write(f"Commissioni: {comm:,.2f}€")
                    st.write(f"**TOTALE PAGATO: {spesa:,.2f}€**")
                
                with col_right:
                    st.markdown("**📤 ENTRATE**")
                    st.write(f"Cedole nette: {ced_tot:,.2f}€")
                    st.write(f"Plusvalenza: {plus:,.2f}€")
                    st.write(f"**TOTALE INCASSATO: {incasso:,.2f}€**")
                
                st.divider()
                
                # Inflazione
                st.subheader("📉 Impatto Inflazione")
                
                st.error(f"""
                **⚠️ ATTENZIONE ALL'INFLAZIONE!**
                
                I tuoi {incasso:,.2f}€ tra {anni:.1f} anni varranno solo **{valore_reale:,.2f}€** di oggi.
                
                Perdita potere d'acquisto: **-{perdita_infl:,.2f}€** ({(perdita_infl/spesa*100):.1f}%)
                """)
                
                # Timeline
                st.divider()
                st.subheader("📅 Timeline Mese per Mese")
                
                st.dataframe(
                    df_flussi.style.format({
                        'Importo': '{:+,.2f}€',
                        'Data': lambda x: x.strftime('%d/%m/%Y')
                    }),
                    use_container_width=True
                )
        else:
            st.error("ISIN non trovato")

# 5. SISTEMA ALERT
def alert_manager_ui():
    """Gestione alert personalizzati"""
    st.title("🔔 Alert Intelligenti")
    st.caption("Ricevi notifiche su opportunità di mercato")
    
    st.warning("⚠️ Funzione in sviluppo. Al momento puoi solo simulare gli alert.")
    
    # Inizializza session state per alert
    if 'alerts' not in st.session_state:
        st.session_state.alerts = []
    
    st.divider()
    
    # === CREA NUOVO ALERT ===
    st.subheader("➕ Crea Nuovo Alert")
    
    tipo_alert = st.selectbox(
        "Tipo Alert",
        ["Prezzo Scende Sotto", "YTM Sale Sopra", "Nuova Emissione Categoria"]
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if tipo_alert == "Prezzo Scende Sotto":
            isin_alert = st.text_input("ISIN da Monitorare")
            target = st.number_input("Prezzo Target (€)", value=95.0)
            
        elif tipo_alert == "YTM Sale Sopra":
            cat_alert = st.selectbox("Categoria", ["Governativo", "Bancario", "Corporate"])
            target = st.number_input("YTM Minimo %", value=3.5)
            
        else:
            cat_alert = st.selectbox("Categoria", ["BTP", "Corporate", "Bancari"])
            target = None
    
    with col2:
        metodo = st.radio("Metodo Notifica", ["Email", "App (Non disponibile)"], disabled=True)
    
    if st.button("✅ Attiva Alert"):
        alert = {
            'tipo': tipo_alert,
            'target': target,
            'data_creazione': date.today()
        }
        st.session_state.alerts.append(alert)
        st.success("Alert attivato! (Simulazione)")
    
    st.divider()
    
    # === ALERT ATTIVI ===
    st.subheader("📋 I Tuoi Alert Attivi")
    
    if st.session_state.alerts:
        for i, alert in enumerate(st.session_state.alerts):
            col_info, col_btn = st.columns([4, 1])
            
            with col_info:
                st.info(f"**{alert['tipo']}** - Target: {alert.get('target', 'N/A')} - Creato: {alert['data_creazione']}")
            
            with col_btn:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.alerts.pop(i)
                    st.rerun()
    else:
        st.info("Nessun alert attivo")

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
        
        st.subheader("🧭 NAVIGAZIONE")
        
        # MENU UNIFICATO
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🎯 Screener Avanzato", use_container_width=True): st.session_state.page = "Screener"; st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True): st.session_state.page = "SmartAnalysis"; st.rerun()
        if st.button("📊 Dashboard Mercato", use_container_width=True): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True): st.session_state.page = "Diversificazione"; st.rerun()
        if st.button("💰 Simulatore", use_container_width=True): st.session_state.page = "Simulatore"; st.rerun()
        if st.button("🔔 Alert Manager", use_container_width=True): st.session_state.page = "Alerts"; st.rerun()

        
        # --- SEZIONE SISTEMA UX 2.0 ---
        st.divider()
        st.caption("⚙️ STATO SISTEMA")
        
        last = get_last_update_time()
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_sources = sum(len(v) for v in SOURCES_MAP.values())
        perc_db = len(csv_files) / tot_sources if tot_sources > 0 else 0
        
        sys_c1, sys_c2 = st.columns(2)
        sys_c1.metric("Files", f"{len(csv_files)}/{tot_sources}")
        
        if last:
            last_ita = last + timedelta(hours=1)
            delta_ore = (datetime.now() - last).total_seconds() / 3600
            label_time = f"{int(delta_ore)}h fa" if delta_ore >= 1 else "Adesso"
            sys_c2.metric("Aggiornato", label_time)
        else:
            sys_c2.metric("Aggiornato", "Mai")

        if perc_db < 1.0:
            st.progress(perc_db, text="Incompletezza Database")

        if st.button("🔄 AGGIORNA DATI", type="primary", use_container_width=True):
            status = check_connection_status()
            if "OFFLINE" in status:
                st.error("❌ Sei Offline!")
            else:
                aggiorna_db()

        with st.expander("🛠️ Manutenzione Avanzata"):
            st.caption(f"Status Rete: {check_connection_status()}")
            if st.session_state.current_user in ["giulio", "guest"]:
                 if st.button("🗑️ Reset Database Completo", use_container_width=True):
                    try:
                        for f in os.listdir(DB_FOLDER): os.remove(os.path.join(DB_FOLDER, f))
                        st.toast("Database svuotato!", icon="🧹"); time.sleep(1); st.rerun()
                    except: pass
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True): 
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

    # --- ROUTING PAGINE ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Inserisci un ISIN per analizzare il bond.")
        
        st.markdown("### 🧭 Guida alle Categorie")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown("""<div class="cat-card bg-gov"><div class="cat-title">🏛️ GOV</div><div class="cat-desc">Titoli di Stato. Sicurezza.</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown("""<div class="cat-card bg-bank"><div class="cat-title">🏦 BANK</div><div class="cat-desc">Banche e Assicurazioni.</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown("""<div class="cat-card bg-corp"><div class="cat-title">🏭 CORP</div><div class="cat-desc">Aziende e Industria.</div></div>""", unsafe_allow_html=True)
        with c4: st.markdown("""<div class="cat-card bg-spec"><div class="cat-title">💎 SPEC</div><div class="cat-desc">Zero Coupon, Callable.</div></div>""", unsafe_allow_html=True)
        
        st.divider()
        
        if st.session_state.selected_isin_from_chart:
            isin_default = st.session_state.selected_isin_from_chart
            st.session_state.selected_isin_from_chart = None
        else: isin_default = ""

        col_cat, col_isin, col_btn = st.columns([2, 2, 1])
        with col_cat: cat_select = st.selectbox("Filtra Categoria", list(MACRO_CATEGORIES.keys()))
        with col_isin: isin = st.text_input("ISIN", value=isin_default, placeholder="IT...").strip().upper()
        with col_btn: 
            st.write(""); st.write("") 
            trigger_search = st.button("🔎 Cerca", use_container_width=True)
        
        if isin and (trigger_search or isin):
            if not valida_isin(isin): st.error("❌ ISIN non valido")
            else:
                filtro_cat = cat_select if not isin_default else "🌐 TUTTE"
                row, info = cerca_db(isin, filtro_cat)
                d = processa_riga(row, info) if row is not None else None
                
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality_dettagliata(d, risk, tax, st.session_state.patrimonio)
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div style="flex-grow: 1;">
                                <div style="color:#b0b3c5; font-size:13px; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">{chi}</div>
                                <div style="color:white; font-size:22px; font-weight:bold; margin-bottom:6px; line-height:1.2;">{d['desc']}</div>
                                <div style="color:#00CC96; font-size:13px;">{tipo} <span style="color:#555;">|</span> {risk_msg}</div>
                            </div>
                            <div style="text-align:right; min-width: 90px; margin-left: 10px;">
                                <h2 style="color:#00CC96; margin:0; font-size:28px;">{d['ced']}%</h2>
                                <div style="color:#b0b3c5; font-size:12px;">Cedola</div>
                            </div>
                        </div>
                        <hr style="border-color:rgba(255,255,255,0.1); margin:15px 0;">
                        <div style="display:flex; justify-content:space-between; color:#e0e0e0; font-size:14px;">
                            <div>📅 Scadenza: <b style="color:white;">{d['sc'].strftime('%d/%m/%Y')}</b></div>
                            <div>⏳ Manca: <b style="color:white;">{tempo}</b></div>
                            <div>🧾 Prezzo: <b style="color:white;">{d['pr']}€</b></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.subheader("📊 Dati Chiave")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("Prezzo", f"{d['pr']}€")
                    c2.metric("Rendimento Netto", f"{qual['ytm_netto']:.2f}%")
                    c3.metric("Rendimento Lordo", f"{risk['ytm']:.2f}%")
                    c4.metric("Cedola", f"{d['ced']}%")
                    c5.metric("Taglio Minimo", f"{d['taglio']:,.0f}€")
                    c6.metric("Duration", f"{risk['mod_dur']:.2f} Anni")

                    st.divider(); st.subheader("💡 Analisi in Breve")
                    t1, t2, t3 = st.columns(3)
                    with t1: st.markdown(f'<div class="explanation-box"><div class="explanation-title">Rendimento</div><div class="explanation-text">Netto annuo: <b>{qual["ytm_netto"]:.2f}%</b>.</div></div>', unsafe_allow_html=True)
                    with t2: 
                        ced_net = (1000 * (d['ced']/100) * (1 - tax/100))
                        st.markdown(f'<div class="explanation-box"><div class="explanation-title">Cashflow</div><div class="explanation-text">Ricevi <b>{ced_net:.2f}€</b> ogni 1k/anno.</div></div>', unsafe_allow_html=True)
                    with t3: st.markdown(f'<div class="explanation-box"><div class="explanation-title">Rischio</div><div class="explanation-text">Duration: <b>{risk["mod_dur"]:.1f}</b>.</div></div>', unsafe_allow_html=True)

                    st.divider(); st.subheader("💰 Simulatore & P&L")
                    c_sim1, c_sim2 = st.columns([1, 2])
                    with c_sim1:
                        inv = st.number_input("Investimento (€)", value=10000, step=1000)
                        comm = st.number_input("Commissioni (€)", value=5.0)
                    
                    df_f, spesa, incasso, _, _, _ = genera_flussi_dettagliati(d, inv, tax, comm, d['pr'])
                    utile = incasso - spesa
                    
                    with c_sim2:
                        st.markdown(f"""
                        <div class="receipt-box">
                            <div class="receipt-row"><span>Costo Oggi:</span> <span>{spesa:.2f} €</span></div>
                            <div class="receipt-total"><span>UTILE TOTALE:</span><span>+{utile:.2f} €</span></div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.subheader("🗓️ Quando recupero i miei soldi?")
                    df_f['Cumulativo'] = df_f['Importo'].cumsum()
                    df_pos = df_f[(df_f['Cumulativo'] >= 0) & (df_f['Data'] > date.today())]
                    if not df_pos.empty:
                        data_p = df_pos.iloc[0]['Data']
                        msg_p = f"Tra **{(data_p - date.today()).days} giorni** ({data_p.strftime('%d/%m/%Y')}) sei in pareggio."
                        col_m = "rgba(0, 204, 150, 0.1)"; ico = "✅"
                    else:
                        msg_p = "Recupero solo a scadenza."; col_m = "rgba(255, 170, 0, 0.1)"; ico = "⏳"

                    st.markdown(f"""<div style="background-color: {col_m}; padding: 15px; border-radius: 10px; border-left: 5px solid white; margin-bottom: 15px;"><span style="font-size: 20px;">{ico}</span> <span style="font-size: 16px;">{msg_p}</span></div>""", unsafe_allow_html=True)

                    fig_pnl = go.Figure()
                    y_neg = df_f['Cumulativo'].copy(); y_neg[y_neg > 0] = 0
                    fig_pnl.add_trace(go.Scatter(x=df_f['Data'], y=y_neg, fill='tozeroy', mode='lines', name='Recupero', line=dict(color='#FF4B4B', width=0), fillcolor='rgba(255, 75, 75, 0.3)', hoverinfo='skip'))
                    y_pos = df_f['Cumulativo'].copy(); y_pos[y_pos < 0] = 0
                    fig_pnl.add_trace(go.Scatter(x=df_f['Data'], y=y_pos, fill='tozeroy', mode='lines', name='Guadagno', line=dict(color='#00CC96', width=0), fillcolor='rgba(0, 204, 150, 0.3)', hoverinfo='skip'))
                    fig_pnl.add_trace(go.Scatter(x=df_f['Data'], y=df_f['Cumulativo'], mode='lines+markers', name='Saldo', line=dict(color='white', width=2), marker=dict(size=6, color='white')))
                    fig_pnl.update_layout(template="plotly_dark", height=350, showlegend=False, title="Andamento Saldo", yaxis=dict(title="€", zeroline=False), margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_pnl, use_container_width=True)

                    with st.expander("📅 Cedolario Completo"):
                        def color_red(val): return f'color: {"#ff4b4b" if val < 0 else "#00cc96"}; font-weight: bold;'
                        st.dataframe(df_f[['Data', 'Tipo', 'Importo', 'Dettagli']].style.map(color_red, subset=['Importo']).format({'Importo': '{:+.2f} €', 'Data': lambda x: x.strftime('%d/%m/%Y')}), use_container_width=True)

                else: st.warning("Bond non trovato. Aggiorna il DB.")

    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Pro Tools")
        with st.spinner("Caricamento dati..."): df_m = carica_dati_mercato()
        if df_m.empty: st.warning("DB Vuoto."); return
        
        c_s, _ = st.columns([1, 3])
        with c_s: 
            isin_s = st.text_input("ISIN", placeholder="IT...").strip().upper()
            cat_v = st.selectbox("Filtro", list(MACRO_CATEGORIES.keys()))
        
        if isin_s and valida_isin(isin_s):
            row, info = cerca_db(isin_s, cat_v)
            ds = processa_riga(row, info) if row is not None else None
            if ds:
                cat_t = "Governativo" if "BTP" in ds['desc'] else "Corporate"
                ds['Categoria'] = cat_t; ytm = calcola_rendimento_grezzo(ds['pr'], ds['ced'], ds['sc'])
                anni = (ds['sc'] - date.today()).days / 365.25
                
                st.divider(); st.subheader(f"📊 Market Landscape: {cat_t}")
                st.info("💎 Diamante = TU | 🔴 Rossa = Risk Free (Bund) | 🟡 Gialla = Media")
                
                df_z = df_m[(df_m['Anni'] >= anni - 4) & (df_m['Anni'] <= anni + 4)].copy()
                fig = px.scatter(df_z, x='Anni', y='YTM_Grezzo', color='Categoria', opacity=0.6, color_discrete_map={"Governativo": "#00CC96", "Corporate": "#636EFA", "Bancario": "#AB63FA", "Altro": "#EF553B"})
                
                x_tr = np.linspace(df_z['Anni'].min(), df_z['Anni'].max(), 100)
                df_g = df_m[df_m['Desc'].str.contains("BUND|GERMANIA", case=False, na=False)]
                if len(df_g) > 3:
                    try:
                        z = np.polyfit(df_g['Anni'], df_g['YTM_Grezzo'], 2); p = np.poly1d(z)
                        fig.add_trace(go.Scatter(x=x_tr, y=p(x_tr), mode='lines', name='Risk Free', line=dict(color='#FF4B4B', width=3)))
                    except: pass
                
                fig.add_trace(go.Scatter(x=[anni], y=[ytm], mode='markers+text', name='TU', text=['💎 TU'], textposition="top center", marker=dict(color='#FF00FF', size=20, symbol='diamond', line=dict(width=2, color='white'))))
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider(); st.subheader("🛠️ Stress Test & Efficienza")
                c_st, c_ef = st.columns([3, 2])
                with c_st:
                    shocks = [-1.0, -0.5, 0.0, +0.5, +1.0]
                    res = [{"Shock": f"{s}%", "Prezzo": f"{ds['pr']*(1-(anni*(s/100))):.2f}€"} for s in shocks]
                    st.dataframe(pd.DataFrame(res), use_container_width=True)
                with c_ef:
                    st.metric("Yield/Duration", f"{ytm/anni:.2f}x" if anni>0 else "0")
            else: st.error("Non trovato.")

    elif st.session_state.page == "Screener": bond_screener_ui()
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_portfolio_ui()
    elif st.session_state.page == "Simulatore": simulatore_guadagno_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()

if st.session_state.logged_in: main_app()
else: login()
