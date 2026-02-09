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
# 3. MAPPA FONTI (DATASET ESTESO - PRO VERSION)
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
        # Filtro Rigido Categoria (o simili)
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
    # Cerca in tutte le categorie se cat non è specificato
    search_cats = list(SOURCES_MAP.keys())
    for c in search_cats:
        for src in SOURCES_MAP.get(c, []):
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): continue
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any(): 
                        row = df[mask].iloc[0]
                        # Tentativo di rilevare la categoria reale
                        cat_reale = "Governativo" if "BTP" in str(row) or "BOT" in str(row) else "Corporate" # Semplificato
                        return row, {"nome": src['nome'], "freq": src['freq'], "cat_reale": c}
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
        
        st.markdown("### 🧭 Guida alle Categorie")
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown("""
            <div class="cat-card bg-gov">
                <div class="cat-title">🏛️ GOVERNATIVI</div>
                <div class="cat-desc">Titoli di Stato (es. BTP, Bund). Massima sicurezza, tassazione agevolata.</div>
                <div><span class="cat-meta">Rischio: BASSO</span><span class="cat-meta">Tax: 12.5%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown("""
            <div class="cat-card bg-bank">
                <div class="cat-title">🏦 FINANZIARI</div>
                <div class="cat-desc">Obbligazioni bancarie. Rendimento medio. Attenzione se "Subordinate".</div>
                <div><span class="cat-meta">Rischio: MEDIO</span><span class="cat-meta">Tax: 26%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            st.markdown("""
            <div class="cat-card bg-corp">
                <div class="cat-title">🏭 CORPORATE</div>
                <div class="cat-desc">Emessi da aziende (es. Eni, Fiat). Rendimento più alto, rischio emittente.</div>
                <div><span class="cat-meta">Rischio: ALTO</span><span class="cat-meta">Tax: 26%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c4:
            st.markdown("""
            <div class="cat-card bg-spec">
                <div class="cat-title">💎 SPECIALI</div>
                <div class="cat-desc">Zero Coupon, Callable, 25y+. Strumenti complessi per strategie avanzate.</div>
                <div><span class="cat-meta">Rischio: VARIABILE</span><span class="cat-meta">Tax: Mista</span></div>
            </div>
            """, unsafe_allow_html=True)
        
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
                    
                    st.subheader("📊 Dati Chiave")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("Prezzo", f"{d['pr']}€", delta="Sopra la Pari" if d['pr']>100 else "Sotto la Pari", 
                              help="💰 **Cosa significa?**\n\n• **Sotto la Pari (<100):** Paghi meno del valore che ti rimborseranno. Es: paghi 90, ricevi 100. La differenza è guadagno extra.\n• **Sopra la Pari (>100):** Paghi di più. Es: paghi 105, ricevi 100. È normale se la cedola è alta.")
                    c2.metric("Rendimento Netto", f"{qual['ytm_netto']:.2f}%", 
                              help="📈 **Cosa significa?**\n\nÈ il guadagno reale annuo che ti rimane in tasca, GIA' SOTTRATTE le tasse (12.5% o 26%). È il numero più importante da guardare.")
                    c3.metric("Rendimento Lordo", f"{risk['ytm']:.2f}%",
                              help="È il guadagno annuo PRIMA delle tasse. Serve per confrontare bond con tassazione diversa.")
                    c4.metric("Cedola", f"{d['ced']}%", 
                              help="💸 **Cosa significa?**\n\nÈ l'interesse periodico (il bonifico) che l'emittente ti paga. Es: 4% su 1.000€ = 40€ lordi l'anno.")
                    c5.metric("Taglio Minimo", f"{d['taglio']:,.0f}€", 
                              help="🧱 **Cosa significa?**\n\nÈ la quantità minima che puoi comprare. Se è 1.000€, non puoi investirne 500€.")
                    c6.metric("Duration", f"{risk['mod_dur']:.2f} Anni", 
                              help="📉 **Cosa significa?**\n\nIndica quanto è rischioso il prezzo. Se la Duration è 6 anni, e i tassi salgono dell'1%, il prezzo del bond scenderà circa del 6%.")

                    st.divider()
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
                        if d['freq'] == 1: freq_txt = "in un'unica soluzione annuale"
                        elif d['freq'] == 2: freq_txt = f"in 2 cedole semestrali da {cedola_netta_euro/2:.2f}€"
                        elif d['freq'] == 4: freq_txt = f"in 4 cedole trimestrali da {cedola_netta_euro/4:.2f}€"
                        elif d['freq'] == 0: freq_txt = "(Zero Coupon: tutto a scadenza)"
                        else: freq_txt = ""
                        st.markdown(f'<div class="explanation-text">Ogni 1.000€ investiti, riceverai circa <b>{cedola_netta_euro:.2f}€ netti</b> all\'anno, {freq_txt}.</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    with t3:
                        st.markdown('<div class="explanation-box">', unsafe_allow_html=True)
                        st.markdown('<div class="explanation-title">3. Rischio Prezzo</div>', unsafe_allow_html=True)
                        volatilita = "BASSA" if risk['mod_dur'] < 3 else "MEDIA" if risk['mod_dur'] < 7 else "ALTA"
                        st.markdown(f'<div class="explanation-text">Volatilità: <b>{volatilita}</b>. Se i tassi salgono dell\'1%, il prezzo scende del {risk["mod_dur"]:.1f}%.</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    st.divider()
                    st.subheader("💰 Simulatore d'Acquisto")
                    c_sim1, c_sim2 = st.columns([1, 2])
                    with c_sim1:
                        investimento = st.number_input("Quanto vuoi investire? (€)", value=10000, step=1000)
                        commissioni = st.number_input("Commissioni Banca (€)", value=5.0, step=1.0, help="Non lo sai? Se hai una banca online (Fineco, Directa) metti 5-10€. Se hai una banca fisica, spesso è lo 0.19% del capitale (es. 19€ su 10k).")
                    
                    df_flussi, spesa_tot, incasso_tot, costo_rateo, totale_cedole_nette, plusvalenza_netta = genera_flussi_dettagliati(d, investimento, tax, commissioni, d['pr'])
                    guadagno_netto = incasso_tot - spesa_tot
                    anni_durata = (d['sc'] - date.today()).days / 365.25
                    rend_annuo_semplice = (guadagno_netto / spesa_tot / anni_durata) * 100 if anni_durata > 0 else 0
                    
                    with c_sim2:
                        st.markdown(f"""
                        <div class="receipt-box">
                            <div class="receipt-row"><span>Costo Titoli (Prezzo {d['pr']}):</span> <span>{investimento * d['pr'] / 100:.2f} €</span></div>
                            <div class="receipt-row"><span>+ Rateo Interessi (da anticipare):</span> <span>{costo_rateo:.2f} €</span></div>
                            <div class="receipt-row"><span>+ Commissioni Banca:</span> <span>{commissioni:.2f} €</span></div>
                            <div class="receipt-total"><span>TOTALE DA PAGARE OGGI:</span><span>{spesa_tot:.2f} €</span></div>
                            <div class="receipt-sub">Hai pagato circa {(spesa_tot/investimento)*100:.1f}% del valore nominale</div>
                            <hr>
                            <div class="receipt-row" style="color:#00CC96; font-weight:bold;"><span>GUADAGNO TOTALE (in {anni_durata:.1f} anni):</span><span>+{guadagno_netto:.2f} €</span></div>
                            <div class="receipt-row"><span>Rendimento Annuo Effettivo:</span><span>{rend_annuo_semplice:.2f}%</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.info(f"""
                        ℹ️ **Perché questo rendimento ({rend_annuo_semplice:.2f}%) è diverso da quello sopra ({qual['ytm_netto']:.2f}%)?**
                        Perché qui stiamo calcolando i costi reali incluse le **Commissioni Bancarie ({commissioni}€)** che abbassano leggermente il rendimento finale.
                        **Composizione del Guadagno ({guadagno_netto:.2f}€):**
                        1. 🎫 Cedole Nette Totali: +{totale_cedole_nette:.2f}€
                        2. 📈 Guadagno sul Prezzo (Capital Gain): +{plusvalenza_netta:.2f}€
                        3. 🏦 Meno Costi (Commissioni): -{commissioni:.2f}€
                        """)

                    st.divider()
                    st.subheader("📅 Cedolario (I tuoi flussi di cassa)")
                    tot_da_incassare = df_flussi[df_flussi['Importo'] > 0]['Importo'].sum()
                    data_fine = d['sc'].strftime('%d/%m/%Y')
                    col_kpi_c1, col_kpi_c2 = st.columns(2)
                    col_kpi_c1.metric("Totale da Incassare (Netto)", f"{tot_da_incassare:.2f} €")
                    col_kpi_c2.metric("Ultimo Pagamento", data_fine)
                    
                    def color_negative_red(val):
                        color = '#ff4b4b' if val < 0 else '#00cc96'
                        return f'color: {color}; font-weight: bold;'
                        
                    st.dataframe(
                        df_flussi[['Data', 'Tipo', 'Importo', 'Dettagli']].style.map(color_negative_red, subset=['Importo']).format({'Importo': '{:+.2f} €', 'Data': lambda x: x.strftime('%d/%m/%Y')}),
                        use_container_width=True,
                        height=400
                    )
                    
                    fig_timeline = px.bar(df_flussi, x='Data', y='Importo', color='Tipo', 
                                        color_discrete_map={'USCITA': '#FF4B4B', 'ENTRATA': '#00CC96'},
                                        title="Timeline Flussi di Cassa", template="plotly_dark")
                    st.plotly_chart(fig_timeline, use_container_width=True)

                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("📌 Salva per Confronto", use_container_width=True):
                        st.session_state.confronto = d; st.success("Salvato!")
                    if c_btn2.button("💼 Aggiungi a Portafoglio", use_container_width=True):
                        st.session_state.portfolio.append(d)
                        st.success("Aggiunto!")

                else: st.warning("Bond non trovato. Aggiorna il DB.")

    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Pro Tools")
        st.caption("Strumenti istituzionali per la valutazione del rischio e del fair value, spiegati in modo semplice.")
        with st.spinner("Elaborazione dati di mercato..."):
            df_market = carica_dati_mercato()
        
        if df_market.empty: st.warning("⚠️ Database vuoto. Aggiorna i dati dalla sidebar.")
        else:
            col_search, col_kpi = st.columns([1, 3])
            with col_search:
                isin_smart = st.text_input("Analizza ISIN", placeholder="IT...").strip().upper()
                cat_view = st.selectbox("Filtra Categoria Ricerca", list(SOURCES_MAP.keys()))
                
            if isin_smart and valida_isin(isin_smart):
                row, info = cerca_db(isin_smart, cat_view)
                d_smart = processa_riga(row, info) if row is not None else None
                
                if d_smart:
                    cat_target = "Altro"
                    desc_upp = d_smart['desc'].upper()
                    fonte_upp = d_smart['fonte'].upper()
                    if "BTP" in desc_upp or "BOT" in desc_upp or "ITALIA" in fonte_upp: cat_target = "Governativo"
                    elif "BUND" in desc_upp or "GERMANIA" in desc_upp: cat_target = "Governativo"
                    elif "BANCHE" in fonte_upp or "INTESA" in desc_upp or "UNICREDIT" in desc_upp: cat_target = "Bancario"
                    elif "CORP" in fonte_upp or "ENI" in desc_upp or "STELLANTIS" in desc_upp: cat_target = "Corporate"
                    
                    if cat_target == "Altro":
                        if "GOVERNATIVI" in cat_view: cat_target = "Governativo"
                        elif "FINANZIARI" in cat_view: cat_target = "Bancario"
                        elif "CORPORATE" in cat_view: cat_target = "Corporate"

                    d_smart['isin'] = isin_smart
                    d_smart['Categoria'] = cat_target
                    ytm_s = calcola_rendimento_grezzo(d_smart['pr'], d_smart['ced'], d_smart['sc'])
                    risk_metrics = calcola_metriche_rischio(d_smart['pr'], d_smart['ced'], d_smart['sc'], d_smart['freq'])
                    duration = risk_metrics['mod_dur'] if risk_metrics else 0
                    anni_scadenza = (d_smart['sc'] - date.today()).days / 365.25
                    
                    st.divider()
                    st.subheader(f"📊 Market Landscape: {cat_target}")
                    
                    range_zoom = 4
                    df_zoom = df_market[
                        (df_market['Anni'] >= anni_scadenza - range_zoom) & 
                        (df_market['Anni'] <= anni_scadenza + range_zoom) &
                        (df_market['YTM_Grezzo'] > -2) & (df_market['YTM_Grezzo'] < 15)
                    ].copy()
                    
                    fig = px.scatter(
                        df_zoom, x='Anni', y='YTM_Grezzo', color='Categoria', 
                        hover_data={'ISIN': True, 'Desc': True, 'Prezzo': ':.2f', 'YTM_Grezzo': ':.2f', 'Categoria': False},
                        color_discrete_map={"Governativo": "#00CC96", "Bancario": "#AB63FA", "Corporate": "#636EFA", "Altro": "#EF553B"},
                        opacity=0.7, labels={'Anni': 'Anni alla Scadenza', 'YTM_Grezzo': 'Rendimento Lordo (%)'}
                    )
                    
                    df_cat_specific = df_zoom[df_zoom['Categoria'] == cat_target]
                    if len(df_cat_specific) > 5:
                        z = np.polyfit(df_cat_specific['Anni'], df_cat_specific['YTM_Grezzo'], 2)
                        p = np.poly1d(z)
                        x_trend = np.linspace(df_zoom['Anni'].min(), df_zoom['Anni'].max(), 100)
                        fig.add_trace(go.Scatter(x=x_trend, y=p(x_trend), mode='lines', name=f'Media {cat_target}', line=dict(color='yellow', width=3, dash='dot')))
                        fair_yield = p(anni_scadenza)
                        delta_spread = ytm_s - fair_yield
                        sigma = np.std(df_cat_specific['YTM_Grezzo'] - p(df_cat_specific['Anni']))
                        z_score = delta_spread / sigma if sigma > 0 else 0
                    else:
                        fair_yield = ytm_s; delta_spread = 0; z_score = 0

                    fig.add_trace(go.Scatter(x=[anni_scadenza], y=[ytm_s], mode='markers+text', name='TUO BOND', text=['📍 TU'], textposition="top center", marker=dict(color='red', size=22, symbol='star')))
                    fig.update_layout(template="plotly_dark", height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    
                    selected_point = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
                    if selected_point and len(selected_point['selection']['points']) > 0:
                        try:
                            if 'customdata' in selected_point['selection']['points'][0]:
                                clicked_isin = selected_point['selection']['points'][0]['customdata'][0]
                                st.session_state.selected_isin_from_chart = clicked_isin
                                st.session_state.page = "Scanner"; st.rerun()
                        except: pass

                    st.divider()
                    st.subheader("🌡️ Analisi del Valore (Relativo alla Categoria)")
                    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
                    c_kpi1.metric("Rendimento Lordo", f"{ytm_s:.2f}%", help="È il rendimento annuo totale PRIMA delle tasse. Si usa il lordo per confrontare bond con tassazioni diverse (es. BTP vs Corporate).")
                    c_kpi2.metric(f"Fair Value ({cat_target})", f"{fair_yield:.2f}%", help=f"È il rendimento 'giusto' calcolato matematicamente. Rappresenta la media di quanto rendono oggi tutti gli altri bond {cat_target} con scadenza {anni_scadenza:.1f} anni.")
                    
                    verdetto = ""; colore_box = ""; spiegazione = ""
                    if z_score > 1.2: verdetto = "💎 SOTTOVALUTATO (Cheap)"; colore_box = "rgba(0, 204, 150, 0.2)"; spiegazione = f"Rende il **{delta_spread:+.2f}%** in più rispetto alla curva {cat_target}. Potrebbe essere un affare o incorporare un rischio specifico."
                    elif z_score > 0.4: verdetto = "✅ BUON VALORE"; colore_box = "rgba(0, 204, 150, 0.1)"; spiegazione = f"Rende leggermente sopra la media ({delta_spread:+.2f}%). Un buon acquisto difensivo."
                    elif z_score < -1.2: verdetto = "❌ SOPRAVALUTATO (Rich)"; colore_box = "rgba(255, 75, 75, 0.2)"; spiegazione = f"Rende molto meno ({delta_spread:+.2f}%) della media. È caro. Probabilmente è un emittente ultra-sicuro o molto liquido."
                    elif z_score < -0.4: verdetto = "⚠️ RENDIMENTO BASSO"; colore_box = "rgba(255, 170, 0, 0.1)"; spiegazione = f"Rende sotto la media ({delta_spread:+.2f}%). Ci sono alternative più redditizie a parità di rischio."
                    else: verdetto = "⚖️ FAIR VALUE"; colore_box = "rgba(128, 128, 128, 0.1)"; spiegazione = "Il prezzo è allineato al mercato. Non ci sono anomalie."

                    c_kpi3.metric("Spread vs Media", f"{delta_spread:+.2f}%", delta_color="normal", help="La differenza tra il TUO rendimento e il FAIR VALUE. Se è positivo (+), stai ottenendo un rendimento extra rispetto alla media.")
                    st.markdown(f"""<div style="background-color: {colore_box}; padding: 15px; border-radius: 10px; border-left: 5px solid white; margin-bottom: 20px;"><h3>{verdetto}</h3><p>{spiegazione}</p></div>""", unsafe_allow_html=True)

                    with st.expander("🎓 Come leggere questi dati (Clicca per info)"):
                        st.markdown("""
                        * **Rendimento Lordo:** Quanto rende il bond senza contare le tasse (utile per i confronti puri).
                        * **Fair Value:** Immaginalo come il "prezzo di listino" del mercato. Se il grafico mostra una linea gialla, quello è il Fair Value.
                        * **Spread:** È il tuo vantaggio. Se compri un bond con Spread positivo, stai comprando "a sconto" rispetto alla media della sua categoria.
                        """)

                    st.divider()
                    st.subheader("🛠️ Strumenti Pro: Rischio & Efficienza")
                    
                    col_stress, col_efficiency = st.columns([3, 2])
                    with col_stress:
                        st.markdown("**🌪️ Stress Test Tassi (Cosa succede se...?)**")
                        st.caption("Simulazione dell'impatto sul prezzo se la BCE alza o abbassa i tassi oggi.")
                        shocks = [-1.0, -0.5, 0.0, +0.5, +1.0, +2.0]
                        prices = []; pnl_pct = []
                        for s in shocks:
                            px_estim = d_smart['pr'] * (1 - (duration * (s/100)))
                            change = px_estim - d_smart['pr']
                            prices.append(f"{px_estim:.2f}€")
                            pnl_pct.append(change)
                        df_stress = pd.DataFrame({"Variazione Tassi": [f"{s:+.1f}%" for s in shocks], "Nuovo Prezzo": prices, "Perdita/Guadagno": [f"{ (p/d_smart['pr'])*100 :+.2f}%" for p in pnl_pct]})
                        def color_stress(val):
                            if "0.00" in val: return ""
                            return 'color: #ff4b4b' if '-' in val else 'color: #00cc96'
                        st.dataframe(df_stress.style.map(color_stress, subset=['Perdita/Guadagno']), use_container_width=True, hide_index=True)

                    with col_efficiency:
                        st.markdown("**🍋 Efficienza del Rischio**")
                        efficiency_score = ytm_s / duration if duration > 0 else 0
                        eff_label = "Eccellente" if efficiency_score > 0.8 else "Buona" if efficiency_score > 0.5 else "Bassa"
                        eff_color = "green" if efficiency_score > 0.8 else "orange" if efficiency_score > 0.5 else "red"
                        st.metric("Yield / Duration Ratio", f"{efficiency_score:.2f}x", help="Indica quanto rendimento ottieni per ogni unità di rischio (Duration) che ti assumi.")
                        st.markdown(f"Giudizio: :{eff_color}[**{eff_label}**]")
                        st.caption(f"Per ogni anno di durata (rischio), questo bond ti paga il **{efficiency_score:.2f}%** di rendimento.")
                        st.markdown("---")
                        risk_free_proxy = 2.50 
                        spread_implied = max(0, ytm_s - risk_free_proxy)
                        df_decomp = pd.DataFrame({"Componente": ["Tasso Base (Risk Free)", "Premio Rischio (Spread)"], "Valore": [risk_free_proxy, spread_implied]})
                        fig_pie = px.pie(df_decomp, values='Valore', names='Componente', hole=0.6, color_discrete_sequence=['#2E86C1', '#E74C3C'])
                        fig_pie.update_layout(showlegend=False, height=150, margin=dict(t=0, b=0, l=0, r=0), annotations=[dict(text=f"{ytm_s:.1f}%", x=0.5, y=0.5, font_size=16, showarrow=False)])
                        st.markdown("**🍔 Composizione Rendimento**")
                        st.plotly_chart(fig_pie, use_container_width=True)

                    st.divider()
                    st.subheader(f"🔄 Smart Switch ({cat_target})")
                    st.caption(f"Bond {cat_target} con durata simile che offrono un rendimento migliore.")
                    alternative = trova_alternative_migliori(d_smart, df_market, categoria_obbligatoria=cat_target)
                    
                    if not alternative.empty:
                        alternative['Efficienza'] = alternative['YTM_Netto'] / (alternative['Anni'] + 0.1) 
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
                    else:
                        st.success(f"🏆 Il tuo bond è già tra i migliori {cat_target} per questa scadenza.")

                else: st.error("ISIN non trovato nel database.")
            else: st.info("Inserisci un ISIN per iniziare l'analisi.")

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
