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
import matplotlib.pyplot as plt # Aggiunto per evitare errori grafici
import json
import yfinance as yf 

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

    /* --- SCONTRINO (Style Nativo Streamlit) --- */
    .receipt-box {
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        background-color: rgba(255, 255, 255, 0.02);
    }
    .receipt-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 14px; }
    .receipt-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; margin-top: 10px; padding-top: 10px; border-top: 1px solid #444; }

    /* --- ALTRI STILI --- */
    .user-box { padding: 10px; background-color: rgba(0, 204, 150, 0.1); border-left: 5px solid #00CC96; border-radius: 5px; margin-bottom: 20px; font-weight: bold; color: inherit; }
    
    [data-testid="stSidebar"] div.stButton > button { background-color: transparent; border: none; text-align: left; color: inherit !important; font-weight: 600; }
    [data-testid="stSidebar"] div.stButton > button:hover { padding-left: 10px; background-color: rgba(128, 128, 128, 0.1); border-radius: 5px; }
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
# 3. MAPPA FONTI
# ==============================================================================

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
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1}
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
    "🌐 TUTTE": [], 
    "🏛️ GOVERNATIVI": ["GOV_IT", "GOV_EU", "GOV_PERIF", "GOV_WORLD", "SUPRA"],
    "🏦 BANCARI": ["BANCHE"],
    "🏭 CORPORATE": ["CORP"],
    "💎 SPECIALI": ["SPEC"]
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
# --- NUOVE FUNZIONI DI INTELLIGENZA BOND ---
def detect_bond_features(desc, isin):
    """
    Rileva automaticamente: Cumulative, Zero Coupon, Callable, Tassazione.
    Sostituisce le vecchie logiche sparse.
    """
    desc = str(desc).upper()
    features = {
        'is_cumulative': False,     # Cedola pagata solo a scadenza
        'is_zero_coupon': False,    # Nessuna cedola
        'is_callable': False,       # Emittente può rimborsare prima
        'tax_rate': 26.0            # Default Corporate/Bank
    }
    
    # 1. Rilevamento Struttura (Parole Chiave)
    if "CUMUL" in desc or "ZC" in desc or "ZERO" in desc or "STRIP" in desc:
        features['is_cumulative'] = True
        if "ZERO" in desc or "ZC" in desc or "STRIP" in desc:
            features['is_zero_coupon'] = True
            
    if "CALL" in desc or "CALLABLE" in desc:
        features['is_callable'] = True

    # 2. Rilevamento Tassazione Agevolata (White List 12.5%)
    whitelist_tax = [
        "BTP", "BOT", "CCT", "BUND", "OAT", "TREASURY", "USA ", 
        "BEI", "EU ", "WORLD BANK", "EIB", "ROMANIA", "UNGHERIA", "TURCHIA"
    ]
    if any(x in desc for x in whitelist_tax):
        features['tax_rate'] = 12.5
        
    return features
    
def detect_valuta(desc, isin):
    """Rileva la valuta dalla descrizione"""
    desc = str(desc).upper()
    if "USA" in desc or "TREASURY" in desc or "DOLLAR" in desc: return "USD"
    if "TURCHIA" in desc or "TRY" in desc or "LIRA" in desc: return "TRY"
    if "BRASILE" in desc or "BRL" in desc or "REAL" in desc: return "BRL"
    if "ROMANIA" in desc or "RON" in desc: return "RON"
    if "GBP" in desc or "UK" in desc: return "GBP"
    return "EUR" # Default
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
        
        desc = str(row[c_de]).replace("â‚¬", "€").strip()
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        ced = 0.0
        if m: ced = float(m.group(1).replace(',', '.'))
        
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]): taglio = pulisci_taglio(row[c_min])
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating, "isin": isin_val}
    except: return None
# ==============================================================================
# FUNZIONE MANCANTE: INTELLIGENZA BOND
# ==============================================================================


def detect_valuta(desc, isin):
    """Rileva la valuta dalla descrizione"""
    desc = str(desc).upper()
    if "USA" in desc or "TREASURY" in desc or "DOLLAR" in desc: return "USD"
    if "TURCHIA" in desc or "TRY" in desc or "LIRA" in desc: return "TRY"
    if "BRASILE" in desc or "BRL" in desc or "REAL" in desc: return "BRL"
    if "ROMANIA" in desc or "RON" in desc: return "RON"
    if "GBP" in desc or "UK" in desc: return "GBP"
    return "EUR" # Default
def identikit_bond(dati):
    desc = dati['desc'].upper()
    fonte = dati['fonte'].upper()
    risk_msg = ""; chi = ""; tipo = ""

    if "ITALIA" in fonte or "BTP" in desc or "BOT" in desc:
        chi = "🇮🇹 STATO ITALIANO"; tipo = "Titolo di Stato"; risk_msg = "Rischio Paese: Medio"
    elif "GERMANIA" in fonte or "BUND" in desc:
        chi = "🇩🇪 GERMANIA"; tipo = "Bund (Risk Free)"; risk_msg = "Bene Rifugio"
    elif "USA" in fonte or "TREASURY" in desc:
        chi = "🇺🇸 USA"; tipo = "Treasury Bond"; risk_msg = "Rischio Cambio"
    elif "BANCHE" in fonte or "INTESA" in desc or "UNICREDIT" in desc:
        chi = "🏦 SETTORE BANCARIO"; tipo = "Bond Bancario"; risk_msg = "Rischio Settoriale"
    elif "CORP" in fonte or "ENI" in desc or "ENEL" in desc:
        chi = "🏭 AZIENDA"; tipo = "Corporate Bond"; risk_msg = "Rischio Emittente"
    else:
        chi = "🌍 EMITTENTE"; tipo = "Obbligazione"; risk_msg = "Rating da verificare"

    diff = (dati['sc'] - date.today())
    anni = diff.days // 365
    mesi = (diff.days % 365) // 30
    tempo = f"{anni} Anni e {mesi} Mesi"
    return chi, tipo, tempo, risk_msg

