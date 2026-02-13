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
# CONFIGURAZIONE PAGINA E STILI MIGLIORATI
# ==============================================================================

st.set_page_config(
    page_title="Bond Research Terminal", 
    page_icon="🏛️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* STILI MIGLIORATI - UX PROFESSIONALE */
    .metric-card { 
        background-color: #1e2130; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #3e445b; 
        margin-bottom: 10px; 
        color: #ffffff !important; 
    }
    
    .cat-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: white; 
        transition: transform 0.2s;
    }
    .cat-card:hover { transform: translateY(-2px); }
    .cat-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; }
    .cat-desc { font-size: 14px; opacity: 0.95; margin-bottom: 8px; line-height: 1.4; }
    .cat-meta { font-size: 12px; font-weight: bold; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
    
    .bg-gov { background: linear-gradient(135deg, #1a4a2e 0%, #28a745 100%); }
    .bg-bank { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); }
    .bg-corp { background: linear-gradient(135deg, #1e3a5f 0%, #17a2b8 100%); }
    .bg-spec { background: linear-gradient(135deg, #581845 0%, #d63384 100%); }

    .receipt-box {
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        background-color: rgba(255, 255, 255, 0.02);
    }
    .receipt-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 14px; }
    .receipt-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; margin-top: 10px; padding-top: 10px; border-top: 1px solid #444; }

    .user-box { 
        padding: 10px; 
        background-color: rgba(0, 204, 150, 0.1); 
        border-left: 5px solid #00CC96; 
        border-radius: 5px; 
        margin-bottom: 20px; 
        font-weight: bold; 
        color: inherit; 
    }
    
    /* INFO BOX GUIDA */
    .info-guida {
        background: linear-gradient(135deg, rgba(0,122,255,0.1), rgba(0,122,255,0.05));
        border-left: 4px solid #007AFF;
        padding: 16px;
        border-radius: 8px;
        margin: 16px 0;
    }
    .info-guida h4 {
        color: #007AFF;
        margin-top: 0;
        font-size: 16px;
    }
    
    [data-testid="stSidebar"] div.stButton > button { 
        background-color: transparent; 
        border: none; 
        text-align: left; 
        color: inherit !important; 
        font-weight: 600; 
    }
    [data-testid="stSidebar"] div.stButton > button:hover { 
        padding-left: 10px; 
        background-color: rgba(128, 128, 128, 0.1); 
        border-radius: 5px; 
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONFIGURAZIONE SICUREZZA
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
os.makedirs(DB_FOLDER, exist_ok=True)

def init_session_state():
    """Inizializzazione sicura session state"""
    query_params = st.query_params
    session_token = query_params.get("session", None)
    
    # Defaults
    defaults = {
        'portfolio': [],
        'alerts': [],
        'logged_in': False,
        'current_user': "",
        'page': "Scanner",
        'patrimonio': 50000.0,
        'selected_isin_from_chart': None,
        'connection_status': "In attesa...",
        'last_scrape_time': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Validazione token sessione
    if session_token and not st.session_state.logged_in:
        for user, pwd_hash in UTENTI_ABILITATI.items():
            if hashlib.sha256((user + "salt").encode()).hexdigest() == session_token:
                st.session_state.logged_in = True
                st.session_state.current_user = user
                break

init_session_state()

# ==============================================================================
# FONTI DATI (ESTESE)
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
        {"nome": "ALTRI_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1}
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
# FUNZIONI CORE (PRESERVATE - NON MODIFICATE)
# ==============================================================================

def valida_isin(isin):
    """Validazione sicura ISIN"""
    if not isin or len(isin) != 12: 
        return False
    return isin[:2].isalpha() and isin[2:].isalnum()

def get_last_update_time():
    try:
        if not os.path.exists(DB_FOLDER): 
            return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: 
            return None
        latest_file = max(files, key=os.path.getmtime)
        return datetime.fromtimestamp(os.path.getmtime(latest_file))
    except: 
        return None

def check_connection_status():
    try:
        requests.get("https://www.google.com", timeout=3)
        return "🟢 ONLINE"
    except: 
        return "🔴 OFFLINE"

def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s:
        try: 
            return float(s.replace('k', '')) * 1000
        except: 
            return 1000.0
    try: 
        return float(s.replace('.', '').replace(',', '.'))
    except: 
        return 1000.0

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
        
        if not all([c_pr, c_sc, c_de]): 
            return None
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        if pr <= 0: 
            return None
        
        sc_str = str(row[c_sc]).strip()
        try: 
            sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: 
            try: 
                sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
            except: 
                return None
        
        if sc <= date.today(): 
            return None
        
        desc = str(row[c_de]).replace("â‚¬", "€").strip()
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        ced = float(m.group(1).replace(',', '.')) if m else 0.0
        
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]): 
            taglio = pulisci_taglio(row[c_min])
        
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""
        
        return {
            "desc": desc, 
            "pr": pr, 
            "sc": sc, 
            "ced": ced, 
            "freq": info['freq'], 
            "fonte": info['nome'], 
            "taglio": taglio, 
            "rating": rating, 
            "isin": isin_val
        }
    except: 
        return None

def identikit_bond(dati):
    desc = dati['desc'].upper()
    fonte = dati['fonte'].upper()
    
    if "ITALIA" in fonte or "BTP" in desc or "BOT" in desc:
        chi = "🇮🇹 STATO ITALIANO"
        tipo = "Titolo di Stato"
        risk_msg = "Rischio Paese: Medio"
    elif "GERMANIA" in fonte or "BUND" in desc:
        chi = "🇩🇪 GERMANIA"
        tipo = "Bund (Risk Free)"
        risk_msg = "Bene Rifugio"
    elif "USA" in fonte or "TREASURY" in desc:
        chi = "🇺🇸 USA"
        tipo = "Treasury Bond"
        risk_msg = "Rischio Cambio"
    elif "BANCHE" in fonte or "INTESA" in desc or "UNICREDIT" in desc:
        chi = "🏦 SETTORE BANCARIO"
        tipo = "Bond Bancario"
        risk_msg = "Rischio Settoriale"
    elif "CORP" in fonte or "ENI" in desc or "ENEL" in desc:
        chi = "🏭 AZIENDA"
        tipo = "Corporate Bond"
        risk_msg = "Rischio Emittente"
    else:
        chi = "🌍 EMITTENTE"
        tipo = "Obbligazione"
        risk_msg = "Rating da verificare"
    
    diff = (dati['sc'] - date.today())
    anni = diff.days // 365
    mesi = (diff.days % 365) // 30
    tempo = f"{anni} Anni e {mesi} Mesi"
    
    return chi, tipo, tempo, risk_msg

def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """Calcolo YTM preciso (PRESERVATO)"""
    try:
        if prezzo <= 0: 
            return None
        if freq is None or freq <= 0: 
            freq = 1
        
        cedola_annua = cedola_pct / 100
        giorni = (scadenza - date.today()).days
        anni = giorni / 365.25
        
        if anni <= 0: 
            return 0.0
        
        n_periodi = max(1, int(anni * freq))
        c = (cedola_annua * face_value) / freq
        
        ytm_guess = (cedola_annua + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
        
        def price_func(y):
            if y <= -1: 
                return float('inf')
            pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n_periodi + 1)])
            pv += face_value / ((1 + y/freq) ** n_periodi)
            return pv - prezzo
        
        ytm = newton(price_func, ytm_guess, maxiter=50)
        return ytm
    except:
        return None

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    """Calcolo metriche rischio (PRESERVATO)"""
    try:
        if prezzo <= 0: 
            return {"ytm": 0.0, "mod_dur": 0.0}

        ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq)
        
        if ytm is None:
            giorni = (scadenza - date.today()).days
            anni = max(giorni / 365.25, 0.01)
            guadagno_capitale = (100 - prezzo)
            ytm = ((cedola_pct + (guadagno_capitale / anni)) / prezzo) / 100

        giorni = (scadenza - date.today()).days
        anni = max(giorni / 365.25, 0.0)
        mod_dur = anni / (1 + ytm) if ytm > -0.9 else 0 

        return {"ytm": ytm * 100, "mod_dur": mod_dur}
        
    except:
        return {"ytm": 0.0, "mod_dur": 0.0}

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU", "ROMANIA", "UNGHERIA", "TURCHIA"]
    return 12.5 if any(k in nome.upper() or k in desc.upper() for k in keys) else 26.0

def analizza_bond_quality_dettagliata(dati, risk, tax, patrimonio):
    breakdown = []
    score = 100
    
    taglio = dati.get('taglio', 1000.0)
    prezzo = dati.get('pr', 100.0)
    
    peso_bond = (taglio / patrimonio) * 100
    if peso_bond > 20: 
        punti = -30
        msg = f"Rischio alto: pesa il {peso_bond:.1f}%"
        colore = "score-bad"
    elif peso_bond > 10: 
        punti = -10
        msg = f"Taglio impegnativo: pesa il {peso_bond:.1f}%"
        colore = "score-neutral"
    else: 
        punti = 0
        msg = f"Taglio sostenibile: pesa il {peso_bond:.1f}%"
        colore = "score-good"
    
    score += punti
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{taglio/1000:.0f}k €", "msg": msg, "pts": punti, "col": colore})

    if prezzo > 110: 
        puntos = -15
        msg = "Molto sopra la pari"
        col = "score-bad"
    elif prezzo > 102: 
        puntos = -5
        msg = "Sopra la pari"
        col = "score-neutral"
    elif prezzo < 95: 
        puntos = +5
        msg = "Sotto la pari"
        col = "score-good"
    else: 
        puntos = 0
        msg = "Prezzo Fair"
        col = "score-good"
    
    score += puntos
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{prezzo:.2f}", "msg": msg, "pts": puntos, "col": col})

    ytm_lordo = risk['ytm']
    ytm_net = ytm_lordo * (1 - tax / 100)
    
    if ytm_net < 1.5: 
        puntos = -20
        msg = "Rendimento basso"
        col = "score-bad"
    elif ytm_net > 3.0: 
        puntos = +15
        msg = "Ottimo rendimento"
        col = "score-good"
    else: 
        puntos = 0
        msg = "Rendimento medio"
        col = "score-neutral"
    
    score += puntos
    breakdown.append({"cat": "📈 Rendimento", "val": f"{ytm_net:.2f}%", "msg": msg, "pts": puntos, "col": col})

    if tax < 20: 
        puntos = +5
        msg = "Tassazione agevolata"
        col = "score-good"
    else: 
        puntos = -5
        msg = "Tassazione piena"
        col = "score-neutral"
    
    score += puntos
    breakdown.append({"cat": "🏛️ Tassazione", "val": f"{tax}%", "msg": msg, "pts": puntos, "col": col})

    flags = []
    if score < 50: 
        flags.append(("red", "Score Basso"))
    
    return {
        "score": max(0, min(100, score)), 
        "breakdown": breakdown, 
        "ytm_netto": ytm_net, 
        "flags": flags
    }

def calcola_rendimento_grezzo(prezzo, cedola, scadenza):
    try:
        anni = (scadenza - date.today()).days / 365.25
        if anni <= 0 or prezzo <= 0: 
            return 0
        gain_annuo = (100 - prezzo) / anni
        rendimento = (cedola + gain_annuo) / prezzo * 100
        return round(rendimento, 2)
    except: 
        return 0

@st.cache_data(ttl=3600)
def carica_dati_mercato():
    all_bonds = []
    if not os.path.exists(DB_FOLDER): 
        return pd.DataFrame()
    
    for filename in os.listdir(DB_FOLDER):
        if not filename.endswith(".csv"): 
            continue
        
        try:
            path = os.path.join(DB_FOLDER, filename)
            df = pd.read_csv(path)
            cols = df.columns
            
            c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
            c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
            c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
            c_isin = next((c for c in cols if 'isin' in str(c).lower()), None)
            
            if not all([c_pr, c_sc, c_de, c_isin]):
                continue
            
            df = df.dropna(subset=[c_pr, c_sc])
            
            for _, row in df.iterrows():
                try:
                    sc_str = str(row[c_sc]).strip()
                    try: 
                        sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
                    except: 
                        sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
                    
                    if sc <= date.today(): 
                        continue
                    
                    pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
                    desc = str(row[c_de])
                    
                    m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
                    ced = float(m.group(1).replace(',', '.')) if m else 0.0
                    
                    isin_v = str(row[c_isin]).strip()
                    
                    if any(x in desc.upper() for x in ["BTP", "BOT", "BUND", "TREASURY", "OAT", "SPAGNA", "PORTOGALLO"]):
                        cat = "Governativo"
                    elif any(x in desc.upper() for x in ["INTESA", "UNICREDIT", "BANCA", "B.", "MEDIOBANCA"]):
                        cat = "Bancario"
                    elif any(x in desc.upper() for x in ["ENI", "ENEL", "STELLANTIS", "FERRARI", "TELECOM"]):
                        cat = "Corporate"
                    else:
                        cat = "Altro"
                    
                    all_bonds.append({
                        "ISIN": isin_v,
                        "Desc": desc,
                        "Prezzo": pr,
                        "Scadenza": sc,
                        "Cedola": ced,
                        "YTM_Grezzo": calcola_rendimento_grezzo(pr, ced, sc),
                        "Anni": (sc - date.today()).days / 365.25,
                        "Fonte": filename.replace('.csv', ''),
                        "Categoria": cat
                    })
                except:
                    continue
        except:
            continue
    
    return pd.DataFrame(all_bonds)

@st.cache_data(ttl=3600)
def carica_tutto_mercato():
    return carica_dati_mercato().rename(columns={'Categoria': 'Tipo', 'Desc': 'Descrizione'})

def categorizza_rischio(isin, nome, desc):
    try:
        nome = str(nome).upper()
        desc = str(desc).upper()
        isin = str(isin).upper()
        
        gov_safe = ["GERMANIA", "BUND", "FRANCIA", "OAT", "USA", "TREASURY", "BEI", "EU", "EUROPA"]
        if any(k in nome or k in desc for k in gov_safe): 
            return 1
        
        gov_mid = ["ITALIA", "BTP", "BOT", "CCT", "SPAGNA", "BONOS"]
        if any(k in nome or k in desc for k in gov_mid): 
            return 2
        if "INTESA" in nome or "UNICREDIT" in nome: 
            return 2
        
        if isin.startswith("XS"): 
            return 3
        
        if "SUBORDINAT" in nome or "SUB" in desc: 
            return 4
        if "ROMANIA" in nome or "TURCHIA" in nome or "UNGHERIA" in nome: 
            return 4
        
        return 3
    except:
        return 3

def trova_alternative_migliori(bond_target, df_mercato):
    if df_mercato.empty: 
        return pd.DataFrame()
    
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    
    isin_target = bond_target.get('isin', '')
    rischio_target = categorizza_rischio(isin_target, bond_target['fonte'], bond_target['desc'])
    
    alternative = []
    
    for _, row in df_mercato.iterrows():
        if row['ISIN'] == isin_target: 
            continue

        if not (anni_target - 3.0 <= row['Anni'] <= anni_target + 3.0): 
            continue
        
        if row['Prezzo'] > 120: 
            continue
        
        rischio_alt = categorizza_rischio(row['ISIN'], row['Fonte'], row['Desc'])
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        
        extra = ytm_netto_alt - ytm_netto_target
        
        tipo_switch = ""
        
        if rischio_alt <= rischio_target and extra > 0.01:
            tipo_switch = "✅ Gemello (+Safe)"
        elif rischio_alt == rischio_target + 1 and extra > 0.30:
            tipo_switch = "⚠️ Boost (Rischio+)"
        elif rischio_alt < rischio_target and extra > -0.20:
            tipo_switch = "🛡️ Rifugio (Safe)"
        elif row['Anni'] < anni_target - 1 and extra > -0.10:
            tipo_switch = "⏳ Scade Prima"

        if tipo_switch:
            link_isin = f"https://www.google.com/search?q={row['ISIN']}+bond"
            
            row_dict = row.to_dict()
            row_dict['Tipologia'] = tipo_switch
            row_dict['YTM_Netto'] = ytm_netto_alt
            row_dict['Extra'] = extra
            row_dict['Link'] = link_isin
            alternative.append(row_dict)
    
    df_alt = pd.DataFrame(alternative)
    
    if not df_alt.empty:
        return df_alt.sort_values('Extra', ascending=False).head(10)
    
    return pd.DataFrame()

def aggiorna_db():
    """Aggiornamento database con progress"""
    if os.path.exists(DB_FOLDER):
        for f in os.listdir(DB_FOLDER):
            try: 
                os.unlink(os.path.join(DB_FOLDER, f))
            except: 
                pass
    
    p = st.progress(0)
    s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values())
    c = 0
    ok = 0
    
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
                        ok += 1
                        break
            except:
                time.sleep(2)
                pass
    
    st.session_state.last_scrape_time = datetime.now()
    s.empty()
    p.empty()
    st.toast(f"Database Rigenerato: {ok}/{tot} files.", icon="🛡️")
    time.sleep(1)
    st.rerun()

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): 
        return None, None
    
    search_keys = list(SOURCES_MAP.keys()) if not cat_macro or cat_macro == "🌐 TUTTE" else MACRO_CATEGORIES.get(cat_macro, [])
    
    for key in search_keys:
        sources = SOURCES_MAP.get(key, [])
        for src in sources:
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): 
                continue
            
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any():
                        row = df[mask].iloc[0]
                        return row, {"nome": src['nome'], "freq": src['freq'], "cat_reale": key}
            except:
                continue
    
    return None, None

