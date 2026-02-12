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
import matplotlib.pyplot as plt
import json
import yfinance as yf 

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA E STILI CSS (ORIGINALE ESTESO)
# ============================================================================

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
# 3. MAPPA FONTI (ESTESA - 29 DATASETS)
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
# 4. FUNZIONI UTILI & DATABASE (COMPLETO)
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
# 5. RISK ENGINE E SCORECARD
# ==============================================================================

# ==============================================================================
# 5. RISK ENGINE E SCORECARD (VERSIONE INDISTRUTTIBILE)
# ==============================================================================

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
def categorizza_rischio(isin, nome, desc):
    """Calcola il livello di rischio (1=Basso, 4=Alto) basandosi su nome e ISIN"""
    try:
        nome = str(nome).upper()
        desc = str(desc).upper()
        isin = str(isin).upper()
        
        # Livello 1: Governativi Ultra Safe (Tripla A o quasi)
        gov_safe = ["GERMANIA", "BUND", "FRANCIA", "OAT", "USA", "TREASURY", "BEI", "EU", "EUROPA"]
        if any(k in nome or k in desc for k in gov_safe): return 1
        
        # Livello 2: Governativi Periferici / Bancari Senior
        gov_mid = ["ITALIA", "BTP", "BOT", "CCT", "SPAGNA", "BONOS"]
        if any(k in nome or k in desc for k in gov_mid): return 2
        if "INTESA" in nome or "UNICREDIT" in nome: return 2
        
        # Livello 3: Corporate IG / XS Generici
        # Se l'ISIN inizia con XS, spesso è Corporate o Sovranazionale, rischio medio-alto rispetto a BTP
        if isin.startswith("XS"): return 3
        
        # Livello 4: High Risk / Subordinate / Emergenti
        if "SUBORDINAT" in nome or "SUB" in desc: return 4
        if "ROMANIA" in nome or "TURCHIA" in nome or "UNGHERIA" in nome: return 4
        
        return 3 # Default (Corporate Generico)
    except:
        return 3
def trova_alternative_migliori(bond_target, df_mercato):
    """
    VERSIONE 'AGGRESSIVA': Cerca alternative con maglie più larghe
    per evitare di dire sempre 'Nessuna alternativa'.
    """
    if df_mercato.empty: return pd.DataFrame()
    
    # Dati Target
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    
    # Calcoliamo YTM Netto del bond che stiamo guardando
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    
    # Identifichiamo il rischio del target (ISIN e Fonte)
    isin_target = bond_target.get('isin', '')
    rischio_target = categorizza_rischio(isin_target, bond_target['fonte'], bond_target['desc'])
    
    alternative = []
    
    for _, row in df_mercato.iterrows():
        # Escludi se stesso
        if row['ISIN'] == isin_target: continue

        # 1. FILTRO DURATA (ALLARGATO a +/- 3 anni)
        # Se il tuo bond scade tra 5 anni, guardiamo bond da 2 a 8 anni.
        if not (anni_target - 3.0 <= row['Anni'] <= anni_target + 3.0): continue
        
        # 2. FILTRO PREZZO (ALZATO a 120)
        # Molti bond buoni hanno cedole alte e costano 115. Non escludiamoli.
        if row['Prezzo'] > 120: continue
        
        # Calcoli Alternativa
        rischio_alt = categorizza_rischio(row['ISIN'], row['Fonte'], row['Desc'])
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        
        # Calcolo Extra Rendimento (Differenza tra alternativa e tuo bond)
        extra = ytm_netto_alt - ytm_netto_target
        
        tipo_switch = ""
        
        # --- LOGICHE DI SELEZIONE (PIÙ GENEROSE) ---
        
        # CASO A: "Gemello Migliore" (Stesso Rischio o Minore, Rendimento Maggiore)
        # Basta che renda anche solo lo 0.01% in più per essere mostrato
        if rischio_alt <= rischio_target and extra > 0.01:
            tipo_switch = "✅ Gemello (+Safe)"
        
        # CASO B: "Boost Rendimento" (Rischio leggermente superiore)
        # Accettiamo rischio +1 (es. da Germania a Italia, o da Italia a Corporate IG) 
        # se il guadagno è almeno +0.30%
        elif rischio_alt == rischio_target + 1 and extra > 0.30:
            tipo_switch = "⚠️ Boost (Rischio+)"
            
        # CASO C: "Rifugio" (Rischio Minore, anche se rende un filo meno)
        # Se posso passare da un Corporate a un BTP perdendo solo lo 0.2%, è un buon affare.
        elif rischio_alt < rischio_target and extra > -0.20:
            tipo_switch = "🛡️ Rifugio (Safe)"

        # CASO D: "Durata Minore" (Stesso rendimento ma scade prima)
        # Se scade 1 anno prima e rende uguale, è meglio.
        elif row['Anni'] < anni_target - 1 and extra > -0.10:
             tipo_switch = "⏳ Scade Prima"

        if tipo_switch:
            # Creiamo il link cliccabile per Google
            link_isin = f"https://www.google.com/search?q={row['ISIN']}+bond"
            
            # Aggiungiamo alla lista
            row_dict = row.to_dict()
            row_dict['Tipologia'] = tipo_switch
            row_dict['YTM_Netto'] = ytm_netto_alt
            row_dict['Extra'] = extra
            row_dict['Link'] = link_isin
            alternative.append(row_dict)
            
    df_alt = pd.DataFrame(alternative)
    
    if not df_alt.empty:
        # Ordiniamo per Extra Rendimento decrescente e prendiamo i primi 10 (non solo 5)
        return df_alt.sort_values('Extra', ascending=False).head(10)
        
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