# ==============================================================================
# 5. RISK ENGINE E SCORECARD (VERSIONE INDISTRUTTIBILE)
# ==============================================================================
# --- INIZIO NUOVO BLOCCO (COPIA DA QUI) ---

def detect_bond_features(desc, isin):
    """Rileva automaticamente se il bond è CUMULATIVE, CALLABLE o ZERO COUPON."""
    desc = str(desc).upper()
    features = {
        'is_cumulative': False, 'is_zero_coupon': False, 
        'is_callable': False, 'tax_rate': 26.0
    }
    # 1. Rilevamento Struttura
    if "CUMUL" in desc or "ZC" in desc or "ZERO" in desc or "STRIP" in desc:
        features['is_cumulative'] = True
        if "ZERO" in desc or "ZC" in desc: features['is_zero_coupon'] = True
    if "CALL" in desc or "CALLABLE" in desc:
        features['is_callable'] = True
    
    # 2. Tassazione Agevolata (12.5%)
    whitelist = ["BTP", "BOT", "CCT", "BUND", "OAT", "TREASURY", "USA ", "BEI", "EU ", "WORLD BANK", "EIB", "ROMANIA", "UNGHERIA", "TURCHIA"]
    if any(x in desc for x in whitelist): features['tax_rate'] = 12.5
    
    return features

def calcola_flussi_reali(dati, prezzo_acquisto, nominale=100.0):
    """
    Calcola i flussi reali spostando gli interessi a scadenza se CUMULATIVE.
    Questo corregge il rendimento dei bond Barclays/Zero Coupon/Unicredit Callable.
    """
    feats = detect_bond_features(dati['desc'], dati.get('isin', ''))
    tax = feats['tax_rate']
    flussi = []
    
    today = date.today()
    settle = today + timedelta(days=2) # Data valuta
    
    # 1. Rateo (Se non è ZC)
    rateo_netto = 0.0
    rateo_lordo_perc = 0.0
    if not feats['is_zero_coupon'] and dati['freq'] > 0:
        data_prec = dati['sc']
        while data_prec > today: data_prec -= timedelta(days=int(365/dati['freq']))
        giorni = (today - data_prec).days
        rateo_lordo_perc = (dati['ced']) * (giorni/365.0)
        rateo_netto = (rateo_lordo_perc * nominale / 100) * (1 - tax/100)
    
    spesa = (prezzo_acquisto * nominale / 100) + rateo_netto
    flussi.append({'Data': settle, 'Importo': -spesa, 'Tipo': 'ACQUISTO'})
    
    # 2. Cedole Future
    interessi_finali = 0.0
    if dati['freq'] > 0 and not feats['is_zero_coupon']:
        if feats['is_cumulative']:
            # CUMULATIVE: Nessun pagamento ora. Si accumula tutto alla fine.
            anni_residui = (dati['sc'] - settle).days / 365.25
            interessi_finali = (dati['ced'] * nominale / 100) * anni_residui
            # Aggiungo il rateo già maturato
            interessi_finali += (rateo_lordo_perc * nominale / 100)
        else:
            # STANDARD: Cedole periodiche
            cn = (dati['ced'] * nominale / 100) / dati['freq'] * (1 - tax/100)
            curr = dati['sc']
            while curr > settle:
                flussi.append({'Data': curr, 'Importo': cn, 'Tipo': 'CEDOLA'})
                curr -= timedelta(days=int(365/dati['freq']))
    
    # 3. Rimborso (Gestione Tasse Capital Gain)
    gain = max(0, nominale - (prezzo_acquisto * nominale / 100))
    tax_gain = gain * (tax/100)
    rimborso_netto = nominale - tax_gain
    
    if feats['is_cumulative']:
        rimborso_netto += interessi_finali * (1 - tax/100)
        
    flussi.append({'Data': dati['sc'], 'Importo': rimborso_netto, 'Tipo': 'RIMBORSO'})
    
    # Ordino
    df = pd.DataFrame(flussi).groupby('Data', as_index=False).sum().sort_values('Data')
    df['Tipo'] = df.apply(lambda x: 'ACQUISTO' if x['Importo'] < 0 else 'FLUSSO', axis=1)
    return df, spesa, feats

def xirr(df_flussi):
    """Calcola il rendimento netto reale (TIR)."""
    try:
        dates = df_flussi['Data'].tolist(); amounts = df_flussi['Importo'].tolist()
        if not amounts or amounts[0] >= 0: return 0.0
        def xnpv(rate, amounts, dates):
            if rate <= -1.0: return float('inf')
            d0 = dates[0]
            return sum([a / ((1 + rate) ** ((d - d0).days / 365.0)) for a, d in zip(amounts, dates)])
        return newton(lambda r: xnpv(r, amounts, dates), 0.05) * 100
    except: return 0.0