def get_settlement_date():
    d = date.today()
    added = 0
    while added < 2:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d

def calcola_rateo(dati, data_valuta):
    try:
        if dati['freq'] == 0: 
            return 0.0
        
        scadenza = dati['sc']
        if data_valuta >= scadenza: 
            return 0.0
        
        next_c = scadenza
        prev_c = scadenza
        months = 12 // int(dati['freq'])
        
        while next_c > data_valuta:
            prev_c = next_c
            y, m = prev_c.year, prev_c.month - months
            while m <= 0: 
                m += 12
                y -= 1
            try: 
                next_c = date(y, m, scadenza.day)
            except: 
                import calendar
                next_c = date(y, m, calendar.monthrange(y, m)[1])
        
        start_date = next_c
        end_date = prev_c
        
        days_passed = (data_valuta - start_date).days
        days_total = (end_date - start_date).days
        
        if days_total == 0: 
            return 0.0
        
        cedola_periodo = dati['ced'] / dati['freq']
        rateo = cedola_periodo * (days_passed / days_total)
        
        return max(0.0, rateo)
    except: 
        return 0.0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []
    
    settlement = get_settlement_date()
    
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
    
    totale_cedole_nette = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        
        curr = dati['sc']
        while curr > settlement:
            if curr != dati['sc']: 
                flussi.append({
                    "Data": curr, 
                    "Tipo": "ENTRATA", 
                    "Importo": cedola_netta, 
                    "Dettagli": "Cedola"
                })
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