# --- FUNZIONI UTILI (HELPER) ---

def get_settlement_date():
    """
    Calcola la data di valuta T+2 (Standard Bancario).
    Se oggi è Giovedì -> Lunedì. Se è Venerdì -> Martedì.
    """
    d = date.today()
    added = 0
    while added < 2:
        d += timedelta(days=1)
        if d.weekday() < 5: # 0-4 sono Lun-Ven (Giorni Lavorativi)
            added += 1
    return d

def calcola_rateo(dati, data_valuta):
    """
    Calcola il rateo maturato con metodo ACT/ACT ICMA (Standard SimpleTools).
    """
    try:
        if dati['freq'] == 0: return 0.0
        
        scadenza = dati['sc']
        if data_valuta >= scadenza: return 0.0
        
        # 1. Trova le date esatte del periodo cedolare corrente
        # Torniamo indietro dalla scadenza
        next_c = scadenza
        prev_c = scadenza
        months = 12 // int(dati['freq'])
        
        # "Walk back" fino a trovare la finestra temporale che include la data_valuta
        while next_c > data_valuta:
            prev_c = next_c
            # Sottrazione precisa dei mesi
            y, m = prev_c.year, prev_c.month - months
            while m <= 0: m += 12; y -= 1
            
            # Gestione fine mese (es. 30 Febbraio)
            try: next_c = date(y, m, scadenza.day)
            except: 
                import calendar
                next_c = date(y, m, calendar.monthrange(y, m)[1])
        
        # Riordiniamo: prev_c era il futuro nel loop, next_c il passato
        start_date = next_c
        end_date = prev_c
        
        # 2. Calcolo Giorni (ACT/ACT)
        days_passed = (data_valuta - start_date).days
        days_total = (end_date - start_date).days
        
        if days_total == 0: return 0.0
        
        # 3. Rateo Lordo Percentuale
        cedola_periodo = dati['ced'] / dati['freq']
        rateo = cedola_periodo * (days_passed / days_total)
        
        return max(0.0, rateo)
    except: return 0.0
def genera_flussi_reali(dati, nominale, tax_rate, commissioni, prezzo_mercato):
    """
    Genera i flussi di cassa esatti per il calcolo del rendimento (XIRR).
    Replica la logica di SimpleToolsForInvestors.
    """
    flussi = []
    
    # A. DATA DI REGOLAMENTO (T+2)
    valuta = get_settlement_date()
    
    # B. CALCOLO SPESA INIZIALE (USCITA)
    rateo_pct_lordo = calcola_rateo_esatto(dati, valuta)
    rateo_pct_netto = rateo_pct_lordo * (1 - tax_rate/100) # Tassazione immediata sul rateo
    
    costo_secco = (nominale * prezzo_mercato) / 100
    costo_rateo = (nominale * rateo_pct_netto) / 100
    uscita_totale = costo_secco + costo_rateo + commissioni
    
    flussi.append({
        "Data": valuta,
        "Tipo": "USCITA",
        "Importo": -uscita_totale,
        "Dettagli": f"Acquisto (Valuta {valuta.strftime('%d/%m')})"
    })
    
    # C. CALCOLO CEDOLE FUTURE (ENTRATE)
    tot_cedole = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced']/100) / dati['freq']) * (1 - tax_rate/100)
        
        # Algoritmo date future
        curr = dati['sc']
        months = 12 // int(dati['freq'])
        
        while curr > valuta:
            if curr != dati['sc']: # L'ultima va col rimborso
                flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola"})
                tot_cedole += cedola_netta
            
            # Decremento Mesi
            y, m = curr.year, curr.month - months
            while m <= 0: m += 12; y -= 1
            try: curr = date(y, m, dati['sc'].day)
            except: 
                import calendar
                curr = date(y, m, calendar.monthrange(y, m)[1])
                
    flussi.sort(key=lambda x: x['Data'])
    
    # D. RIMBORSO E CAPITAL GAIN (ENTRATA FINALE)
    rimborso = nominale
    
    # Calcolo Tasse su Capital Gain (Se l'hai pagato meno di 100, paghi tasse sulla differenza)
    # Nota: SimpleTools assume rimborso a 100.
    gain_imponibile = max(0, 100 - prezzo_mercato) 
    tassa_gain = (gain_imponibile / 100 * nominale) * (tax_rate/100)
    
    rimborso_netto = rimborso - tassa_gain
    
    # Ultima cedola
    ultima_ced = (nominale * (dati['ced']/100) / dati['freq']) * (1 - tax_rate/100) if dati['freq'] > 0 else 0
    
    flussi.append({
        "Data": dati['sc'],
        "Tipo": "ENTRATA", 
        "Importo": rimborso_netto + ultima_ced,
        "Dettagli": "Rimborso + Ultima"
    })
    
    tot_cedole += ultima_ced
    tot_incasso = tot_cedole + rimborso_netto
    
    # Ritorniamo tutto per le statistiche
    return pd.DataFrame(flussi), uscita_totale, tot_incasso, costo_rateo, tot_cedole