# --- FINE NUOVO BLOCCO ---
def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """Calcolo iterativo preciso (XIRR style)"""
    try:
        if prezzo <= 0: return None
        # Se la frequenza è 0 o non definita, assumiamo annuale (1) per non bloccare il calcolo
        if freq is None or freq <= 0: freq = 1
        
        cedola_annua = cedola_pct / 100
        giorni = (scadenza - date.today()).days
        anni = giorni / 365.25
        
        if anni <= 0: return 0.0 # Scaduto o scade oggi
        
        n_periodi = max(1, int(anni * freq))
        c = (cedola_annua * face_value) / freq
        
        # Stima iniziale (Rendimento Grezzo)
        ytm_guess = (cedola_annua + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
        
        # Funzione prezzo per Newton
        def price_func(y):
            if y <= -1: return float('inf') # Protezione matematica
            pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n_periodi + 1)])
            pv += face_value / ((1 + y/freq) ** n_periodi)
            return pv - prezzo
            
        # Tentativo di risoluzione
        ytm = newton(price_func, ytm_guess, maxiter=50)
        return ytm
    except:
        return None # Se fallisce Newton, restituisce None e attiviamo il fallback

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    """
    Calcola YTM e Duration. 
    Se il metodo preciso fallisce, usa il metodo grezzo (Fallback).
    Non restituisce MAI None che fa crashare l'app.
    """
    try:
        if prezzo <= 0: 
            return {"ytm": 0.0, "mod_dur": 0.0}

        # 1. TENTATIVO PRECISO
        ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq)
        
        # 2. FALLBACK: METODO GREZZO (Se il preciso fallisce)
        if ytm is None:
            giorni = (scadenza - date.today()).days
            anni = max(giorni / 365.25, 0.01) # Evita div by zero
            # Formula scolastica: (Cedola + (GuadagnoCapitale/Anni)) / Prezzo
            guadagno_capitale = (100 - prezzo)
            ytm = ((cedola_pct + (guadagno_capitale / anni)) / prezzo) / 100

        # Calcolo Duration approssimata
        giorni = (scadenza - date.today()).days
        anni = max(giorni / 365.25, 0.0)
        # Modified Duration semplificata
        mod_dur = anni / (1 + ytm) if ytm > -0.9 else 0 

        return {"ytm": ytm * 100, "mod_dur": mod_dur}
        
    except Exception as e:
        # CASO DISPERATO (Dati corrotti)
        return {"ytm": 0.0, "mod_dur": 0.0}

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU", "ROMANIA", "UNGHERIA", "TURCHIA"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def analizza_bond_quality_dettagliata(dati, risk, tax, patrimonio):
    breakdown = []
    score = 100
    
    # Check Dati
    taglio = dati.get('taglio', 1000.0)
    prezzo = dati.get('pr', 100.0)
    
    # 1. Peso in Portafoglio
    peso_bond = (taglio / patrimonio) * 100
    if peso_bond > 20: punti = -30; msg = f"Rischio alto: pesa il {peso_bond:.1f}%"; colore = "score-bad"
    elif peso_bond > 10: punti = -10; msg = f"Taglio impegnativo: pesa il {peso_bond:.1f}%"; colore = "score-neutral"
    else: punti = 0; msg = f"Taglio sostenibile: pesa il {peso_bond:.1f}%"; colore = "score-good"
    score += punti
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{taglio/1000:.0f}k €", "msg": msg, "pts": punti, "col": colore})

    # 2. Prezzo
    if prezzo > 110: puntos = -15; msg="Molto sopra la pari"; col="score-bad"
    elif prezzo > 102: puntos = -5; msg="Sopra la pari"; col="score-neutral"
    elif prezzo < 95: puntos = +5; msg="Sotto la pari"; col="score-good"
    else: puntos=0; msg="Prezzo Fair"; col="score-good"
    score += puntos
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{prezzo:.2f}", "msg": msg, "pts": puntos, "col": col})

    # 3. Rendimento
    ytm_lordo = risk['ytm']
    ytm_net = ytm_lordo * (1 - tax / 100)
    
    if ytm_net < 1.5: puntos=-20; msg="Rendimento basso"; col="score-bad"
    elif ytm_net > 3.0: puntos=+15; msg="Ottimo rendimento"; col="score-good"
    else: puntos=0; msg="Rendimento medio"; col="score-neutral"
    score += puntos
    breakdown.append({"cat": "📈 Rendimento", "val": f"{ytm_net:.2f}%", "msg": msg, "pts": puntos, "col": col})

    # 4. Tassazione
    if tax < 20: puntos=+5; msg="Tassazione agevolata"; col="score-good"
    else: puntos=-5; msg="Tassazione piena"; col="score-neutral"
    score += puntos
    breakdown.append({"cat": "🏛️ Tassazione", "val": f"{tax}%", "msg": msg, "pts": puntos, "col": col})

    flags = []
    if score < 50: flags.append(("red", "Score Basso"))
    
    return {"score": max(0, min(100, score)), "breakdown": breakdown, "ytm_netto": ytm_net, "flags": flags}

# ==============================================================================
# 6. LOGICHE SMART & DB (COMPLETO)
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

@st.cache_data(ttl=3600)
def carica_tutto_mercato():
    """Versione ottimizzata per dashboard e analisi"""
    return carica_dati_mercato().rename(columns={'Categoria': 'Tipo', 'Desc': 'Descrizione'})

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
            s.text(f"⏳ Attesa prudenziale ({sleep_time:.1f}s) -> Scarico {src['nome']} ({c}/{tot})...")
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
    s.empty(); p.empty(); st.toast(f"Database Rigenerato: {ok}/{tot} files.", icon="🛡️"); time.sleep(1); st.rerun()

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): return None, None
    search_keys = list(SOURCES_MAP.keys()) if not cat_macro or cat_macro == "🌐 TUTTE" else MACRO_CATEGORIES.get(cat_macro, [])
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
        today_dt = date.today(); days_ced = 365 / dati['freq'] if dati['freq'] > 0 else 0
        if days_ced == 0: return 0.0
        data_ced = dati['sc']
        while data_ced > today_dt: data_ced -= timedelta(days=int(days_ced))
        return max(0.0, (dati['ced'] / dati['freq']) * ((today_dt - data_ced).days / days_ced))
    except: return 0.0