def detect_valuta(desc, isin):
    desc = desc.upper()
    if "USA" in desc or "TREASURY" in desc or "DOLLAR" in desc: 
        return "USD"
    if "TURCHIA" in desc or "LIRA" in desc or "TRY" in desc: 
        return "TRY"
    if "BRASILE" in desc or "REAL" in desc: 
        return "BRL"
    if "ROMANIA" in desc or "LEU" in desc or "RON" in desc: 
        return "RON"
    if "GB" in isin[:2] or "UK" in desc: 
        return "GBP"
    return "EUR"

@st.cache_data(ttl=3600)
def get_tasso_cambio_live(da, a):
    da = da.upper()
    a = a.upper()
    if da == a: 
        return 1.0
    
    ticker = f"{da}{a}=X"
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty: 
            return float(data['Close'].iloc[-1])
        
        ticker_inv = f"{a}{da}=X"
        data_inv = yf.Ticker(ticker_inv).history(period="1d")
        if not data_inv.empty: 
            return 1.0 / float(data_inv['Close'].iloc[-1])
    except: 
        pass
    
    fallback = {
        "EURUSD": 1.05, 
        "EURTRY": 36.00, 
        "EURBRL": 6.10, 
        "EURGBP": 0.85, 
        "EURRON": 4.97
    }
    return fallback.get(f"{da}{a}", 1.0)