def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    """
    Genera il cedolario professionale basato su Data Valuta (T+2).
    """
    flussi = []
    
    # 1. DATA VALUTA (Regolamento)
    settlement = get_settlement_date()
    
    # 2. FLUSSO DI ACQUISTO (USCITA)
    # Qui chiamiamo la funzione con il nome CORRETTO 'calcola_rateo'
    rateo_pct = calcola_rateo(dati, settlement) 
    costo_titolo = (nominale * prezzo_acquisto) / 100 
    costo_rateo_netto = (nominale * rateo_pct) / 100 * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    
    flussi.append({
        "Data": settlement, 
        "Tipo": "USCITA", 
        "Importo": -spesa_totale, 
        "Dettagli": f"Acquisto (Valuta {settlement.strftime('%d/%m')})"
    })
    
    # 3. FLUSSI CEDOLARI (ENTRATE)
    totale_cedole_nette = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        
        curr = dati['sc']
        while curr > settlement:
            if curr != dati['sc']: 
                flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola"})
                totale_cedole_nette += cedola_netta
            
            mesi_step = 12 // int(dati['freq'])
            new_year = curr.year
            new_month = curr.month - mesi_step
            while new_month <= 0:
                new_month += 12
                new_year -= 1
            try:
                curr = date(new_year, new_month, dati['sc'].day)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(new_year, new_month)[1]
                curr = date(new_year, new_month, last_day)

    flussi.sort(key=lambda x: x['Data'])
    
    # 4. RIMBORSO
    rimborso_lordo = nominale
    gain_prezzo = max(0, 100 - prezzo_acquisto)
    plusvalenza_lorda = (gain_prezzo / 100) * nominale
    tassa_gain = plusvalenza_lorda * (tax_rate / 100)
    rimborso_netto = rimborso_lordo - tassa_gain
    
    ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    
    flussi.append({
        "Data": dati['sc'], 
        "Tipo": "ENTRATA", 
        "Importo": rimborso_netto + ultima_ced, 
        "Dettagli": "Rimborso + Ultima Cedola"
    })
    
    incasso_totale = totale_cedole_nette + rimborso_netto + ultima_ced
    totale_cedole_nette += ultima_ced

    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza_lorda