# --- NUOVO MOTORE DI CALCOLO FLUSSI (XIRR COMPLIANT) ---
def calcola_flussi_reali(dati, prezzo_acquisto, nominale=100.0):
    """
    Genera i flussi di cassa ESATTI per il calcolo XIRR.
    Gestisce: Rateo, Tassazione differita sul Capital Gain, Cedole Cumulative.
    """
    feats = detect_bond_features(dati['desc'], dati.get('isin', ''))
    tax = feats['tax_rate']
    flussi = []
    
    # Date
    today = date.today()
    settlement = today + timedelta(days=2) # Data valuta T+2
    
    # --- 1. FLUSSO USCITA (ACQUISTO) ---
    rateo_netto = 0.0
    rateo_lordo_perc = 0.0
    
    # Se il bond ha cedola e non è ZC puro, calcoliamo il rateo che paghiamo oggi
    if not feats['is_zero_coupon'] and dati['freq'] > 0:
        data_prec = dati['sc']
        # Torniamo indietro per trovare l'inizio godimento cedola attuale
        while data_prec > today: 
            data_prec -= timedelta(days=int(365/dati['freq']))
        
        giorni_maturati = (today - data_prec).days
        rateo_lordo_perc = (dati['ced']) * (giorni_maturati / 365.0)
        # Il rateo si paga al netto
        rateo_netto = (rateo_lordo_perc * nominale / 100) * (1 - tax/100)

    spesa_totale = (prezzo_acquisto * nominale / 100) + rateo_netto
    flussi.append({'Data': settlement, 'Importo': -spesa_totale, 'Tipo': 'ACQUISTO'})
    
    # --- 2. FLUSSI ENTRATA (CEDOLE) ---
    interessi_finali_cumulati = 0.0
    
    if dati['freq'] > 0 and not feats['is_zero_coupon']:
        if feats['is_cumulative']:
            # CUMULATIVE: Nessun pagamento intermedio. Tutto alla fine.
            anni_residui = (dati['sc'] - settlement).days / 365.25
            interessi_finali_cumulati = (dati['ced'] * nominale / 100) * anni_residui
            # Aggiungiamo il rateo che abbiamo anticipato oggi
            interessi_finali_cumulati += (rateo_lordo_perc * nominale / 100)
        else:
            # STANDARD: Cedole periodiche
            cn = (dati['ced'] * nominale / 100) / dati['freq'] * (1 - tax/100)
            curr = dati['sc']
            while curr > settlement:
                flussi.append({'Data': curr, 'Importo': cn, 'Tipo': 'CEDOLA'})
                curr -= timedelta(days=int(365/dati['freq']))
    
    # --- 3. FLUSSO RIMBORSO (CAPITALE + TAX GAIN DIFFERITA) ---
    rimborso_lordo = nominale # Assumiamo rimborso a 100
    
    # Calcolo Capital Gain (Prezzo Fiscale = Prezzo Secco Acquisto)
    gain = max(0, rimborso_lordo - (prezzo_acquisto * nominale / 100))
    tax_gain = gain * (tax/100)
    
    rimborso_netto = rimborso_lordo - tax_gain
    
    # Se è Cumulative, aggiungo la "maxi cedola" finale tassata
    if feats['is_cumulative']:
        interessi_netti = interessi_finali_cumulati * (1 - tax/100)
        rimborso_netto += interessi_netti

    # Aggiungo il rimborso alla data di scadenza
    found = False
    for f in flussi:
        if f['Data'] == dati['sc']:
            f['Importo'] += rimborso_netto
            f['Tipo'] += "+RIMBORSO"
            found = True
            break
            
    if not found:
        flussi.append({'Data': dati['sc'], 'Importo': rimborso_netto, 'Tipo': 'RIMBORSO'})
    
    # Ordino per data e creo DataFrame
    df = pd.DataFrame(flussi).sort_values('Data')
    return df, spesa_totale, feats

def xirr(df_flussi):
    """Calcola il rendimento reale (TIR) dai flussi"""
    try:
        dates = df_flussi['Data'].tolist()
        amounts = df_flussi['Importo'].tolist()
        if not amounts or amounts[0] >= 0: return 0.0
        
        def xnpv(rate, amounts, dates):
            if rate <= -1.0: return float('inf')
            d0 = dates[0]
            return sum([a / ((1 + rate) ** ((d - d0).days / 365.0)) for a, d in zip(amounts, dates)])
            
        return newton(lambda r: xnpv(r, amounts, dates), 0.05) * 100
    except: return 0.0

# ==============================================================================
# 🆕 GESTIONE VALUTE LIVE
# ==============================================================================

def detect_valuta(desc, isin):
    """Cerca di capire la valuta dalla descrizione o dall'ISIN"""
    desc = desc.upper()
    if "USA" in desc or "TREASURY" in desc or "DOLLAR" in desc: return "USD"
    if "TURCHIA" in desc or "LIRA" in desc or "TRY" in desc: return "TRY"
    if "BRASILE" in desc or "REAL" in desc: return "BRL"
    if "ROMANIA" in desc or "LEU" in desc or "RON" in desc: return "RON"
    if "GB" in isin[:2] or "UK" in desc: return "GBP"
    return "EUR" # Default

@st.cache_data(ttl=3600)
def get_tasso_cambio_live(da, a):
    """Scarica il tasso LIVE da Yahoo Finance"""
    da = da.upper(); a = a.upper()
    if da == a: return 1.0
    ticker = f"{da}{a}=X"
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty: return float(data['Close'].iloc[-1])
        # Riprova inverso
        ticker_inv = f"{a}{da}=X"
        data_inv = yf.Ticker(ticker_inv).history(period="1d")
        if not data_inv.empty: return 1.0 / float(data_inv['Close'].iloc[-1])
    except: pass
    
    # Fallback se Yahoo non va
    fallback = {"EURUSD": 1.05, "EURTRY": 36.00, "EURBRL": 6.10, "EURGBP": 0.85, "EURRON": 4.97}
    return fallback.get(f"{da}{a}", 1.0)

# -----------------------------------------------------------------------------
# 🆕 FUNZIONALITÀ RETAIL AVANZATE
# -----------------------------------------------------------------------------

# 1. BOND SCREENER INTELLIGENTE (FUNZIONE VECCHIA - RIMPIAZZATA DALLA PAGINA PRINCIPALE)
# Lasciamo vuota per compatibilità se serve, ma la logica è nel main
def bond_screener_ui():
    pass 

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
# 7. INTERFACCIA UTENTE PRINCIPALE
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
# ==============================================================================
# 🧠 SMART ANALYSIS UI (DA INCOLLARE PRIMA DI MAIN_APP)
# ==============================================================================