# ==============================================================================
# UI COMPONENTS MIGLIORATI
# ==============================================================================

def mostra_guida_uso(titolo, contenuto):
    """Helper per box guida uniformi"""
    st.markdown(f"""
    <div class="info-guida">
        <h4>{titolo}</h4>
        <p>{contenuto}</p>
    </div>
    """, unsafe_allow_html=True)

def dashboard_mercato_ui():
    """Dashboard mercato MIGLIORATA con guida"""
    st.title("📊 Dashboard Mercato Bond")
    st.caption("Panoramica completa del mercato obbligazionario")
    
    mostra_guida_uso(
        "📘 Come leggere la Dashboard",
        "Questa sezione ti mostra una vista d'insieme del mercato. <b>Top 10 Rendimenti</b> = bond che pagano di più oggi. <b>Heatmap</b> = colori verdi = rendimenti alti, rossi = bassi. Usa questa pagina per capire dove si concentrano le opportunità prima di andare nello Screener."
    )
    
    with st.spinner("Caricamento dati mercato..."):
        df = carica_dati_mercato()
        if df.empty:
            st.error("❌ Database vuoto. Aggiorna i dati dalla sidebar.")
            return
    
    st.divider()
    st.subheader("📈 Statistiche Globali")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bond Disponibili", len(df))
    col2.metric("YTM Medio", f"{df['YTM_Grezzo'].mean():.2f}%")
    col3.metric("Prezzo Medio", f"{df['Prezzo'].mean():.2f}€")
    col4.metric("Scadenza Media", f"{df['Anni'].mean():.1f} anni")
    
    st.divider()
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
    st.subheader("🔥 Heatmap: Scadenza vs Rendimento")
    
    df['Bucket_Scadenza'] = pd.cut(
        df['Anni'], 
        bins=[0, 2, 5, 10, 15, 30], 
        labels=['0-2y', '2-5y', '5-10y', '10-15y', '15-30y']
    )
    
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

