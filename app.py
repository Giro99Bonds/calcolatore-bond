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
# APPLE MINIMALIST DESIGN SYSTEM
# ==============================================================================

st.set_page_config(
    page_title="Bond Terminal", 
    page_icon="◆", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    /* === APPLE COLOR PALETTE === */
    :root {
        --apple-blue: #007AFF;
        --apple-green: #34C759;
        --apple-orange: #FF9500;
        --apple-red: #FF3B30;
        --apple-gray: #8E8E93;
        --apple-gray-light: #C7C7CC;
        --apple-gray-bg: #F2F2F7;
        --apple-bg: #FFFFFF;
        --apple-text: #000000;
        --apple-text-secondary: #6E6E73;
        --apple-divider: #D1D1D6;
    }
    
    /* Dark mode */
    [data-theme="dark"] {
        --apple-bg: #000000;
        --apple-gray-bg: #1C1C1E;
        --apple-text: #FFFFFF;
        --apple-text-secondary: #98989D;
        --apple-divider: #38383A;
    }
    
    /* === BASE === */
    .main {
        background-color: var(--apple-gray-bg);
        color: var(--apple-text);
    }
    
    .block-container {
        padding: 1.5rem 2rem;
        max-width: 1400px;
    }
    
    /* === TYPOGRAPHY === */
    h1 {
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: var(--apple-text);
        margin-bottom: 0.3rem;
    }
    
    h2 {
        font-size: 24px;
        font-weight: 600;
        letter-spacing: -0.3px;
        color: var(--apple-text);
    }
    
    h3 {
        font-size: 20px;
        font-weight: 600;
        color: var(--apple-text);
    }
    
    p {
        font-size: 15px;
        line-height: 1.5;
        color: var(--apple-text-secondary);
    }
    
    /* === CARDS (CLEAN) === */
    .apple-card {
        background: var(--apple-bg);
        border-radius: 18px;
        padding: 20px 24px;
        margin: 12px 0;
        border: none;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .apple-card:hover {
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    /* === METRICS (APPLE WATCH STYLE) === */
    .metric-container {
        background: var(--apple-bg);
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 1px 5px rgba(0,0,0,0.06);
    }
    
    .metric-value {
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -1px;
        color: var(--apple-text);
        margin: 4px 0;
    }
    
    .metric-label {
        font-size: 12px;
        font-weight: 500;
        color: var(--apple-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    
    .metric-delta {
        font-size: 13px;
        font-weight: 500;
        margin-top: 4px;
    }
    
    .metric-delta.positive { color: var(--apple-green); }
    .metric-delta.negative { color: var(--apple-red); }
    
    /* === CATEGORY CARDS (FROSTED GLASS) === */
    .cat-card {
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        background: rgba(255,255,255,0.95);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid rgba(0,0,0,0.04);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        height: 100%;
    }
    
    .cat-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    }
    
    .cat-card-gov { 
        background: linear-gradient(135deg, rgba(52,199,89,0.08), rgba(52,199,89,0.02));
        border-left: 4px solid var(--apple-green);
    }
    .cat-card-bank { 
        background: linear-gradient(135deg, rgba(0,122,255,0.08), rgba(0,122,255,0.02));
        border-left: 4px solid var(--apple-blue);
    }
    .cat-card-corp { 
        background: linear-gradient(135deg, rgba(255,149,0,0.08), rgba(255,149,0,0.02));
        border-left: 4px solid var(--apple-orange);
    }
    .cat-card-spec { 
        background: linear-gradient(135deg, rgba(255,59,48,0.08), rgba(255,59,48,0.02));
        border-left: 4px solid var(--apple-red);
    }
    
    .cat-title {
        font-size: 17px;
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--apple-text);
    }
    
    .cat-desc {
        font-size: 14px;
        line-height: 1.5;
        color: var(--apple-text-secondary);
        margin-bottom: 12px;
    }
    
    .cat-badge {
        display: inline-block;
        background: var(--apple-gray-bg);
        color: var(--apple-text);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 500;
        margin-right: 6px;
    }
    
    /* === BOND HEADER === */
    .bond-header {
        background: var(--apple-bg);
        border-radius: 20px;
        padding: 28px 32px;
        margin: 20px 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    }
    
    .bond-title {
        font-size: 26px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: var(--apple-text);
        margin-bottom: 8px;
        line-height: 1.2;
    }
    
    .bond-subtitle {
        font-size: 15px;
        color: var(--apple-text-secondary);
        margin-bottom: 4px;
    }
    
    .bond-badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
    }
    
    .bond-badge {
        background: var(--apple-gray-bg);
        color: var(--apple-text);
        padding: 6px 14px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 500;
    }
    
    /* === ALERTS (CLEAN & MINIMALIST) === */
    .alert {
        border-radius: 14px;
        padding: 16px 20px;
        margin: 16px 0;
        font-size: 15px;
        line-height: 1.6;
        border: none;
    }
    
    .alert-success {
        background: rgba(52,199,89,0.1);
        color: var(--apple-text);
    }
    
    .alert-warning {
        background: rgba(255,149,0,0.1);
        color: var(--apple-text);
    }
    
    .alert-danger {
        background: rgba(255,59,48,0.1);
        color: var(--apple-text);
    }
    
    .alert-info {
        background: rgba(0,122,255,0.08);
        color: var(--apple-text);
    }
    
    .alert-title {
        font-weight: 600;
        margin-bottom: 4px;
        font-size: 16px;
    }
    
    /* === BUTTONS === */
    .stButton > button {
        background: var(--apple-blue);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 10px 20px;
        font-size: 15px;
        font-weight: 500;
        transition: all 0.2s;
        box-shadow: 0 2px 8px rgba(0,122,255,0.2);
    }
    
    .stButton > button:hover {
        background: #0051D5;
        transform: scale(1.02);
        box-shadow: 0 4px 12px rgba(0,122,255,0.3);
    }
    
    /* === SIDEBAR === */
    [data-testid="stSidebar"] {
        background: var(--apple-bg);
        border-right: 1px solid var(--apple-divider);
    }
    
    [data-testid="stSidebar"] .stButton > button {
        background: transparent;
        color: var(--apple-text);
        border-radius: 10px;
        text-align: left;
        font-weight: 500;
        padding: 10px 16px;
        box-shadow: none;
    }
    
    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--apple-gray-bg);
        transform: none;
    }
    
    /* === INPUTS === */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border: 1px solid var(--apple-divider);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 15px;
        background: var(--apple-bg);
        color: var(--apple-text);
        transition: all 0.2s;
    }
    
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: var(--apple-blue);
        box-shadow: 0 0 0 3px rgba(0,122,255,0.1);
    }
    
    /* === DIVIDER === */
    hr {
        border: none;
        border-top: 1px solid var(--apple-divider);
        margin: 24px 0;
    }
    
    /* === DATAFRAME === */
    .dataframe {
        border: 1px solid var(--apple-divider);
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* === PROGRESS === */
    .stProgress > div > div {
        background: var(--apple-blue);
        border-radius: 10px;
    }
    
    /* === EXPLANATION BOXES === */
    .explanation-box {
        background: var(--apple-gray-bg);
        border-left: 4px solid var(--apple-blue);
        padding: 16px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    
    .explanation-title {
        font-weight: 600;
        color: var(--apple-text);
        font-size: 16px;
        margin-bottom: 8px;
    }
    
    .explanation-text {
        font-size: 14px;
        color: var(--apple-text-secondary);
        line-height: 1.5;
    }
    
    /* === RECEIPT BOX === */
    .receipt-box {
        background: var(--apple-bg);
        border: 1px solid var(--apple-divider);
        border-radius: 14px;
        padding: 20px;
        margin-top: 12px;
    }
    
    .receipt-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
        font-size: 15px;
        color: var(--apple-text);
    }
    
    .receipt-total {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;
        padding-top: 12px;
        border-top: 2px solid var(--apple-divider);
        font-weight: 600;
        font-size: 17px;
    }
    
    /* === USER BOX === */
    .user-box {
        background: rgba(0,122,255,0.08);
        border-left: 4px solid var(--apple-blue);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 20px;
        font-weight: 500;
        color: var(--apple-text);
    }
    
    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# [TUTTO IL CODICE FUNZIONALE RIMANE IDENTICO - SOLO CAMBIANO I MARKUP HTML]
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

SOURCES_MAP = {
    "GOV_IT": [
        {"nome": "BTP_FISSI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BTP_ITALIA_INF", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=btpitalia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CCT_VARIABILI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cct&yieldtype=G&timescale=DUR", "freq": 2}
    ],
    "GOV_EU": [
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUSTRIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=austria&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BELGIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=belgio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OLANDA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=olanda&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "GOV_PERIF": [
        {"nome": "SPAGNA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=spagna&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "PORTOGALLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=portogallo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "GOV_WORLD": [
        {"nome": "USA_TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TURCHIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=turchia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BRASILE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=brasile&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNGHERIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=ungheria&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "SUPRA": [
        {"nome": "EU_BEI_ESM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovranazionali&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbonds&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "BANCHE": [
        {"nome": "BANCHE_SENIOR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE_TIER2", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ASSICURATIVI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=assicurazioni&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "CORP": [
        {"nome": "CORP_IG_EUROPE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "HIGH_YIELD_EUR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=highyield&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "SPEC": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

MACRO_CATEGORIES = {
    "🌐 Tutte": [], 
    "🏛️ Governativi": ["GOV_IT", "GOV_EU", "GOV_PERIF", "GOV_WORLD", "SUPRA"],
    "🏦 Bancari": ["BANCHE"],
    "🏭 Corporate": ["CORP"],
    "💎 Speciali": ["SPEC"]
}

# [TUTTE LE FUNZIONI RIMANGONO IDENTICHE]
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
        return "🟢 Online"
    except: return "🔴 Offline"

def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

def get_inflazione_ufficiale():
    return 2.0, "https://www.istat.it/it/archivio/prezzi+al+consumo"

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
        chi = "🇮🇹 Stato Italiano"; tipo = "Titolo di Stato"; risk_msg = "Rischio: Medio"
    elif "GERMANIA" in fonte or "BUND" in desc:
        chi = "🇩🇪 Germania"; tipo = "Bund"; risk_msg = "Bene Rifugio"
    elif "USA" in fonte or "TREASURY" in desc:
        chi = "🇺🇸 USA"; tipo = "Treasury"; risk_msg = "Rischio Cambio"
    elif "BANCHE" in fonte or "INTESA" in desc or "UNICREDIT" in desc:
        chi = "🏦 Banca"; tipo = "Bond Bancario"; risk_msg = "Rischio Settore"
    elif "CORP" in fonte or "ENI" in desc or "ENEL" in desc:
        chi = "🏭 Azienda"; tipo = "Corporate"; risk_msg = "Rischio Emittente"
    else:
        chi = "🌍 Emittente"; tipo = "Obbligazione"; risk_msg = "Verifica Rating"

    diff = (dati['sc'] - date.today())
    anni = diff.days // 365
    mesi = (diff.days % 365) // 30
    tempo = f"{anni} anni, {mesi} mesi"
    return chi, tipo, tempo, risk_msg

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

def trova_alternative_migliori(bond_target, df_mercato, categoria_obbligatoria=None):
    if df_mercato.empty: return pd.DataFrame()
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    
    if not categoria_obbligatoria:
        categoria_obbligatoria = bond_target.get('Categoria', 'Governativo' if tax_target==12.5 else 'Corporate')

    alternative = []
    for _, row in df_mercato.iterrows():
        if categoria_obbligatoria == "Governativo" and row['Categoria'] != "Governativo": continue
        if not (anni_target - 2 <= row['Anni'] <= anni_target + 2): continue
        if row['Prezzo'] > 108: continue 
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        extra = ytm_netto_alt - ytm_netto_target
        
        if extra > 0.15: 
            link_isin = f"https://www.google.com/search?q={row['ISIN']}+bond"
            row['Tipologia'] = "✅ Miglior Rendimento"; row['YTM_Netto'] = ytm_netto_alt; row['Extra'] = extra; row['Link'] = link_isin
            alternative.append(row)
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty: return df_alt.sort_values('Extra', ascending=False).head(5)
    return pd.DataFrame()

def aggiorna_db():
    if os.path.exists(DB_FOLDER):
        for f in os.listdir(DB_FOLDER):
            try: os.unlink(os.path.join(DB_FOLDER, f))
            except: pass
    
    p = st.progress(0); s = st.empty(); tot = sum(len(v) for v in SOURCES_MAP.values()); c = 0; ok = 0
    
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1
            sleep_time = random.uniform(1.5, 3.5)
            s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            time.sleep(sleep_time) 
            p.progress(c/tot)
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
            except: time.sleep(2); pass
                
    st.session_state.last_scrape_time = datetime.now()
    s.empty(); p.empty(); st.toast(f"Database aggiornato: {ok}/{tot} files", icon="✓"); time.sleep(1); st.rerun()

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): return None, None
    search_keys = []
    
    if not cat_macro or cat_macro == "🌐 Tutte":
        search_keys = list(SOURCES_MAP.keys())
    elif cat_macro in MACRO_CATEGORIES:
        search_keys = MACRO_CATEGORIES[cat_macro]
    else:
        search_keys = list(SOURCES_MAP.keys())

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
                        return row, {"nome": src['nome'], "freq": src['freq']}
            except: continue
    return None, None

def calcola_rateo(dati):
    try:
        today_dt = date.today(); days_ced = 365 / dati['freq'] if dati['freq'] > 0 else 0
        if days_ced == 0: return 0.0
        data_ced = dati['sc']
        while data_ced > today_dt: data_ced -= timedelta(days=int(days_ced))
        return max(0.0, (dati['ced'] / dati['freq']) * ((today_dt - data_ced).days / days_ced))
    except: return 0.0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []; rateo_pct = calcola_rateo(dati)
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_netto = (nominale * rateo_pct) / 100 * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    flussi.append({"Data": date.today(), "Tipo": "USCITA", "Importo": -spesa_totale, "Dettagli": "Acquisto"})
    
    totale_cedole_nette = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = dati['sc']
        while curr > date.today():
            if curr != dati['sc']: 
                flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola"})
                totale_cedole_nette += cedola_netta
            curr -= timedelta(days=int(365 / dati['freq']))
            
    flussi.sort(key=lambda x: x['Data'])
    gain = max(0, 100 - prezzo_acquisto)
    tassa_gain = (gain / 100) * nominale * (tax_rate/100)
    rimborso_netto = nominale - tassa_gain
    ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    flussi.append({"Data": dati['sc'], "Tipo": "ENTRATA", "Importo": rimborso_netto + ultima_ced, "Dettagli": "Rimborso"})
    
    incasso_totale = totale_cedole_nette + rimborso_netto + ultima_ced
    totale_cedole_nette += ultima_ced
    plusvalenza = (gain/100)*nominale - tassa_gain

    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza

# [CONTINUA NEL PROSSIMO MESSAGGIO PER LUNGHEZZA]

# ==============================================================================
# UI COMPONENTS (APPLE MINIMALIST - SOLO MARKUP CAMBIATO)
# ==============================================================================

def login():
    st.markdown("""
    <div style='text-align:center; padding:60px 0 40px 0;'>
        <h1 style='font-size:48px; font-weight:700; letter-spacing:-1px; margin-bottom:8px;'>◆ Bond Terminal</h1>
        <p style='font-size:17px; color:var(--apple-text-secondary);'>Analizza bond con semplicità</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        u = st.text_input("Username", placeholder="giulio", label_visibility="visible").strip()
        p = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="visible")
        
        if st.button("Accedi", use_container_width=True, type="primary"):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                token = hashlib.sha256((u + "salt").encode()).hexdigest()
                st.query_params["session"] = token
                st.success("✓ Accesso riuscito")
                time.sleep(0.8)
                st.rerun()
            else:
                st.error("Credenziali errate")

def main_app():
    with st.sidebar:
        st.markdown(f"""
        <div style='padding:20px 0 16px 0;'>
            <h2 style='font-size:22px; font-weight:600; margin-bottom:4px;'>◆ Terminal</h2>
            <p style='font-size:14px; color:var(--apple-text-secondary);'>{st.session_state.current_user.capitalize()}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        if st.button("◆ Scanner", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("◆ Screener", use_container_width=True): st.session_state.page = "Screener"; st.rerun()
        if st.button("◆ Smart Analysis", use_container_width=True): st.session_state.page = "SmartAnalysis"; st.rerun()
        if st.button("◆ Dashboard", use_container_width=True): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("◆ Diversifica", use_container_width=True): st.session_state.page = "Diversificazione"; st.rerun()
        
        st.markdown("---")
        
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot = sum(len(v) for v in SOURCES_MAP.values())
        
        st.caption("SISTEMA")
        st.write(f"📁 {len(csv_files)}/{tot} dataset")
        
        if len(csv_files) < tot:
            st.progress(len(csv_files)/tot if tot > 0 else 0)
        
        if st.button("↻ Aggiorna", use_container_width=True):
            aggiorna_db()
        
        st.markdown("---")
        
        if st.button("Esci", use_container_width=True):
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

    # ROUTING
    if st.session_state.page == "Scanner":
        # Scanner Page
        st.markdown("<h1>Scanner Bond</h1><p style='margin-bottom:24px;'>Inserisci un ISIN per analizzare</p>", unsafe_allow_html=True)
        
        # Category Cards
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown("""
            <div class="cat-card cat-card-gov">
                <div class="cat-title">🏛️ Governativi</div>
                <div class="cat-desc">BTP, Bund. Sicurezza massima.</div>
                <span class="cat-badge">Tax 12.5%</span>
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown("""
            <div class="cat-card cat-card-bank">
                <div class="cat-title">🏦 Bancari</div>
                <div class="cat-desc">Bond banche. Rendimento medio.</div>
                <span class="cat-badge">Tax 26%</span>
            </div>
            """, unsafe_allow_html=True)
        
        with c3:
            st.markdown("""
            <div class="cat-card cat-card-corp">
                <div class="cat-title">🏭 Corporate</div>
                <div class="cat-desc">Aziende. Rendimento alto.</div>
                <span class="cat-badge">Tax 26%</span>
            </div>
            """, unsafe_allow_html=True)
        
        with c4:
            st.markdown("""
            <div class="cat-card cat-card-spec">
                <div class="cat-title">💎 Speciali</div>
                <div class="cat-desc">Zero coupon, callable.</div>
                <span class="cat-badge">Esperti</span>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Search
        col_cat, col_isin, col_btn = st.columns([2, 2, 1])
        with col_cat:
            cat = st.selectbox("Categoria", list(MACRO_CATEGORIES.keys()))
        with col_isin:
            isin = st.text_input("ISIN", placeholder="IT0005436693").strip().upper()
        with col_btn:
            st.write("")
            st.write("")
            trigger = st.button("Cerca", use_container_width=True, type="primary")
        
        if isin and trigger:
            if not valida_isin(isin):
                st.error("ISIN non valido")
            else:
                row, info = cerca_db(isin, cat)
                bond = processa_riga(row, info) if row else None
                
                if not bond:
                    st.warning("Bond non trovato")
                else:
                    tax = determina_tasse(bond['fonte'], bond['desc'])
                    risk = calcola_metriche_rischio(bond['pr'], bond['ced'], bond['sc'], bond['freq'])
                    ytm_netto = risk['ytm'] * (1 - tax/100) if risk else 0
                    ytm_reale = ytm_netto - 2.0
                    anni = (bond['sc'] - date.today()).days / 365.25
                    chi, tipo, tempo, risk_msg = identikit_bond(bond)
                    
                    # Bond Header (Minimalist)
                    st.markdown(f"""
                    <div class="bond-header">
                        <div class="bond-subtitle">{chi}</div>
                        <div class="bond-title">{bond['desc']}</div>
                        <div class="bond-subtitle" style="margin-top:4px;">{tipo} · {risk_msg}</div>
                        <div class="bond-badge-row">
                            <span class="bond-badge">Cedola {bond['ced']}%</span>
                            <span class="bond-badge">Scadenza {bond['sc'].strftime('%d/%m/%Y')}</span>
                            <span class="bond-badge">Prezzo {bond['pr']}€</span>
                            <span class="bond-badge">Tasse {tax}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Metrics (Apple Watch Style)
                    st.markdown("<h3 style='margin:24px 0 16px 0;'>Metriche Chiave</h3>", unsafe_allow_html=True)
                    
                    m1, m2, m3, m4 = st.columns(4)
                    
                    with m1:
                        delta_class = "negative" if bond['pr'] > 100 else "positive"
                        delta_text = "Sopra pari" if bond['pr'] > 100 else "Sotto pari"
                        st.markdown(f"""
                        <div class="metric-container">
                            <div class="metric-label">Prezzo</div>
                            <div class="metric-value">{bond['pr']:.2f}€</div>
                            <div class="metric-delta {delta_class}">{delta_text}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with m2:
                        st.markdown(f"""
                        <div class="metric-container">
                            <div class="metric-label">YTM Netto</div>
                            <div class="metric-value">{ytm_netto:.2f}%</div>
                            <div class="metric-delta">Dopo tasse</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with m3:
                        delta_class = "negative" if ytm_reale < 0 else "positive"
                        st.markdown(f"""
                        <div class="metric-container">
                            <div class="metric-label">YTM Reale</div>
                            <div class="metric-value">{ytm_reale:.2f}%</div>
                            <div class="metric-delta {delta_class}">Dopo inflazione</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with m4:
                        st.markdown(f"""
                        <div class="metric-container">
                            <div class="metric-label">Scadenza</div>
                            <div class="metric-value">{anni:.1f}</div>
                            <div class="metric-delta">anni</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # Alerts (Clean)
                    if ytm_reale < 0:
                        st.markdown(f"""
                        <div class="alert alert-danger">
                            <div class="alert-title">⚠ Attenzione Rendimento</div>
                            Rendimento reale negativo ({ytm_reale:.2f}%). Perdi potere d'acquisto.
                        </div>
                        """, unsafe_allow_html=True)
                    elif ytm_reale > 2:
                        st.markdown(f"""
                        <div class="alert alert-success">
                            <div class="alert-title">✓ Buon Rendimento</div>
                            Rendimento reale positivo ({ytm_reale:.2f}%). Guadagni anche dopo inflazione.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="alert alert-warning">
                            <div class="alert-title">○ Rendimento Marginale</div>
                            Rendimento reale {ytm_reale:.2f}%. Copri l'inflazione senza grandi margini.
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # Simulatore (Clean)
                    st.markdown("<h3>Simulatore Investimento</h3>", unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        inv = st.number_input("Capitale (€)", value=10000.0, step=1000.0)
                    with col2:
                        comm = st.number_input("Commissioni (€)", value=5.0, step=1.0)
                    with col3:
                        infl = st.number_input("Inflazione %", value=2.0, step=0.5)
                    
                    df_flussi, spesa_tot, incasso_tot, costo_rateo, totale_cedole, plusval = genera_flussi_dettagliati(bond, inv, tax, comm, bond['pr'])
                    guadagno = incasso_tot - spesa_tot
                    
                    # Result Box (Clean)
                    col_r1, col_r2 = st.columns(2)
                    
                    with col_r1:
                        st.markdown(f"""
                        <div class="apple-card" style="text-align:center; background: linear-gradient(135deg, rgba(0,122,255,0.1), rgba(0,122,255,0.05));">
                            <div style="font-size:14px; color:var(--apple-text-secondary); margin-bottom:8px;">GUADAGNO NETTO</div>
                            <div style="font-size:36px; font-weight:700; color:var(--apple-blue); margin:8px 0;">+{guadagno:,.0f}€</div>
                            <div style="font-size:13px; color:var(--apple-text-secondary);">In {anni:.1f} anni</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_r2:
                        st.markdown(f"""
                        <div class="receipt-box">
                            <div style="font-size:12px; color:var(--apple-text-secondary); margin-bottom:12px;">RIEPILOGO</div>
                            <div class="receipt-row">
                                <span>Spesa oggi</span>
                                <span style="color:var(--apple-red);">-{spesa_tot:,.0f}€</span>
                            </div>
                            <div class="receipt-row">
                                <span>Cedole nette</span>
                                <span style="color:var(--apple-green);">+{totale_cedole:,.0f}€</span>
                            </div>
                            <div class="receipt-row">
                                <span>Rimborso</span>
                                <span style="color:var(--apple-green);">+{inv:,.0f}€</span>
                            </div>
                            <div class="receipt-total">
                                <span>Totale</span>
                                <span style="color:var(--apple-green);">+{incasso_tot:,.0f}€</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    
    elif st.session_state.page == "Dashboard":
        st.markdown("<h1>Dashboard Mercato</h1>", unsafe_allow_html=True)
        st.info("Dashboard in sviluppo")
    
    elif st.session_state.page == "Diversificazione":
        st.markdown("<h1>Diversificazione</h1>", unsafe_allow_html=True)
        st.info("Tool in sviluppo")
    
    elif st.session_state.page == "Screener":
        st.markdown("<h1>Screener</h1>", unsafe_allow_html=True)
        st.info("Screener in sviluppo")
    
    elif st.session_state.page == "SmartAnalysis":
        st.markdown("<h1>Smart Analysis</h1>", unsafe_allow_html=True)
        st.info("Analysis in sviluppo")

if st.session_state.logged_in:
    main_app()
else:
    login()