def smart_analysis_ui():
    st.title("🧠 Smart Analysis & Confronto")
    st.caption("Verifica se il tuo bond è un affare rispetto al mercato (Scatter Plot).")
    
    # Caricamento dati
    with st.spinner("Analisi mercato in corso..."):
        df_m = carica_tutto_mercato()
    
    if df_m.empty: 
        st.warning("⚠️ Database vuoto. Aggiorna i dati.")
        return

    c_s, _ = st.columns([1, 2])
    isin_s = c_s.text_input("Inserisci ISIN da confrontare", placeholder="IT...").strip().upper()
    
    if isin_s:
        target_bond = df_m[df_m['ISIN'] == isin_s]
        if not target_bond.empty:
            b = target_bond.iloc[0]
            ytm_target = b['YTM_Grezzo']
            try: anni_target = (pd.to_datetime(b['Scadenza']).date() - date.today()).days / 365.25
            except: anni_target = 0
            
            # 1. KPI VELOCI
            st.divider()
            k1, k2, k3 = st.columns(3)
            k1.metric("Tuo Bond (Lordo)", f"{ytm_target:.2f}%")
            
            # Filtro per grafico (Tolgo outlier)
            df_viz = df_m[
                (df_m['ISIN'] != isin_s) & 
                (df_m['YTM_Grezzo'] > -1) & (df_m['YTM_Grezzo'] < 15) &
                (df_m['Anni'] > 0) & (df_m['Anni'] <= 50)
            ].copy()
            
            avg_cat = df_viz[df_viz['Tipo'] == b['Tipo']]['YTM_Grezzo'].mean()
            delta = ytm_target - avg_cat
            k2.metric(f"Media {b['Tipo']}", f"{avg_cat:.2f}%")
            k3.metric("Posizione", "Sopra Media" if delta>0 else "Sotto Media", f"{delta:.2f}%")

            # 2. GRAFICO SCATTER PLOT
            st.subheader("📍 La Mappa del Tesoro")
            
            fig = go.Figure()
            
            # Limiti assi intelligenti
            max_x = min(max(10, anni_target * 2), 50)
            max_y = max(ytm_target + 3, 8)
            
            palette = {
                "Governativo": "rgba(34, 139, 34, 0.7)", 
                "Bancario": "rgba(30, 144, 255, 0.7)",
                "Corporate": "rgba(255, 140, 0, 0.7)", 
                "Speciali": "rgba(138, 43, 226, 0.7)",
                "Altro": "rgba(102, 51, 153, 0.6)" 
            }
            
            # Disegno categorie
            for tipo in df_viz['Tipo'].unique():
                sub = df_viz[df_viz['Tipo'] == tipo]
                col = palette.get(tipo, palette["Altro"])
                fig.add_trace(go.Scatter(
                    x=sub['Anni'], y=sub['YTM_Grezzo'], mode='markers',
                    marker=dict(color=col, size=6), name=str(tipo),
                    text=sub['Descrizione'],
                    hovertemplate="<b>%{text}</b><br>Tipo: "+str(tipo)+"<br>Scadenza: %{x:.1f}y<br>YTM: %{y:.2f}%<extra></extra>"
                ))
            
            # IL TUO BOND (Diamante Rosso)
            fig.add_trace(go.Scatter(
                x=[anni_target], y=[ytm_target], mode='markers',
                marker=dict(color='red', size=16, symbol='diamond', line=dict(color='black', width=2)),
                name="👉 IL TUO BOND", hovertemplate="<b>TU SEI QUI</b><br>YTM: %{y:.2f}%<extra></extra>"
            ))
            
            fig.update_layout(
                template="plotly_white", height=500,
                xaxis=dict(title="Scadenza (Anni)", range=[0, max_x]),
                yaxis=dict(title="Rendimento Lordo (%)", range=[0, max_y]),
                legend=dict(orientation="h", y=-0.2), margin=dict(t=30, b=80)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 3. TABELLA ALTERNATIVE MIGLIORI
            st.subheader("🔄 Alternative Migliori")
            alt = df_viz[
                (df_viz['Anni'].between(anni_target-1.5, anni_target+1.5)) &
                (df_viz['YTM_Grezzo'] > ytm_target + 0.15) &
                (df_viz['Prezzo'].between(60, 115))
            ].sort_values('YTM_Grezzo', ascending=False).head(10)
            
            if not alt.empty:
                alt['Guadagno Extra'] = alt['YTM_Grezzo'] - ytm_target
                st.dataframe(
                    alt[['Descrizione', 'Tipo', 'Prezzo', 'Scadenza', 'YTM_Grezzo', 'Guadagno Extra', 'ISIN']]
                    .rename(columns={'YTM_Grezzo': 'Rendimento Lordo'}).style.format({
                        'Prezzo': '{:.2f}', 'Rendimento Lordo': '{:.2f}%', 'Guadagno Extra': '+{:.2f}%'
                    }), use_container_width=True, hide_index=True
                )
            else: st.success("✅ Il tuo bond è già tra i migliori per questa scadenza!")

        else: st.error("❌ ISIN non trovato.")
            
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

    # --- SCANNER (VERSIONE MASTER: UX GOLD + MATEMATICA REALE XIRR) ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario Pro")
        st.caption("Analisi professionale: Flussi reali, fiscalità italiana e stress test valutario.")
        
        # 1. LEGENDA CATEGORIE (UX PREMIUM - RECUPERATA DAL TUO CODICE)
        st.markdown("### 🧭 Guida Rapida")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("""<div class="cat-card bg-gov"><div class="cat-title">🏛️ GOVERNATIVI</div><div class="cat-desc">Stati Sovrani. Tax 12.5%.</div><div><span class="cat-meta">Rischio: BASSO</span></div></div>""", unsafe_allow_html=True)
        with c2:
            st.markdown("""<div class="cat-card bg-bank"><div class="cat-title">🏦 BANCARI</div><div class="cat-desc">Senior/Sub. Tax 26%.</div><div><span class="cat-meta">Rischio: MEDIO</span></div></div>""", unsafe_allow_html=True)
        with c3:
            st.markdown("""<div class="cat-card bg-corp"><div class="cat-title">🏭 CORPORATE</div><div class="cat-desc">Aziende. Tax 26%.</div><div><span class="cat-meta">Rischio: ALTO</span></div></div>""", unsafe_allow_html=True)
        with c4:
            st.markdown("""<div class="cat-card bg-spec"><div class="cat-title">💎 SPECIALI</div><div class="cat-desc">High Yield/Distressed.</div><div><span class="cat-meta">Rischio: VARIO</span></div></div>""", unsafe_allow_html=True)
        
        st.divider()
        
        # 2. INPUT ISIN
        col_cat, col_isin, col_btn = st.columns([2, 2, 1])
        with col_cat: cat_select = st.selectbox("Filtra Categoria DB", list(MACRO_CATEGORIES.keys()))
        with col_isin: 
            default_isin = st.session_state.selected_isin_from_chart if st.session_state.selected_isin_from_chart else ""
            isin = st.text_input("ISIN", value=default_isin, placeholder="IT... / XS...").strip().upper()
            if st.session_state.selected_isin_from_chart: st.session_state.selected_isin_from_chart = None
            
        with col_btn: 
            st.write(""); st.write("")
            trigger_search = st.button("🔎 Analizza", use_container_width=True)
        
        # 3. LOGICA PRINCIPALE
        if isin and (trigger_search or isin):
            if not valida_isin(isin): st.error("❌ ISIN non valido")
            else:
                filtro_cat = cat_select if not default_isin else "🌐 TUTTE"
                row, info = cerca_db(isin, filtro_cat)
                d = processa_riga(row, info) if row is not None else None
                
                if d:
                    # 1. AUTO-DETECTION INTELLIGENTE
                    feats = detect_bond_features(d['desc'], d.get('isin', ''))
                    valuta_bond = detect_valuta(d['desc'], d.get('isin', ''))
                    
                    # 2. PANNELLO PARAMETRI (Override Manuale)
                    with st.expander("⚙️ Parametri Avanzati & Struttura (Clicca per modificare)", expanded=False):
                        c_p1, c_p2, c_p3 = st.columns(3)
                        new_price = c_p1.number_input("Prezzo Acquisto", value=d['pr'], step=0.1, format="%.2f")
                        # Data scadenza modificabile (FONDAMENTALE per i CALLABLE)
                        new_date = c_p2.date_input("Data Scadenza / Call", value=d['sc'])
                        # Struttura Cumulativa
                        is_cum = c_p3.checkbox("Cedola Cumulativa?", value=feats['is_cumulative'], help="Spunta se paga tutto alla fine")
                        
                        # Override dati
                        bond_calc = d.copy()
                        bond_calc['pr'] = new_price; bond_calc['sc'] = new_date
                        feats['is_cumulative'] = is_cum

                    # 3. CALCOLO RENDIMENTO REALE (XIRR NETTO)
                    df_flussi, spesa_tot, feats = calcola_flussi_reali(bond_calc, bond_calc['pr'], 100.0)
                    rendimento_netto_xirr = xirr(df_flussi)
                    
                    # Calcolo Lordo Semplice
                    try: 
                        anni_res = (bond_calc['sc'] - date.today()).days / 365.25
                        rend_lordo = ((bond_calc['ced'] + (100 - bond_calc['pr']) / anni_res) / bond_calc['pr']) * 100 if anni_res > 0 else 0
                    except: rend_lordo = 0

                    # 4. VISUALIZZAZIONE HEADER & KPI
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    if feats['is_callable']: risk_msg += " | 📞 CALLABLE"
                    if feats['is_cumulative']: risk_msg += " | ⚠️ CUMULATIVE"

                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 20px;">
                        <div style="display:flex; justify-content:space-between;">
                            <div>
                                <div style="color:#b0b3c5; font-size:13px;">{chi}</div>
                                <div style="color:white; font-size:22px; font-weight:bold;">{d['desc']}</div>
                                <div style="color:#00CC96; font-size:13px;">{tipo} <span style="color:#555;">|</span> {risk_msg}</div>
                            </div>
                            <div style="text-align:right;">
                                <h2 style="color:#00CC96; margin:0;">{d['ced']}%</h2>
                                <div style="color:#b0b3c5; font-size:12px;">Cedola</div>
                            </div>
                        </div>
                        <hr style="border-color:rgba(255,255,255,0.1); margin:10px 0;">
                        <div style="display:flex; justify-content:space-between; color:#e0e0e0; font-size:14px;">
                            <div>📅 Scadenza/Call: <b>{bond_calc['sc'].strftime('%d/%m/%Y')}</b></div>
                            <div>🧾 Prezzo: <b>{bond_calc['pr']} {valuta_bond}</b></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Prezzo", f"{bond_calc['pr']} {valuta_bond}")
                    c2.metric("Rend. NETTO (XIRR)", f"{rendimento_netto_xirr:.2f}%", help="Rendimento reale annuo netto calcolato sui flussi di cassa esatti.")
                    c3.metric("Rend. LORDO (YTM)", f"{rend_lordo:.2f}%")
                    c4.metric("Duration", f"{(bond_calc['sc']-date.today()).days/365:.1f}y")

                    if feats['is_callable']:
                        st.warning("⚠️ **Bond CALLABLE:** Il rendimento è calcolato alla data indicata. Se vuoi calcolare lo 'Yield to Call', cambia la data nel pannello 'Parametri Avanzati'.")
                    if feats['is_cumulative']:
                        st.info("ℹ️ **Bond CUMULATIVE:** Interessi spostati tutti a scadenza.")
                    
                    # 5. SIMULATORE BUDGET
                    st.divider(); st.subheader("💰 Simulatore Budget")
                    col_set1, col_set2, col_set3 = st.columns(3)
                    with col_set1: liste_valute = ["EUR", "USD", "GBP", "CHF", "TRY", "BRL"]; valuta_user = st.selectbox("La tua Valuta", liste_valute, index=0)
                    with col_set2: budget_user = st.number_input(f"Budget Totale ({valuta_user})", value=10000.0, step=1000.0)
                    with col_set3: commissioni_input = st.number_input("Commissioni", value=5.0)

                    tasso_spot = get_tasso_cambio_live(valuta_user, valuta_bond)
                    costo_100_in_user = spesa_tot / tasso_spot
                    nominale_teorico = ((budget_user - commissioni_input) / costo_100_in_user) * 100
                    lotto = d['taglio'] if d['taglio'] > 0 else 1000.0
                    nominale_effettivo = int(nominale_teorico / lotto) * lotto
                    if nominale_effettivo == 0: nominale_effettivo = 0
                    
                    if nominale_effettivo > 0:
                        # Ricalcolo flussi su nominale effettivo
                        df_sim, spesa_reale_bond, _ = calcola_flussi_reali(bond_calc, bond_calc['pr'], nominale_effettivo)
                        
                        spesa_reale_user = (spesa_reale_bond / tasso_spot) + commissioni_input
                        
                        # Conversione flussi futuri
                        df_sim['Importo_User'] = df_sim.apply(
                            lambda x: -spesa_reale_user if x['Tipo'] == 'ACQUISTO' else (x['Importo'] / tasso_spot), 
                            axis=1
                        )
                        
                        incassi_futuri_user = df_sim[df_sim['Importo_User'] > 0]['Importo_User'].sum()
                        netto_user = incassi_futuri_user - spesa_reale_user
                        
                        # SCONTRINO
                        st.write("")
                        c_res1, c_res2 = st.columns(2)
                        with c_res1:
                            st.markdown(f"""<div class="receipt-box"><div style="color:#aaa;">Nominale da Comprare</div><div style="font-size:18px; font-weight:bold;">{nominale_effettivo:,.0f} {valuta_bond}</div><div style="font-size:12px; color:#aaa;">Spesa Totale: -{spesa_reale_user:,.2f} {valuta_user}</div></div>""", unsafe_allow_html=True)
                        with c_res2:
                            colore = "#00CC96" if netto_user > 0 else "#FF4B4B"
                            st.markdown(f"""<div class="receipt-box" style="border-left: 4px solid {colore};"><div style="color:#aaa;">Guadagno Netto Previsto</div><div style="font-size:18px; font-weight:bold; color:{colore};">{netto_user:+,.2f} {valuta_user}</div></div>""", unsafe_allow_html=True)
                        
                        # --- 6. GRAFICO RECUPERO CAPITALE (RIPRISTINATO) ---
                        st.subheader("🗓️ Recupero Capitale")
                        df_sim['Cumulativo'] = df_sim['Importo_User'].cumsum()
                        
                        # Calcolo data pareggio (approssimata)
                        df_neg = df_sim[df_sim['Cumulativo'] < 0]
                        df_pos = df_sim[df_sim['Cumulativo'] >= 0]
                        
                        fig = go.Figure()
                        # Linea rossa (sotto zero) e verde (sopra zero)
                        fig.add_trace(go.Scatter(x=df_sim['Data'], y=df_sim['Cumulativo'], mode='lines+markers', line=dict(color='#00CC96', width=3), name='Flusso Netto'))
                        fig.add_hline(y=0, line_color='white', line_dash="dash")
                        
                        fig.update_layout(
                            template="plotly_dark", 
                            height=350, 
                            margin=dict(l=20,r=20,t=30,b=20),
                            title="Andamento Saldo (Break-even)",
                            yaxis_title=f"Saldo ({valuta_user})"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # --- 7. CEDOLARIO DETTAGLIATO (RIPRISTINATO) ---
                        with st.expander("📅 Vedi Cedolario Dettagliato", expanded=True):
                            # Styling condizionale
                            def color_val(val):
                                color = '#00CC96' if val >= 0 else '#FF4B4B'
                                return f'color: {color}; font-weight: bold;'
                                
                            st.dataframe(
                                df_sim[['Data', 'Tipo', 'Importo_User']].style
                                .format({'Importo_User': f'{{:+.2f}} {valuta_user}'})
                                .map(color_val, subset=['Importo_User']),
                                use_container_width=True
                            )
                    else:
                        st.warning(f"⚠️ Budget insufficiente. Minimo {lotto:,.0f} {valuta_bond}.")

    # --- SCREENER (VERSIONE "TRASPARENZA TOTALE" + SEMAFORO RISCHIO) ---
    elif st.session_state.page == "Screener":
        st.title("⚡ Screener & Ranking (Semaforo Rischio)")
        st.caption("Classifica basata sul rendimento puro, con avvisi di rischio chiari.")
        
        # 1. Caricamento
        df = carica_tutto_mercato()
        if df.empty:
            st.warning("⚠️ Database vuoto. Clicca 'Aggiorna Dati'."); st.stop()

        # 2. Arricchimento
        if 'Valuta' not in df.columns:
            df['Valuta'] = df.apply(lambda x: detect_valuta(x['Descrizione'], x['ISIN']), axis=1)

        # =====================================================================
        # 🎛️ CONFIGURAZIONE RICERCA
        # =====================================================================
        
        with st.expander("🛠️ CONFIGURA LA TUA CLASSIFICA", expanded=True):
            with st.form(key="ranking_risk_form"):
                
                # RIGA 1: CHI SEI E DOVE GUARDI
                c1, c2 = st.columns([1, 2])
                with c1:
                    valuta_wallet = st.selectbox("1. Valuta del tuo Conto", ["EUR", "USD"], index=0)
                
                with c2:
                    scope = st.radio(
                        "2. Perimetro di Ricerca",
                        ["🇪🇺 Solo Mercato Locale (Es. Solo EUR)", 
                         "🌍 Tutto il Mondo (Classifica Globale)"],
                        horizontal=True
                    )

                st.divider()

                # RIGA 2: FILTRI (NON CENSURA, SOLO LIMITI)
                f1, f2, f3 = st.columns(3)
                with f1:
                    min_y = st.number_input("Rendimento Minimo (%)", value=3.0, step=0.5)
                with f2:
                    max_anni = st.number_input("Scadenza Massima (Anni)", value=15, step=1)
                with f3:
                    # Filtro sul PREZZO REALE
                    max_pz = st.number_input(f"Prezzo Max ({valuta_wallet})", value=110.0, step=1.0)

                # RIGA 3: Categoria
                cats = ["🌐 TUTTE LE CATEGORIE"] + list(MACRO_CATEGORIES.keys())
                filtro_cat = st.selectbox("Categoria Emittente", cats, index=0)
                
                st.write("") 
                submitted = st.form_submit_button("🚀 MOSTRA CLASSIFICA COMPLETA", type="primary", use_container_width=True)

        # =====================================================================
        # ⚙️ MOTORE DI RANKING (RISCHIO CALCOLATO)
        # =====================================================================
        
        # 1. Filtro Universo
        if "Solo Mercato Locale" in scope:
            df_work = df[df['Valuta'] == valuta_wallet].copy()
        else:
            df_work = df.copy()

        # 2. Filtro Categoria
        if filtro_cat != "🌐 TUTTE LE CATEGORIE":
            if "GOVERNATIVI" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Governativo']
            elif "BANCARI" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Bancario']
            elif "CORPORATE" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Corporate']
            elif "SPECIALI" in filtro_cat: df_work = df_work[df_work['Tipo'].isin(['Altro', 'Speciali'])]

        # 3. Filtri Numerici
        df_work = df_work[
            (df_work['YTM_Grezzo'] >= min_y) &
            (df_work['Anni'] <= max_anni)
        ]

        # 4. CALCOLO: CONVERSIONE + ETICHETTATURA RISCHIO
        if not df_work.empty:
            # Cache tassi
            tassi_live = {}
            for v in df_work['Valuta'].unique():
                if v != valuta_wallet:
                    tassi_live[v] = get_tasso_cambio_live(valuta_wallet, v)

            def engine_risk_ranking(row):
                curr = row['Valuta']
                yield_lordo = row['YTM_Grezzo']
                
                # A. Conversione Prezzo (Per sapere quanto pago)
                if curr == valuta_wallet:
                    pz_reale = row['Prezzo']
                    tasso = 1.0
                else:
                    tasso = tassi_live.get(curr, 1.0)
                    pz_reale = row['Prezzo'] / tasso if tasso > 0 else 0
                
                # B. INTELLIGENZA SUL RISCHIO (Etichette)
                risk_tags = []
                
                # Rischio 1: Valuta
                if curr != valuta_wallet:
                    risk_tags.append("⚠️ Cambio")
                
                # Rischio 2: Rendimento "Sospetto" (Credit Risk)
                if yield_lordo > 15.0:
                    risk_tags.append("☠️ DEFAULT?")
                elif yield_lordo > 9.0:
                    risk_tags.append("🔴 VERY HIGH RISK")
                elif yield_lordo > 5.5:
                    risk_tags.append("🟠 High Yield")
                else:
                    if not risk_tags: risk_tags.append("🟢 Investment Grade") # Se non ha altri rischi
                
                full_status = " + ".join(risk_tags)
                
                return pd.Series([pz_reale, full_status])

            df_work[['Prezzo_Wallet', 'Risk_Analysis']] = df_work.apply(engine_risk_ranking, axis=1)
            
            # 5. Filtro sul Prezzo Convertito
            df_work = df_work[df_work['Prezzo_Wallet'] <= max_pz]
            
            # 6. ORDINAMENTO (Puro Rendimento)
            df_work = df_work.sort_values(by='YTM_Grezzo', ascending=False)

            # =================================================================
            # 🏆 CLASSIFICA (SENZA FILTRI NASCOSTI)
            # =================================================================
            st.divider()
            st.subheader(f"🏆 Classifica per Rendimento ({len(df_work)} Bond)")
            
            # Legenda Dinamica
            st.info("""
            **Guida alla lettura:**
            * **☠️ DEFAULT? / 🔴 VERY HIGH RISK:** Il bond rende tantissimo (>9%) perché l'emittente è in crisi o ristrutturazione (es. Astaldi). Rischio capitale altissimo.
            * **⚠️ Cambio:** Il rendimento è in valuta estera. Se la valuta crolla, il rendimento reale scende.
            * **🟢 Investment Grade:** Rendimenti standard di mercato, emittenti solidi.
            """)

            cols = ['Descrizione', 'Valuta', 'Risk_Analysis', 'Prezzo_Wallet', 'YTM_Grezzo', 'Scadenza', 'ISIN']
            
            # Funzione colore semplice per evitare crash matplotlib
            def color_risk(val):
                if "☠️" in val or "🔴" in val: return 'color: #ff0000; font-weight: bold;' # Rosso Acceso
                if "🟠" in val: return 'color: #ff8c00; font-weight: bold;' # Arancione
                if "⚠️" in val: return 'color: #d4af37; font-weight: bold;' # Oro scuro
                return 'color: #00cc96;' # Verde

            st.dataframe(
                df_work[cols].style
                .format({
                    'Prezzo_Wallet': f'{{:.2f}} {valuta_wallet}', 
                    'YTM_Grezzo': '{:.2f}%',
                    'Scadenza': '{:%d/%m/%Y}'
                })
                .map(color_risk, subset=['Risk_Analysis']), # Applichiamo colori alle etichette
                use_container_width=True,
                height=700,
                column_config={
                    "Descrizione": st.column_config.TextColumn("Nome Titolo", width="medium"),
                    "Prezzo_Wallet": st.column_config.NumberColumn(f"Prezzo ({valuta_wallet})", help="Costo reale per te."),
                    "YTM_Grezzo": st.column_config.NumberColumn("Rendimento Annuo", help="Yield Lordo Nominale."),
                    "Risk_Analysis": st.column_config.TextColumn("⚠️ ANALISI RISCHIO", width="medium"),
                    "Valuta": st.column_config.TextColumn("Divisa", width="small")
                }
            )
            
            # Analisi Singola
            st.write("")
            c1, c2 = st.columns([3, 1])
            with c1:
                isin_pick = st.text_input("Analizza un ISIN specifico", placeholder="Es. XS...").strip().upper()
            with c2:
                st.write("")
                if st.button("Vai allo Scanner ➡️", type="primary"):
                    if isin_pick:
                        st.session_state.selected_isin_from_chart = isin_pick
                        st.session_state.page = "Scanner"
                        st.rerun()
        else:
            st.info("Nessun bond trovato. Prova ad allargare i parametri.")

    elif st.session_state.page == "SmartAnalysis": smart_analysis_ui()
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_portfolio_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()

if st.session_state.logged_in: main_app()
else: login()