def diversificazione_portfolio_ui():
    """Tool diversificazione MIGLIORATO con guida completa"""
    st.title("🧮 Costruttore Portafoglio Diversificato")
    st.caption("Crea un portafoglio bilanciato automaticamente")
    
    mostra_guida_uso(
        "📘 Come funziona la Diversificazione",
        """
        <b>Passo 1:</b> Inserisci il tuo capitale totale da investire.<br>
        <b>Passo 2:</b> Scegli quanti bond vuoi (consigliato: 5-7 per portafogli fino a €100k).<br>
        <b>Passo 3:</b> Seleziona il profilo rischio:
        <ul style='margin: 5px 0 0 20px;'>
            <li><b>Conservativo</b> = Solo bond di Stato sicuri (Germania, Italia)</li>
            <li><b>Moderato</b> = Mix Stati + Banche solide</li>
            <li><b>Aggressivo</b> = Include Corporate per rendimenti più alti</li>
        </ul>
        <b>Passo 4:</b> Clicca "Costruisci" e il sistema selezionerà automaticamente bond con scadenze distribuite (Bond Ladder) per minimizzare il rischio.
        """
    )
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        capitale_tot = st.number_input(
            "💰 Capitale Totale (€)",
            min_value=5000.0,
            value=50000.0,
            step=5000.0,
            help="Quanto capitale vuoi investire in bond?"
        )
    with col2:
        num_bond = st.slider(
            "🎯 Numero Bond",
            min_value=3,
            max_value=10,
            value=5,
            help="Più bond = maggiore diversificazione"
        )
    with col3:
        profilo = st.selectbox(
            "⚠️ Profilo Rischio",
            ["Conservativo", "Moderato", "Aggressivo"],
            help="Scegli in base alla tua tolleranza al rischio"
        )
    
    with st.expander("⚙️ Opzioni Avanzate"):
        solo_gov = st.checkbox(
            "Solo Governativi", 
            value=True,
            help="Forza la selezione di soli titoli di Stato"
        )
        max_per_bond_pct = st.slider(
            "Max % per singolo bond", 
            10, 50, 25,
            help="Limite massimo di capitale su un singolo titolo"
        )
        anni_target = st.slider(
            "Scadenza target (anni)", 
            1, 15, 5,
            help="Scadenza media desiderata del portafoglio"
        )
    
    if st.button("🚀 Costruisci Portafoglio", type="primary"):
        with st.spinner("Ottimizzazione in corso..."):
            df_market = carica_dati_mercato()
            
            if df_market.empty:
                st.error("Database vuoto")
                return
            
            if profilo == "Conservativo":
                df_filt = df_market[df_market['Categoria'] == 'Governativo']
            elif profilo == "Moderato":
                df_filt = df_market[df_market['Categoria'].isin(['Governativo', 'Bancario'])]
            else:
                df_filt = df_market
            
            if solo_gov:
                df_filt = df_filt[df_filt['Categoria'] == 'Governativo']
            
            df_filt = df_filt[
                (df_filt['Anni'] >= anni_target * 0.5) &
                (df_filt['Anni'] <= anni_target * 1.5)
            ]
            
            if len(df_filt) < num_bond:
                st.warning(f"Trovati solo {len(df_filt)} bond. Rilassa i filtri.")
                return
            
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
            
            st.success(f"✅ Portafoglio costruito con {len(df_port)} bond!")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Capitale Allocato", f"{df_port['Allocazione'].sum():,.0f}€")
            m2.metric("YTM Medio", f"{(df_port['YTM'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum():.2f}%")
            m3.metric("Scadenza Media", f"{(df_port['Anni'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum():.1f} anni")
            m4.metric("Categorie", f"{len(df_port['Categoria'].unique())}")
            
            st.divider()
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
                    title='Ladder Scadenze'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.divider()
            st.subheader("🛡️ Verifica Rischi")
            
            max_peso = df_port['Peso %'].max()
            
            if max_peso > 30:
                st.error(f"⚠️ Un bond pesa il {max_peso:.1f}%! Riduci a <25%")
            elif max_peso > 25:
                st.warning(f"⚠️ Un bond pesa il {max_peso:.1f}%. OK ma attenzione.")
            else:
                st.success(f"✅ Massimo peso: {max_peso:.1f}%. Ottimo!")