# 🆕 GESTIONE VALUTE LIVE (NUOVO SISTEMA)
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
# 🆕 FUNZIONALITÀ RETAIL AVANZATE (FULL CODE)
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
# 🧠 SMART ANALYSIS UI (FUNZIONE DI PAGINA COMPLETA)
# ==============================================================================
def smart_analysis_ui():
    st.title("🧠 Smart Analysis & Fair Value")
    st.caption("Mappa del mercato: visualizza il posizionamento e trova alternative migliori.")
    
    # 1. Caricamento Dati
    with st.spinner("Analisi dell'intero mercato in corso..."):
        df_market = carica_dati_mercato()
    
    if df_market.empty:
        st.warning("⚠️ Database vuoto. Clicca su 'Aggiorna Database' nella barra laterale.")
        return

    # 2. Arricchimento Dati per il Grafico (Categorizzazione al volo)
    def get_tipo_rapido(row):
        s = (str(row['Fonte']) + " " + str(row['Desc'])).upper()
        if any(x in s for x in ['BTP', 'BOT', 'ITALIA', 'GERMANIA', 'BUND', 'USA', 'TREASURY', 'SPAGNA']): return "Governativo"
        if any(x in s for x in ['BANCA', 'INTESA', 'UNICREDIT', 'BANCARI', 'SUB', 'ASSICURAZIONI']): return "Bancario"
        if any(x in s for x in ['CORP', 'ENI', 'ENEL', 'STELLANTIS', 'INDUSTRIA', 'AUTO']): return "Corporate"
        return "Altro / High Yield"
    
    # Applica la categorizzazione
    df_market['Tipo'] = df_market.apply(get_tipo_rapido, axis=1)

    # 3. Gestione Input ISIN (Automatico dal grafico o Manuale)
    if st.session_state.selected_isin_from_chart:
        default_isin = st.session_state.selected_isin_from_chart
        st.session_state.selected_isin_from_chart = None # Reset dopo l'uso per non bloccare l'input
    else:
        default_isin = ""

    col_search, col_cat = st.columns([1, 3])
    with col_search:
        isin_smart = st.text_input("Analizza ISIN", value=default_isin, placeholder="IT...").strip().upper()
    with col_cat:
        # Filtro visivo per il grafico
        cat_options = [""] + sorted(list(set(df_market['Tipo'].unique())))
        cat_filter = st.selectbox("Filtra Grafico per Categoria", cat_options, format_func=lambda x: "Mostra Tutto" if x == "" else x)

    # 4. Elaborazione e Visualizzazione
    if isin_smart and valida_isin(isin_smart):
        # Cerca il bond specifico
        row, info = cerca_db(isin_smart, None) # Cerca ovunque
        d_smart = processa_riga(row, info) if row is not None else None
        
        if d_smart:
            d_smart['isin'] = isin_smart
            # Calcoli live per il bond selezionato
            ytm_s = calcola_rendimento_grezzo(d_smart['pr'], d_smart['ced'], d_smart['sc'])
            dur_s = (d_smart['sc'] - date.today()).days / 365.25
            tipo_s = get_tipo_rapido({'Fonte': d_smart['fonte'], 'Desc': d_smart['desc']})
            
            # --- SEZIONE A: GRAFICO "FAIR VALUE" (PALLINI VUOTI) ---
            st.divider()
            st.subheader("📊 Mappa del Mercato")
            st.caption(f"Confronto con bond scadenza +/- 3 anni. Tu sei la stella rossa.")
            
            # Filtri Zoom Automatici (Focus sulla durata del bond)
            mask_zoom = (df_market['Anni'] >= dur_s - 3) & (df_market['Anni'] <= dur_s + 3) & (df_market['YTM_Grezzo'] < ytm_s + 8)
            if cat_filter: mask_zoom = mask_zoom & (df_market['Tipo'] == cat_filter)
            
            df_zoom = df_market[mask_zoom].copy()
            
            # Creazione Grafico Interattivo
            fig = px.scatter(
                df_zoom, 
                x='Anni', 
                y='YTM_Grezzo', 
                color='Tipo', # Colora automaticamente in base alla categoria
                # Configurazione Hover (Cosa vedi passando il mouse)
                hover_data={
                    'ISIN': True, 
                    'Desc': True, 
                    'Prezzo': ':.2f', 
                    'YTM_Grezzo': ':.2f', 
                    'Tipo': True,
                    'Anni': False # Nascondi perché è già sull'asse X
                },
                labels={'Anni': 'Durata (Anni)', 'YTM_Grezzo': 'Rendimento Lordo (%)', 'Tipo': 'Categoria'},
                # Mappa colori professionale
                color_discrete_map={
                    "Governativo": "#00CC96", # Verde acqua
                    "Bancario": "#FFA15A",    # Arancio
                    "Corporate": "#636EFA",   # Blu viola
                    "Altro / High Yield": "#EF553B" # Rosso
                }
            )
            
            # APPLICA STILE "CERCHI VUOTI" (RICHIESTA SPECIFICA)
            fig.update_traces(
                marker=dict(
                    symbol='circle-open', # Questo rende il cerchio vuoto
                    size=9,               # Grandezza leggibile
                    line=dict(width=2)    # Spessore del bordo colorato
                )
            )
            
            # Aggiungi il TUO bond (Stella Rossa Piena per distinguerlo)
            fig.add_trace(go.Scatter(
                x=[dur_s], y=[ytm_s],
                mode='markers+text',
                name='IL TUO BOND',
                text=['📍 TU'],
                textposition="top center",
                marker=dict(color='red', size=18, symbol='star', line=dict(width=1, color='white')),
                hoverinfo='text',
                hovertext=f"TUO BOND<br>{d_smart['desc']}<br>YTM: {ytm_s:.2f}%"
            ))
            
            fig.update_layout(
                template="plotly_dark", 
                height=500, 
                legend=dict(orientation="h", y=1.1), # Legenda orizzontale in alto
                hovermode="closest",
                margin=dict(l=20, r=20, t=20, b=20)
            )
            
            # Rendi il grafico cliccabile
            selected_point = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
            
            # Gestione click sul grafico
            if selected_point and len(selected_point['selection']['points']) > 0:
                try:
                    point = selected_point['selection']['points'][0]
                    # Plotly mette i customdata nello stesso ordine di hover_data
                    if 'customdata' in point:
                        # L'ISIN è il primo elemento (indice 0) nei customdata definiti sopra
                        clicked_isin = point['customdata'][0] 
                        st.session_state.selected_isin_from_chart = clicked_isin
                        st.rerun() # Ricarica la pagina analizzando il nuovo bond
                except: pass

            # --- SEZIONE B: SMART SWITCH (TABELLA) ---
            st.divider()
            st.subheader("🔄 Smart Switch (Alternative)")
            st.caption(f"Confronto con bond simili a **{d_smart['desc']}** ({tipo_s})")
            
            alternative = trova_alternative_migliori(d_smart, df_market)
            
            if not alternative.empty:
                st.dataframe(
                    alternative[['Tipologia', 'ISIN', 'Desc', 'Prezzo', 'YTM_Netto', 'Extra', 'Link']],
                    column_config={
                        "Link": st.column_config.LinkColumn("Scheda", display_text="🔗 Apri"),
                        "YTM_Netto": st.column_config.NumberColumn("YTM Netto", format="%.2f%%"),
                        "Extra": st.column_config.NumberColumn("Delta", format="+%.2f%%"),
                        "Prezzo": st.column_config.NumberColumn("Prezzo", format="%.2f€"),
                        "Tipologia": st.column_config.TextColumn("Analisi", width="medium"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("🏆 Nessuna alternativa nettamente migliore trovata con questi parametri.")
                
        else:
            st.error("ISIN non trovato nel database.")
    else:
        st.info("Inserisci un ISIN per iniziare l'analisi.")
        
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

    # --- ROUTING PAGINE ---
# --- SCANNER (CODICE COMPLETO E CORRETTO) ---
# --- SCANNER (GRAFICA ORIGINALE + VALUTA LIVE + CEDOLARIO COLORATO) ---
# --- SCANNER (GRAFICA PREMIUM + VALUTA LIVE + INFOBOX) ---
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
                    # --- MOTORE MATEMATICO (REPLICA SIMPLE TOOLS) ---
                    tax_rate = determina_tasse(d['fonte'], d['desc'])
                    valuta_bond = detect_valuta(d['desc'], d['isin'])
                    
                    # 1. Calcoli Preliminari
                    settlement = get_settlement_date()
                    rateo_per_visualizzazione = calcola_rateo_esatto(d, settlement)
                    
                    # 2. Calcolo Rendimento NETTO (XIRR) su Base 100
                    # Usiamo base 100 e 0 commissioni per trovare il rendimento puro del titolo
                    df_yield, _, _, _, _ = genera_flussi_reali(d, 100.0, tax_rate, 0, d['pr'])
                    
                    def xirr_calc(flow_df):
                        try:
                            dates = flow_df['Data'].tolist()
                            amounts = flow_df['Importo'].tolist()
                            if not amounts or amounts[0] >= 0: return 0.0
                            def xnpv(r, amts, dts):
                                d0 = dts[0] # Data T+2
                                return sum([a / ((1 + r)**((dt - d0).days / 365.0)) for a, dt in zip(amts, dts)])
                            return newton(lambda r: xnpv(r, amounts, dates), 0.05) * 100
                        except: return 0.0

                    rendimento_netto = xirr_calc(df_yield)
                    
                    # 3. Metriche classiche (solo per visualizzazione)
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    
                    # --- FINE CALCOLI, INIZIO GRAFICA ---
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    
                
                    
                    # Analisi Quality Score
                    qual = analizza_bond_quality_dettagliata(d, risk, tax_rate, st.session_state.patrimonio)
                    qual['ytm_netto'] = rendimento_netto # Sovrascriviamo con il calcolo preciso XIRR

                    # --- B. INTERFACCIA VISUALE ---
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    
                    # ... (DA QUI IN POI IL CODICE RESTA UGUALE: st.markdown, Header, etc.)
                    
                    # HEADER BOND (Box Gradiente - UX Gold)
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
                            <div>🧾 Prezzo: <b style="color:white;">{d['pr']} {valuta_bond}</b></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # DATI CHIAVE (Con Info Box Help - UX Gold)
                    st.subheader("📊 Dati Chiave")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    simbolo = "€" if valuta_bond == "EUR" else valuta_bond
                    
                    c1.metric("Prezzo", f"{d['pr']} {simbolo}", help="Prezzo di mercato attuale.")
                    c2.metric("Rend. NETTO", f"{rendimento_netto:.2f}%", help="Rendimento reale annuo calcolato sui flussi netti (XIRR).")
                    c3.metric("Rend. LORDO", f"{risk['ytm']:.2f}%", help="Yield to Maturity Lordo.")
                    c4.metric("Cedola", f"{d['ced']}%", help="Interesse periodico pagato.")
                    c5.metric("Valuta", valuta_bond, help="Valuta di denominazione.")
                    c6.metric("Duration", f"{risk['mod_dur']:.2f}", help="Sensibilità ai tassi.")

                    st.divider()
                    
                    # === 💰 SIMULATORE & STRESS TEST (UX Gold + Matematica Fixata) ===
                    # === 💰 SIMULATORE & STRESS TEST (Math Fix + UX Gold) ===
                    # === 💰 SIMULATORE & STRESS TEST ===
                    st.subheader("💰 Simulatore & Stress Test")
                    
                    col_set1, col_set2, col_set3 = st.columns(3)
                    with col_set1: 
                        liste_valute = ["EUR", "USD", "GBP", "CHF", "TRY", "BRL", "RON", "JPY"]
                        valuta_user = st.selectbox("La tua Valuta", liste_valute, index=0)
                    with col_set2: 
                        budget_user = st.number_input(f"Budget Totale ({valuta_user})", value=10000.0, step=1000.0, help="Quanto vuoi spendere tutto incluso")
                    with col_set3: 
                        commissioni_input = st.number_input("Commissioni", value=5.0, help="Costi fissi dell'operazione")

                    # Recupero Tasso Cambio
                    tasso_spot = get_tasso_cambio_live(valuta_user, valuta_bond)
                    st.caption(f"📡 Tasso LIVE: 1 {valuta_user} = {tasso_spot:.4f} {valuta_bond}")
                    
                    scenario_fx = 0
                    if valuta_user != valuta_bond:
                        c_ux1, c_ux2 = st.columns([2, 1])
                        with c_ux1:
                            risk_txt = "MEDIO"
                            sugg = "-10% o -20%"
                            if valuta_bond in ["TRY", "ARS", "RUB"]: risk_txt = "ALTISSIMO"; sugg = "-40%"
                            elif valuta_bond in ["BRL", "ZAR", "MXN"]: risk_txt = "ALTO"; sugg = "-25%"
                            st.info(f"**Rischio {valuta_bond}: {risk_txt}**")
                        with c_ux2:
                            scenario_fx = st.slider(f"📉 Variazione {valuta_bond}", -50, 50, 0, format="%d%%")

                    # --- CALCOLI ---
                    rateo_unitario = calcola_rateo_esatto(d, get_settlement_date())
                    prezzo_telquel = d['pr'] + rateo_unitario 
                    costo_100_user = (prezzo_telquel / tasso_spot)
                    
                    nominale_teorico = ((budget_user - commissioni_input) / costo_100_user) * 100
                    lotto = d['taglio'] if d['taglio'] > 0 else 1000.0
                    nominale_effettivo = int(nominale_teorico / lotto) * lotto
                    
                    force_calc = False
                    if nominale_effettivo == 0 and budget_user > 0: 
                        nominale_effettivo = lotto; force_calc = True

                    if nominale_effettivo > 0:
                        if force_calc: st.warning(f"⚠️ Budget insufficiente. Calcolo su 1 lotto ({lotto:,.0f} {valuta_bond}).")

                        # Generazione Flussi
                        df_flussi, spesa_loc, incasso_loc, rateo_loc, tot_ced_loc, _ = genera_flussi_dettagliati(
                            d, nominale_effettivo, tax_rate, 0, d['pr']
                        )
                        
                        # Conversioni
                        rate_rientro = tasso_spot * (1 - (scenario_fx/100)) if valuta_user != valuta_bond else 1.0
                        if rate_rientro < 0.001: rate_rientro = 0.001
                        
                        costo_titolo_user = ((nominale_effettivo * d['pr'] / 100) / tasso_spot)
                        rateo_user = (rateo_loc / tasso_spot)
                        spesa_reale_user = costo_titolo_user + rateo_user + commissioni_input
                        
                        df_flussi['Importo_User'] = df_flussi.apply(
                            lambda x: (x['Importo'] / tasso_spot) if x['Tipo'] == 'USCITA' else (x['Importo'] / rate_rientro), axis=1
                        )
                        
                        incasso_reale_user = df_flussi[df_flussi['Tipo'] != 'USCITA']['Importo_User'].sum()
                        cedole_tot_user = tot_ced_loc / rate_rientro
                        rimborso_visual = incasso_reale_user - cedole_tot_user
                        
                        guadagno_netto_user = incasso_reale_user - spesa_reale_user
                        roi_pct = (guadagno_netto_user / spesa_reale_user) * 100
                        
                        # Annualizzato
                        giorni_residui = (d['sc'] - date.today()).days
                        anni_residui = max(giorni_residui / 365.25, 0.1)
                        roi_annuo = ((incasso_reale_user / spesa_reale_user) ** (1 / anni_residui) - 1) * 100 if spesa_reale_user > 0 else -100

                        # SCONTRINO
                        st.write("")
                        st.markdown(f"### 🧾 Analisi Flussi (Nominale: {nominale_effettivo:,.0f} {valuta_bond})")
                        col_usc, col_entr = st.columns(2)
                        
                        with col_usc:
                            st.markdown(f"""
                            <div class="receipt-box" style="border-left: 4px solid #FF4B4B; background-color: rgba(255, 75, 75, 0.05); padding: 15px; border-radius: 8px;">
                                <div style="font-weight:bold; color:#FF4B4B; margin-bottom:10px;">📉 USCITE (Oggi)</div>
                                <div class="receipt-row" style="color:#aaa;">Prezzo: {d['pr']:.2f} | Nominale: {nominale_effettivo:,.0f}</div>
                                <div class="receipt-row"><span>Costo Titoli:</span><span>{costo_titolo_user:,.2f} {valuta_user}</span></div>
                                <div class="receipt-row"><span>Rateo Interessi:</span><span>{rateo_user:,.2f} {valuta_user}</span></div>
                                <div class="receipt-row"><span>Commissioni:</span><span>{commissioni_input:,.2f} {valuta_user}</span></div>
                                <hr style="margin:10px 0; border-color:#444;">
                                <div class="receipt-total" style="color:#FF4B4B;">TOTALE: -{spesa_reale_user:,.2f} {valuta_user}</div>
                            </div>""", unsafe_allow_html=True)
                        
                        with col_entr:
                            col_res = "#00CC96" if guadagno_netto_user > 0 else "#FF4B4B"
                            lbl_tasso = f"{rate_rientro:.2f}" if valuta_user != valuta_bond else "Inv."
                            st.markdown(f"""
                            <div class="receipt-box" style="border-left: 4px solid {col_res}; background-color: rgba(0, 204, 150, 0.05); padding: 15px; border-radius: 8px;">
                                <div style="font-weight:bold; color:{col_res}; margin-bottom:10px;">📈 ENTRATE (Futuro - Tasso {lbl_tasso})</div>
                                <div class="receipt-row"><span>Cedole Nette:</span><span>+{cedole_tot_user:,.2f} {valuta_user}</span></div>
                                <div class="receipt-row"><span>Rimborso Netto:</span><span>+{rimborso_visual:,.2f} {valuta_user}</span></div>
                                <div class="receipt-row" style="color:#888;"><span>(Effetto Cambio: {scenario_fx}%)</span></div>
                                <hr style="margin:10px 0; border-color:#444;">
                                <div class="receipt-total" style="color:{col_res};">TOTALE: +{incasso_reale_user:,.2f} {valuta_user}</div>
                            </div>""", unsafe_allow_html=True)

                        st.divider()
                        if guadagno_netto_user > 0: st.success(f"✅ **PROFITTO:** +{guadagno_netto_user:,.2f} {valuta_user} (Tot: +{roi_pct:.2f}% | **Annuo: +{roi_annuo:.2f}%**)")
                        else: st.error(f"❌ **PERDITA:** {guadagno_netto_user:,.2f} {valuta_user} (Tot: {roi_pct:.2f}% | **Annuo: {roi_annuo:.2f}%**)")

                       # --- GRAFICO RECUPERO CAPITALE (LOGICA PERFETTA) ---
                        # --- GRAFICO BREAK-EVEN (INTERPOLAZIONE ESATTA) ---
                        st.subheader("🗓️ Recupero Capitale (Break-Even)")
                        df_flussi['Cumulativo'] = df_flussi['Importo_User'].cumsum()
                        colors = ['#FF4B4B' if val < 0 else '#00CC96' for val in df_flussi['Cumulativo']]
                        
                        # CALCOLO INTERPOLATO DEL PUNTO ESATTO DI PAREGGIO
                        be_date_exact = None
                        
                        # Separiamo i punti negativi da quelli positivi
                        df_neg = df_flussi[df_flussi['Cumulativo'] < 0]
                        df_pos = df_flussi[df_flussi['Cumulativo'] >= 0]
                        
                        # Se abbiamo un passaggio da negativo a positivo (Break-Even esiste)
                        if not df_neg.empty and not df_pos.empty:
                            last_neg = df_neg.iloc[-1]  # Ultimo punto rosso
                            first_pos = df_pos.iloc[0]  # Primo punto verde
                            
                            # Coordinate per l'interpolazione
                            y1 = last_neg['Cumulativo']
                            y2 = first_pos['Cumulativo']
                            x1 = last_neg['Data'].toordinal() # Convertiamo date in numeri
                            x2 = first_pos['Data'].toordinal()
                            
                            # Formula della retta per trovare X quando Y=0
                            # x = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
                            if y2 != y1:
                                x_zero = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
                                be_date_exact = date.fromordinal(int(x_zero))
                            else:
                                be_date_exact = first_pos['Data']

                        fig = go.Figure()
                        
                        # 1. Linea Guida (Percorso)
                        fig.add_trace(go.Scatter(
                            x=df_flussi['Data'], y=df_flussi['Cumulativo'], 
                            mode='lines', 
                            line=dict(color='#888', width=1, dash='dot'), 
                            name='Trend'
                        ))
                        
                        # 2. Marker (Pallini Vuoti)
                        fig.add_trace(go.Scatter(
                            x=df_flussi['Data'], y=df_flussi['Cumulativo'], 
                            mode='markers', 
                            marker=dict(symbol='circle-open', size=9, color=colors, line=dict(width=2.5)),
                            text=df_flussi['Dettagli'], 
                            hovertemplate="<b>%{text}</b><br>Saldo: %{y:,.2f}<extra></extra>"
                        ))
                        
                        # 3. Stella nel punto ESATTO di intersezione (Asse X)
                        if be_date_exact:
                            fig.add_trace(go.Scatter(
                                x=[be_date_exact], y=[0],
                                mode='markers', # SOLO Marker, niente testo sovrapposto
                                name='Break-Even',
                                marker=dict(
                                    symbol='star', 
                                    size=18, 
                                    color='#FFD700', # Oro
                                    line=dict(width=1, color='white')
                                ),
                                hoverinfo='text',
                                hovertext=f"★ BREAK-EVEN POINT<br>Data stimata: {be_date_exact.strftime('%d/%m/%Y')}"
                            ))

                        # Asse X (Linea Bianca)
                        fig.add_hline(y=0, line_color='white', line_width=1, layer="below")
                        
                        fig.update_layout(
                            template="plotly_dark", 
                            height=350, 
                            showlegend=False, 
                            margin=dict(l=20,r=20,t=30,b=20), 
                            yaxis_title="Saldo Cumulativo"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # CEDOLARIO (SEMPRE VISIBILE, SENZA EXPANDER)
                        st.subheader("📅 Cedolario Dettagliato")
                        def style_cedola(v): return f'color: {"#00CC96" if v >= 0 else "#FF4B4B"}; font-weight: bold;'
                        st.dataframe(
                            df_flussi[['Data', 'Tipo', 'Importo', 'Importo_User', 'Dettagli']]
                            .style.format({'Importo': f'{{:+,.2f}} {valuta_bond}', 'Importo_User': f'{{:+,.2f}} {valuta_user}'})
                            .map(style_cedola, subset=['Importo', 'Importo_User']),
                            use_container_width=True
                        )

                    else: st.warning(f"⚠️ Budget insufficiente. Il taglio minimo è {lotto:,.0f} {valuta_bond}.")
                else: st.error("❌ Bond non trovato nel database.")
    # --- SCREENER AVANZATO (FILTRI VALUTA + CONVERSIONE PREZZI) ---
# --- SCREENER (LOGICA DIRETTA: DAL TUO PORTAFOGLIO AL MERCATO) ---
    elif st.session_state.page == "Screener":
        st.title("⚡ Screener & Ranking")
        st.caption("Trova i migliori rendimenti in base alla tua valuta di partenza.")
        
        # 1. Caricamento Dati
        df = carica_tutto_mercato()
        if df.empty:
            st.warning("⚠️ Database vuoto. Clicca 'Aggiorna Dati'.")
            st.stop()

        # 2. Arricchimento
        if 'Valuta' not in df.columns:
            df['Valuta'] = df.apply(lambda x: detect_valuta(x['Descrizione'], x['ISIN']), axis=1)

        # =====================================================================
        # 🎛️ CONFIGURAZIONE (DENTRO IL FORM PER NON RICARICARE SEMPRE)
        # =====================================================================
        
        with st.expander("🛠️ IMPOSTA LA RICERCA", expanded=True):
            
            with st.form(key="ranking_form"):
                
                # --- SEZIONE 1: CHI SEI E COSA VUOI ---
                st.markdown("##### 1️⃣ Il Tuo Profilo")
                c_val, c_scope = st.columns(2)
                
                with c_val:
                    # TUA VALUTA
                    valuta_wallet = st.selectbox("La valuta del tuo portafoglio", ["EUR", "USD"], index=0)
                
                with c_scope:
                    # PERIMETRO (La modifica richiesta)
                    perimetro = st.radio(
                        "Quali obbligazioni vuoi vedere in classifica?",
                        [f"🔒 Solo titoli in {valuta_wallet} (Nessun rischio cambio)", 
                         "🌍 Tutto il Mercato Globale (Max rendimento, ma rischio cambio)"],
                        index=0
                    )

                st.divider()

                # --- SEZIONE 2: I PARAMETRI DEL BOND ---
                st.markdown("##### 2️⃣ I Parametri del Bond")
                f1, f2, f3 = st.columns(3)
                
                with f1:
                    min_y = st.number_input("Rendimento Minimo (%)", value=3.0, step=0.5)
                with f2:
                    max_anni = st.number_input("Scadenza Massima (Anni)", value=10, step=1)
                with f3:
                    # Questo filtro agisce sul prezzo CONVERTITO nella tua valuta
                    max_pz = st.number_input(f"Prezzo Massimo ({valuta_wallet})", value=105.0, step=1.0)

                # Categoria
                cats = ["🌐 TUTTE LE CATEGORIE"] + list(MACRO_CATEGORIES.keys())
                filtro_cat = st.selectbox("Filtra Categoria Emittente", cats, index=0)
                
                st.write("") 
                
                # BOTTONE
                submitted = st.form_submit_button("🚀 GENERA CLASSIFICA", type="primary", use_container_width=True)

        # =====================================================================
        # ⚙️ MOTORE DI RANKING (SCATTA SOLO COL BOTTONE O AL PRIMO AVVIO)
        # =====================================================================
        
        # Logica di filtraggio iniziale (Valuta)
        if "Solo titoli" in perimetro:
            # Mostro solo la roba sicura nella mia valuta
            df_work = df[df['Valuta'] == valuta_wallet].copy()
        else:
            # Mostro tutto
            df_work = df.copy()

        # Logica Categoria
        if filtro_cat != "🌐 TUTTE LE CATEGORIE":
            if "GOVERNATIVI" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Governativo']
            elif "BANCARI" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Bancario']
            elif "CORPORATE" in filtro_cat: df_work = df_work[df_work['Tipo'] == 'Corporate']
            elif "SPECIALI" in filtro_cat: df_work = df_work[df_work['Tipo'].isin(['Altro', 'Speciali'])]

        # Filtri Preliminari
        df_work = df_work[
            (df_work['YTM_Grezzo'] >= min_y) &
            (df_work['Anni'] <= max_anni)
        ]

        # ⚙️ CALCOLO CONVERSIONI PER IL RANKING
        if not df_work.empty:
            # Recupero tassi live solo per le valute diverse dalla mia
            tassi_live = {}
            unique_currencies = df_work['Valuta'].unique()
            for v in unique_currencies:
                if v != valuta_wallet:
                    tassi_live[v] = get_tasso_cambio_live(valuta_wallet, v)

            def engine_ranking(row):
                curr_bond = row['Valuta']
                
                # 1. PREZZO REALE (Quanto mi esce dal conto oggi)
                if curr_bond == valuta_wallet:
                    pz_reale = row['Prezzo']
                    tasso = 1.0
                else:
                    tasso = tassi_live.get(curr_bond, 1.0)
                    pz_reale = row['Prezzo'] / tasso if tasso > 0 else 0
                
                # 2. STATUS RISCHIO
                risk_label = "✅ Sicuro" if curr_bond == valuta_wallet else "⚠️ Rischio FX"
                
                return pd.Series([pz_reale, risk_label])

            df_work[['Prezzo_Wallet', 'Risk_Status']] = df_work.apply(engine_ranking, axis=1)
            
            # FILTRO SUL PREZZO CONVERTITO (Ora che so quanto costa in Euro)
            df_work = df_work[df_work['Prezzo_Wallet'] <= max_pz]
            
            # ORDINAMENTO
            # Ordiniamo per rendimento decrescente
            df_work = df_work.sort_values(by='YTM_Grezzo', ascending=False)

            # =================================================================
            # 🏆 VISUALIZZAZIONE CLASSIFICA
            # =================================================================
            st.divider()
            
            if "Solo titoli" in perimetro:
                st.subheader(f"🏆 Top {len(df_work)} Bond in {valuta_wallet}")
            else:
                st.subheader(f"🌍 Classifica Globale ({len(df_work)} Bond)")
                st.info(f"💡 **Nota:** I prezzi sono stati convertiti in **{valuta_wallet}**. Il rendimento visualizzato è quello offerto dal bond nella sua valuta originale.")

            cols = ['Descrizione', 'Valuta', 'Prezzo_Wallet', 'YTM_Grezzo', 'Scadenza', 'Risk_Status', 'ISIN']
            
            st.dataframe(
                df_work[cols].style
                .format({
                    'Prezzo_Wallet': f'{{:.2f}} {valuta_wallet}', 
                    'YTM_Grezzo': '{:.2f}%',
                    'Scadenza': '{:%d/%m/%Y}'
                })
                .background_gradient(subset=['YTM_Grezzo'], cmap='Greens')
                .map(lambda x: 'color: #ff4b4b; font-weight: bold;' if 'FX' in x else 'color: #00CC96;', subset=['Risk_Status']),
                use_container_width=True,
                height=600,
                column_config={
                    "Descrizione": st.column_config.TextColumn("Nome Bond", width="medium"),
                    "Prezzo_Wallet": st.column_config.NumberColumn(
                        f"Prezzo ({valuta_wallet})", 
                        help=f"Costo reale addebitato sul tuo conto {valuta_wallet}."
                    ),
                    "YTM_Grezzo": st.column_config.NumberColumn(
                        "Rendimento Annuo",
                        help="Rendimento nominale annuo."
                    ),
                    "Risk_Status": st.column_config.TextColumn("Rischio", width="small"),
                    "Valuta": st.column_config.TextColumn("Divisa", width="small")
                }
            )
            
            # AZIONE
            st.write("")
            c1, c2 = st.columns([3, 1])
            with c1:
                isin_pick = st.text_input("Inserisci ISIN per simulazione dettagliata", placeholder="Es. IT000...").strip().upper()
            with c2:
                st.write("")
                if st.button("Vai allo Scanner ➡️", type="primary"):
                    if isin_pick:
                        st.session_state.selected_isin_from_chart = isin_pick
                        st.session_state.page = "Scanner"
                        st.rerun()
        else:
            st.info("Nessun bond trovato. Prova ad allargare i filtri e premi 'GENERA CLASSIFICA'.")
    elif st.session_state.page == "SmartAnalysis":smart_analysis_ui()        
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_portfolio_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()

if st.session_state.logged_in: main_app()
else: login()
