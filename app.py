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
import yfinance as yf 

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA E STILI CSS (ORIGINALE ESTESO)
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
# ==============================================================================
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
# --- SCANNER (VERSIONE GOLD: TUTTE LE FUNZIONI UX RICHIESTE) ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Analisi professionale con simulatore di rischio adattivo.")
        
        # 1. LEGENDA CATEGORIE (Stile Premium con Badge Arrotondati)
        st.markdown("### 🧭 Guida alle Categorie")
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown("""
            <div class="cat-card bg-gov">
                <div class="cat-title">🏛️ GOVERNATIVI</div>
                <div class="cat-desc">Titoli di Stato (es. BTP). Sicurezza massima.</div>
                <div><span class="cat-meta">Rischio: BASSO</span><span class="cat-meta">Tax: 12.5%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown("""
            <div class="cat-card bg-bank">
                <div class="cat-title">🏦 BANCARI</div>
                <div class="cat-desc">Obbligazioni bancarie. Rendimento medio.</div>
                <div><span class="cat-meta">Rischio: MEDIO</span><span class="cat-meta">Tax: 26%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c3:
            st.markdown("""
            <div class="cat-card bg-corp">
                <div class="cat-title">🏭 CORPORATE</div>
                <div class="cat-desc">Aziende (Eni, Fiat...). Rendimenti più alti.</div>
                <div><span class="cat-meta">Rischio: ALTO</span><span class="cat-meta">Tax: 26%</span></div>
            </div>
            """, unsafe_allow_html=True)
            
        with c4:
            st.markdown("""
            <div class="cat-card bg-spec">
                <div class="cat-title">💎 SPECIALI</div>
                <div class="cat-desc">Strumenti complessi (Sub, Callable).</div>
                <div><span class="cat-meta">Rischio: VARIO</span><span class="cat-meta">Tax: Mista</span></div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Input ISIN
        col_cat, col_isin, col_btn = st.columns([2, 2, 1])
        with col_cat: cat_select = st.selectbox("Filtra Categoria", list(MACRO_CATEGORIES.keys()))
        with col_isin: 
            default_isin = st.session_state.selected_isin_from_chart if st.session_state.selected_isin_from_chart else ""
            isin = st.text_input("ISIN", value=default_isin, placeholder="IT...").strip().upper()
            if st.session_state.selected_isin_from_chart: st.session_state.selected_isin_from_chart = None
            
        with col_btn: 
            st.write(""); st.write("")
            trigger_search = st.button("🔎 Cerca", use_container_width=True)
        
        # Logica Principale
        if isin and (trigger_search or isin):
            if not valida_isin(isin): st.error("❌ ISIN non valido")
            else:
                filtro_cat = cat_select if not default_isin else "🌐 TUTTE"
                row, info = cerca_db(isin, filtro_cat)
                d = processa_riga(row, info) if row is not None else None
                
                if d:
                    # Calcoli Finanziari Base
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality_dettagliata(d, risk, tax, st.session_state.patrimonio)
                    chi, tipo, tempo, risk_msg = identikit_bond(d)
                    
                    # Rilevamento Valuta
                    valuta_bond = detect_valuta(d['desc'], d['isin'])

                    # Header del Bond (Box con Gradiente)
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
                    
                    # Dati Chiave (CON INFO BOX 'help' ATTIVI)
                    st.subheader("📊 Dati Chiave")
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    simbolo = "€" if valuta_bond == "EUR" else valuta_bond
                    
                    c1.metric("Prezzo", f"{d['pr']} {simbolo}", help="Prezzo di mercato attuale.")
                    c2.metric("Rend. Netto (Locale)", f"{qual['ytm_netto']:.2f}%", help="Rendimento annuale al netto delle tasse (nella valuta del titolo).")
                    c3.metric("Rend. Lordo", f"{risk['ytm']:.2f}%", help="Yield to Maturity lordo.")
                    c4.metric("Cedola", f"{d['ced']}%", help="Interesse periodico pagato.")
                    c5.metric("Valuta", valuta_bond, help="Valuta di denominazione del titolo.")
                    c6.metric("Duration", f"{risk['mod_dur']:.2f} Anni", help="Sensibilità ai tassi.")

                    st.divider()
                    
                    # === 💰 SIMULATORE AVANZATO ===
                    st.subheader("💰 Simulatore & Stress Test")
                    
                    col_set1, col_set2, col_set3 = st.columns(3)
                    with col_set1:
                        # Lista Valute Estesa
                        liste_valute = ["EUR", "USD", "GBP", "CHF", "TRY", "BRL", "RON", "JPY", "CAD", "AUD"]
                        valuta_user = st.selectbox("La tua Valuta (Conto)", liste_valute, index=0)
                    
                    with col_set2:
                        importo_user = st.number_input(f"Capitale da Investire ({valuta_user})", value=10000.0, step=1000.0)
                    with col_set3:
                        infl_sim = st.number_input("Inflazione Stimata %", value=2.0, step=0.5)

                    # Recupero Tasso Live
                    tasso_spot = get_tasso_cambio_live(valuta_user, valuta_bond)
                    
                    # --- CONFIGURAZIONE SLIDER ADATTIVA + BOX INFO ---
                    if valuta_user != valuta_bond:
                        if valuta_bond in ["TRY", "ARS", "RUB"]:
                            slider_step = 5; slider_min = -80; slider_max = 20
                            risk_txt = "ALTISSIMO. Queste valute possono crollare del 50% in un anno."
                            suggested_test = "-40% o -50%"
                        elif valuta_bond in ["BRL", "ZAR", "MXN", "RON"]:
                            slider_step = 2; slider_min = -50; slider_max = 20
                            risk_txt = "ALTO. Valute emergenti soggette a forti oscillazioni."
                            suggested_test = "-20% o -25%"
                        else: # USD, GBP, CHF, CAD, AUD, JPY
                            slider_step = 1; slider_min = -30; slider_max = 20
                            risk_txt = "MEDIO-BASSO. Valute solide, ma attenzione ai cicli."
                            suggested_test = "-10% o -15%"

                        st.caption(f"📡 Tasso LIVE: 1 {valuta_user} = {tasso_spot:.4f} {valuta_bond}")
                        st.divider()
                        
                        # Box Guida Dinamico
                        c_ux1, c_ux2 = st.columns([2, 1])
                        with c_ux1:
                            st.info(f"""
                            **💡 Analisi Rischio: {valuta_bond}**
                            Volatilità storica: **{risk_txt}**
                            👉 **Consiglio:** Imposta lo slider a **{suggested_test}** per uno stress test realistico.
                            """)
                        
                        # Slider Adattivo
                        scenario_fx = st.slider(
                            f"📉 Stress Test: Variazione {valuta_bond} a scadenza", 
                            min_value=slider_min, max_value=slider_max, value=0, 
                            step=slider_step, format="%d%%"
                        )
                        
                        if scenario_fx < 0:
                            st.warning(f"⚠️ STRESS TEST: Simuli che il **{valuta_bond} perda il {abs(scenario_fx)}%**.")
                        elif scenario_fx > 0:
                            st.success(f"📈 SCENARIO OTTIMISTA: Simuli un apprezzamento del **{valuta_bond}**.")
                    else:
                        scenario_fx = 0
                        
                    # --- CALCOLI FINANZIARI SIMULATORE ---
                    nominale_bond = importo_user * tasso_spot 
                    commissioni = 5.0 
                    
                    df_flussi, spesa_loc, incasso_loc, rateo_loc, tot_ced_loc, _ = genera_flussi_dettagliati(d, nominale_bond, tax, 0, d['pr'])
                    
                    rate_rientro = tasso_spot * (1 - (scenario_fx/100)) if valuta_user != valuta_bond else 1.0
                    if rate_rientro <= 0.001: rate_rientro = 0.001
                    
                    # Conversione flussi
                    df_flussi['Importo_User'] = df_flussi.apply(
                        lambda x: (x['Importo'] / tasso_spot) if x['Tipo'] == 'USCITA' else (x['Importo'] / rate_rientro), axis=1
                    )
                    
                    spesa_reale_user = importo_user + commissioni
                    costo_titolo_user = (nominale_bond * d['pr'] / 100) / tasso_spot
                    rateo_user = rateo_loc / tasso_spot
                    incasso_reale_user = df_flussi[df_flussi['Tipo'] == 'ENTRATA']['Importo_User'].sum()
                    cedole_tot_user = tot_ced_loc / rate_rientro
                    rimborso_user = (nominale_bond) / rate_rientro 
                    guadagno_netto_user = incasso_reale_user - spesa_reale_user
                    
                    # -- CALCOLO ROI TOTALE E ROI ANNUO --
                    roi_pct_totale = (guadagno_netto_user / spesa_reale_user) * 100
                    
                    # Calcolo anni residui per annualizzare il rendimento
                    giorni_residui = (d['sc'] - date.today()).days
                    anni_residui = max(giorni_residui / 365.25, 0.1) # Evita division by zero
                    
                    # Formula Interesse Composto Annualizzato (CAGR)
                    if spesa_reale_user > 0 and incasso_reale_user > 0:
                        roi_annuo = ((incasso_reale_user / spesa_reale_user) ** (1 / anni_residui) - 1) * 100
                    else:
                        roi_annuo = -100 # Perdita totale

                    # --- SCONTRINO (STILE HTML PREMIUM) ---
                    st.write("")
                    st.markdown(f"### 🧾 Analisi Flussi di Cassa (In {valuta_user})")
                    col_usc, col_entr = st.columns(2)
                    
                    with col_usc:
                        st.markdown(f"""
                        <div class="receipt-box" style="border-left: 4px solid #FF4B4B; background-color: rgba(255, 75, 75, 0.05); padding: 15px; border-radius: 8px;">
                            <div style="font-weight:bold; color:#FF4B4B; margin-bottom:10px; font-size:14px;">📉 USCITE (OGGI al tasso {tasso_spot:.2f})</div>
                            <div class="receipt-row" style="display:flex; justify-content:space-between; margin-bottom:5px;"><span>Costo Titoli:</span> <span>{costo_titolo_user:,.2f} {valuta_user}</span></div>
                            <div class="receipt-row" style="display:flex; justify-content:space-between; margin-bottom:5px;"><span>Rateo Interessi:</span> <span>{rateo_user:,.2f} {valuta_user}</span></div>
                            <div class="receipt-row" style="display:flex; justify-content:space-between; margin-bottom:5px;"><span>Commissioni:</span> <span>{commissioni:,.2f} {valuta_user}</span></div>
                            <hr style="margin: 10px 0; border-color: #444;">
                            <div class="receipt-total" style="color: #FF4B4B; font-size:16px; font-weight:bold; display:flex; justify-content:space-between;">
                                <span>TOTALE ADDEBITO:</span> <span>-{spesa_reale_user:,.2f} {valuta_user}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_entr:
                        color_res = "#00CC96" if guadagno_netto_user > 0 else "#FF4B4B"
                        tasso_futuro_lbl = f"{rate_rientro:.2f}" if valuta_user != valuta_bond else "Invariato"
                        
                        st.markdown(f"""
                        <div class="receipt-box" style="border-left: 4px solid {color_res}; background-color: rgba(0, 204, 150, 0.05); padding: 15px; border-radius: 8px;">
                            <div style="font-weight:bold; color:{color_res}; margin-bottom:10px; font-size:14px;">📈 ENTRATE (FUTURO al tasso {tasso_futuro_lbl})</div>
                            <div class="receipt-row" style="display:flex; justify-content:space-between; margin-bottom:5px;"><span>Cedole Nette Totali:</span> <span>+{cedole_tot_user:,.2f} {valuta_user}</span></div>
                            <div class="receipt-row" style="display:flex; justify-content:space-between; margin-bottom:5px;"><span>Rimborso Capitale:</span> <span>+{rimborso_user:,.2f} {valuta_user}</span></div>
                            <div class="receipt-row" style="color:#888; font-size:12px; display:flex; justify-content:space-between; margin-bottom:5px;"><span>(Effetto Cambio: {scenario_fx}%)</span> <span></span></div>
                            <hr style="margin: 10px 0; border-color: #444;">
                            <div class="receipt-total" style="color: {color_res}; font-size:16px; font-weight:bold; display:flex; justify-content:space-between;">
                                <span>TOTALE INCASSO:</span> <span>+{incasso_reale_user:,.2f} {valuta_user}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    
   # -- CALCOLO FORMATTAZIONE TEMPORALE --
                    giorni_residui = (d['sc'] - date.today()).days
                    anni_residui = giorni_residui / 365.25
                    str_durata = f"{anni_residui:.1f} anni" if anni_residui >= 1 else f"{giorni_residui} giorni"

                    # VERDETTO FINALE (PRIORITÀ AL RENDIMENTO ANNUO)
                    st.divider()
                    if guadagno_netto_user > 0:
                        st.success(
                            f"✅ **GUADAGNO NETTO:** +{guadagno_netto_user:,.2f} {valuta_user}\n\n"
                            f"📊 **Rendimento Annuo Reale: +{roi_annuo:.2f}%**\n"
                            f"*(Rendimento Cumulato Totale: +{roi_pct_totale:.2f}% spalmato su {str_durata})*"
                        )
                    else:
                        st.error(
                            f"❌ **PERDITA STIMATA:** {guadagno_netto_user:,.2f} {valuta_user}\n\n"
                            f"📉 **Rendimento Annuo Reale: {roi_annuo:.2f}%**\n"
                            f"*(Perdita Cumulata Totale: {roi_pct_totale:.2f}% su {str_durata})*"
                        )
                    # --- GRAFICO BREAKEVEN (LINEE COLORATE + STELLA + PUNTO ZERO) ---
                    # --- GRAFICO BREAKEVEN (CON TESTO COMPLETO) ---
                    st.subheader("🗓️ Recupero Capitale nel Tempo")
                    df_flussi['Cumulativo'] = df_flussi['Importo_User'].cumsum()
                    
                    df_neg = df_flussi[df_flussi['Cumulativo'] < 0].copy()
                    df_pos = df_flussi[df_flussi['Cumulativo'] >= 0].copy()
                    
                    breakeven_date = None
                    if not df_neg.empty and not df_pos.empty:
                        last_neg = df_neg.iloc[-1]; first_pos = df_pos.iloc[0]
                        y1, y2 = last_neg['Cumulativo'], first_pos['Cumulativo']
                        x1, x2 = last_neg['Data'].toordinal(), first_pos['Data'].toordinal()
                        if y2 != y1:
                            x_zero = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
                            breakeven_date = date.fromordinal(int(x_zero))
                            row_zero = pd.DataFrame({'Data': [breakeven_date], 'Cumulativo': [0]})
                            df_neg = pd.concat([df_neg, row_zero], ignore_index=True)
                            df_pos = pd.concat([row_zero, df_pos], ignore_index=True)

                    # QUI HO RIMESSO IL TESTO CHE VOLEVI 👇
                    if breakeven_date:
                        days_to_be = (breakeven_date - date.today()).days
                        st.markdown(f"""
                        <div style="background-color: #e6fffa; padding: 15px; border-radius: 10px; border-left: 5px solid #00CC96; color: #1e2130; margin-bottom: 10px;">
                            ✅ <b>Punto di Pareggio:</b> Raggiunto il <b>{breakeven_date.strftime('%d/%m/%Y')}</b> (tra <b style="color: #007755;">{days_to_be} giorni</b>).
                            <br>Da quel momento in poi è tutto <b>Profitto Netto</b>.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div style="background-color: #fff8e1; padding: 15px; border-radius: 10px; border-left: 5px solid #ffa500; color: #1e2130; margin-bottom: 10px;">⏳ <b>Recupero capitale</b> solo a scadenza.</div>""", unsafe_allow_html=True)

                    fig = go.Figure()
                    if not df_neg.empty: fig.add_trace(go.Scatter(x=df_neg['Data'], y=df_neg['Cumulativo'], mode='lines', line=dict(color='#FF4B4B', width=3), name='Sotto Zero'))
                    if not df_pos.empty: fig.add_trace(go.Scatter(x=df_pos['Data'], y=df_pos['Cumulativo'], mode='lines', line=dict(color='#00CC96', width=3), name='Profitto'))
                    if breakeven_date: fig.add_trace(go.Scatter(x=[breakeven_date], y=[0], mode='markers', marker=dict(color='yellow', size=12, symbol='star'), name='Pareggio'))

                    fig.add_hline(y=0, line_color='white', line_dash="dash", line_width=1)
                    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=20,r=20,t=30,b=20), hovermode="x unified", showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # --- CEDOLARIO (TABELLA SEMPRE VISIBILE E COLORATA) ---
                    st.subheader("📅 Cedolario Dettagliato")
                    def style_cedola(v): return f'color: {"#00CC96" if v >= 0 else "#FF4B4B"}; font-weight: bold;'
                    st.dataframe(
                        df_flussi[['Data', 'Tipo', 'Importo', 'Importo_User', 'Dettagli']]
                        .style.format({'Importo': f'{{:+,.2f}} {valuta_bond}', 'Importo_User': f'{{:+,.2f}} {valuta_user}'})
                        .map(style_cedola, subset=['Importo', 'Importo_User']),
                        use_container_width=True
                    )

                else: st.error("❌ Nessun risultato trovato.")
# --- SMART ANALYSIS (GRAFICO MARCO + ZOOM + LIVE EXCHANGE) ---
    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Confronto")
        st.caption("Verifica se il tuo bond è un affare rispetto al mercato.")
        
        with st.spinner("Analisi mercato in corso..."):
            df_m = carica_tutto_mercato()
        
        if df_m.empty: st.warning("⚠️ Database vuoto. Aggiorna i dati."); st.stop()

        c_s, _ = st.columns([1, 2])
        isin_s = c_s.text_input("Inserisci ISIN", placeholder="IT...").strip().upper()
        
        if isin_s:
            target_bond = df_m[df_m['ISIN'] == isin_s]
            if not target_bond.empty:
                b = target_bond.iloc[0]
                ytm_target = b['YTM_Grezzo']
                try: anni_target = (pd.to_datetime(b['Scadenza']).date() - date.today()).days / 365.25
                except: anni_target = 0
                
                # --- 1. KPI VELOCI ---
                st.divider()
                k1, k2, k3 = st.columns(3)
                k1.metric("Tuo Bond (Lordo)", f"{ytm_target:.2f}%")
                
                # Filtriamo il mercato (Via gli errori e i bond > 50 anni)
                df_viz = df_m[
                    (df_m['ISIN'] != isin_s) & 
                    (df_m['YTM_Grezzo'] > -1) & (df_m['YTM_Grezzo'] < 15) &
                    (df_m['Anni'] > 0) & (df_m['Anni'] <= 50)
                ].copy()
                
                avg_cat = df_viz[df_viz['Tipo'] == b['Tipo']]['YTM_Grezzo'].mean()
                delta = ytm_target - avg_cat
                k2.metric(f"Media {b['Tipo']}", f"{avg_cat:.2f}%")
                k3.metric("Posizione", "Sopra Media" if delta>0 else "Sotto Media", f"{delta:.2f}%")

                # --- 2. GRAFICO SCATTER (ZOOM + COLORI) ---
                st.subheader("📍 La Mappa del Tesoro")
                
                fig = go.Figure()
                
                # Zoom intelligente su Marco
                max_x = min(max(10, anni_target * 2), 50)
                max_y = max(ytm_target + 3, 8)
                
                palette = {
                    "Governativo": "rgba(34, 139, 34, 0.7)", "Bancario": "rgba(30, 144, 255, 0.7)",
                    "Corporate": "rgba(255, 140, 0, 0.7)", "Speciali": "rgba(138, 43, 226, 0.7)",
                    "Altro": "rgba(102, 51, 153, 0.6)" # VIOLA SCURO VISIBILE
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
                
                # --- 3. TABELLA ALTERNATIVE (FIX) ---
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
    # --- SCREENER AVANZATO (FILTRI VALUTA + CONVERSIONE PREZZI) ---
 # --- SCREENER AVANZATO (INPUT MANUALI + TUTTE LE VALUTE) ---
# --- SCREENER AVANZATO (ALL SELECTED DEFAULT + RISCHIO CAMBIO) ---
    elif st.session_state.page == "Screener":
        st.title("⚡ Screener Avanzato")
        st.caption("Tutto il mercato a colpo d'occhio. Filtra per escludere.")
        
        # 1. Caricamento Dati
        with st.spinner("Caricamento database bond..."):
            df = carica_tutto_mercato()
            
        if df.empty:
            st.warning("⚠️ Database vuoto. Clicca 'Aggiorna Dati' nella sidebar.")
            st.stop()

        # 2. Arricchimento Dati
        if 'Valuta' not in df.columns:
            df['Valuta'] = df.apply(lambda x: detect_valuta(x['Descrizione'], x['ISIN']), axis=1)

        # ---------------------------------------------------------------------
        # BARRA DEI FILTRI (LOGICA "TUTTO INCLUSO")
        # ---------------------------------------------------------------------
        with st.expander("🎛️ FILTRI DI RICERCA", expanded=True):
            
            r1_c1, r1_c2, r1_c3 = st.columns(3)
            
            with r1_c1:
                # DEFAULT: TUTTE LE VALUTE SELEZIONATE
                all_currencies = sorted(df['Valuta'].unique().tolist())
                sel_currencies = st.multiselect(
                    "1. Valute (Deseleziona per escludere)", 
                    all_currencies, 
                    default=all_currencies # <--- TUTTO SELEZIONATO DI DEFAULT
                )
                
            with r1_c2:
                # DEFAULT: TUTTE LE CATEGORIE SELEZIONATE
                all_cats = list(MACRO_CATEGORIES.keys())
                sel_cat = st.multiselect(
                    "2. Categorie (Deseleziona per escludere)", 
                    all_cats, 
                    default=all_cats # <--- TUTTO SELEZIONATO DI DEFAULT
                )
                
            with r1_c3:
                # VALUTA DI CONFRONTO (Il tuo conto)
                target_currency = st.selectbox(
                    "3. Il tuo Conto è in...", 
                    ["EUR", "USD", "GBP", "CHF"], 
                    index=0,
                    help="I prezzi verranno convertiti in questa valuta per farti capire quanto paghi davvero."
                )

            st.divider()
            
            # FILTRI NUMERICI MANUALI
            col_y, col_d, col_p = st.columns(3)
            
            with col_y:
                st.markdown("📊 **Rendimento Lordo %**")
                c_min, c_max = st.columns(2)
                min_y = c_min.number_input("Min %", value=0.0, step=0.5)
                max_y = c_max.number_input("Max %", value=100.0, step=0.5)

            with col_d:
                st.markdown("📅 **Scadenza (Anni)**")
                c_min, c_max = st.columns(2)
                min_d = c_min.number_input("Min Anni", value=0.0, step=1.0)
                max_d = c_max.number_input("Max Anni", value=50.0, step=1.0)

            with col_p:
                st.markdown("💰 **Prezzo Mercato**")
                c_min, c_max = st.columns(2)
                min_p = c_min.number_input("Min Prezzo", value=0.0, step=1.0)
                max_p = c_max.number_input("Max Prezzo", value=200.0, step=1.0)

        # ---------------------------------------------------------------------
        # LOGICA DI FILTRAGGIO
        # ---------------------------------------------------------------------
        # Se l'utente toglie tutto, mostriamo lista vuota o tutto? Meglio gestire l'errore.
        if not sel_currencies or not sel_cat:
            st.warning("⚠️ Seleziona almeno una Valuta e una Categoria.")
            st.stop()

        df_filt = df[
            (df['Valuta'].isin(sel_currencies)) &
            (df['Tipo'].isin(sel_cat)) &
            (df['YTM_Grezzo'] >= min_y) & (df['YTM_Grezzo'] <= max_y) &
            (df['Anni'] >= min_d) & (df['Anni'] <= max_d) &
            (df['Prezzo'] >= min_p) & (df['Prezzo'] <= max_p)
        ]

        # 4. CONVERSIONE PREZZI & LOGICA RISCHIO
        if not df_filt.empty:
            # Cache del cambio per velocizzare
            tassi_cache = {curr: get_tasso_cambio_live(target_currency, curr) for curr in df_filt['Valuta'].unique() if curr != target_currency}
            
            def processa_riga_display(row):
                # 1. Conversione Prezzo
                valuta_bond = row['Valuta']
                if valuta_bond == target_currency:
                    pz_conv = row['Prezzo']
                    note = "✅ Cambio Diretto"
                else:
                    rate = tassi_cache.get(valuta_bond, 1.0)
                    pz_conv = row['Prezzo'] / rate if rate > 0 else 0
                    note = "⚠️ Rischio Cambio"
                
                return pd.Series([pz_conv, note])

            df_filt[['Prezzo_Display', 'Note_Rischio']] = df_filt.apply(processa_riga_display, axis=1)
        
        # ---------------------------------------------------------------------
        # VISUALIZZAZIONE RISULTATI
        # ---------------------------------------------------------------------
        st.divider()
        st.subheader(f"🔍 Trovati {len(df_filt)} Bond")

        if not df_filt.empty:
            # Ordinamento: Default per Rendimento, ma evidenziamo il rischio
            df_filt = df_filt.sort_values(by='YTM_Grezzo', ascending=False)
            
            # Preparazione Tabella Finale
            df_show = df_filt[['ISIN', 'Descrizione', 'Tipo', 'Valuta', 'Note_Rischio', 'Prezzo_Display', 'Scadenza', 'YTM_Grezzo']].copy()
            
            st.dataframe(
                df_show.style.format({
                    'Prezzo_Display': f'{{:.2f}} {target_currency}', 
                    'YTM_Grezzo': '{:.2f}%',
                    'Scadenza': '{:%d/%m/%Y}'
                })
                .map(lambda v: 'color: orange; font-weight: bold;' if v == '⚠️ Rischio Cambio' else 'color: green;', subset=['Note_Rischio'])
                .background_gradient(subset=['YTM_Grezzo'], cmap='Greens'),
                use_container_width=True,
                height=600,
                column_config={
                    "Prezzo_Display": st.column_config.NumberColumn(
                        f"Prezzo Reale ({target_currency})", 
                        help=f"Quanto paghi effettivamente in {target_currency} oggi."
                    ),
                    "YTM_Grezzo": st.column_config.NumberColumn(
                        "Rendimento Lordo (Nominale)",
                        help="Attenzione: è il rendimento nella valuta del bond! Se la valuta crolla, questo rendimento in Euro sparisce."
                    ),
                    "Note_Rischio": st.column_config.TextColumn("Info Cambio"),
                    "Valuta": st.column_config.TextColumn("Valuta", width="small")
                }
            )
            
            # Analisi Rapida
            st.write("")
            st.markdown("### 🚀 Analizza nel dettaglio")
            c1, c2 = st.columns([3, 1])
            with c1: isin_input = st.text_input("Incolla ISIN per simulazione cambio", placeholder="IT...").strip().upper()
            with c2: 
                st.write(""); 
                if st.button("Vai allo Scanner 👉"):
                    if isin_input:
                        st.session_state.selected_isin_from_chart = isin_input
                        st.session_state.page = "Scanner"
                        st.rerun()
        else:
            st.info("Nessun bond trovato. Prova ad allargare i filtri numerici.")
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_portfolio_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()

if st.session_state.logged_in: main_app()
else: login()