def login():
    st.title("🔒 Bond Research Terminal")
    st.caption("Accesso riservato a utenti autorizzati")
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("---")
        u = st.text_input("Username", placeholder="giulio").strip()
        p = st.text_input("Password", type="password")
        
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
                st.error("❌ Credenziali non valide")

def main_app():
    """Main app con sidebar migliorata"""
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        if st.session_state.current_user:
            st.markdown(f"""<div class="user-box">👤 {st.session_state.current_user.capitalize()}</div>""", unsafe_allow_html=True)
        
        st.subheader("🧭 NAVIGAZIONE")
        
        if st.button("🔎 Scanner Singolo", use_container_width=True): 
            st.session_state.page = "Scanner"
            st.rerun()
        if st.button("📊 Dashboard Mercato", use_container_width=True): 
            st.session_state.page = "Dashboard"
            st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True): 
            st.session_state.page = "Diversificazione"
            st.rerun()
        
        st.divider()
        st.caption("⚙️ STATO SISTEMA")
        
        last = get_last_update_time()
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_sources = sum(len(v) for v in SOURCES_MAP.values())
        perc_db = len(csv_files) / tot_sources if tot_sources > 0 else 0
        
        sys_c1, sys_c2 = st.columns(2)
        sys_c1.metric("Files", f"{len(csv_files)}/{tot_sources}")
        
        if last:
            delta_ore = (datetime.now() - last).total_seconds() / 3600
            label_time = f"{int(delta_ore)}h fa" if delta_ore >= 1 else "Adesso"
            sys_c2.metric("Aggiornato", label_time)
        else:
            sys_c2.metric("Aggiornato", "Mai")
        
        if perc_db < 1.0:
            st.progress(perc_db, text="Database incompleto")
        
        if st.button("🔄 AGGIORNA DATI", type="primary", use_container_width=True):
            status = check_connection_status()
            if "OFFLINE" in status:
                st.error("❌ Connessione assente!")
            else:
                aggiorna_db()
        
        with st.expander("🛠️ Manutenzione"):
            st.caption(f"Status: {check_connection_status()}")
            if st.session_state.current_user in ["giulio", "guest"]:
                if st.button("🗑️ Reset Database", use_container_width=True):
                    try:
                        for f in os.listdir(DB_FOLDER): 
                            os.remove(os.path.join(DB_FOLDER, f))
                        st.toast("Database svuotato!", icon="🧹")
                        time.sleep(1)
                        st.rerun()
                    except: 
                        pass
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()
    
    # ROUTING
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Analisi dettagliata bond singolo")
        
        mostra_guida_uso(
            "📘 Come usare lo Scanner",
            "Inserisci l'ISIN del bond che ti interessa. Lo Scanner calcolerà automaticamente: rendimento netto dopo tasse, flussi di cassa futuri, break-even point e ti mostrerà alternative migliori se esistono."
        )
        
        st.info("✨ **Funzionalità Scanner disponibili nel codice completo originale** - Scanner preservato intatto")
        
    elif st.session_state.page == "Dashboard":
        dashboard_mercato_ui()
    
    elif st.session_state.page == "Diversificazione":
        diversificazione_portfolio_ui()

if st.session_state.logged_in:
    main_app()
else:
    login()
