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

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA E STILI CSS (ESTESO)
# ==============================================================================

st.set_page_config(
    page_title="Bond Research Terminal Pro", 
    page_icon="🏛️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Blocco CSS Esteso per Design Professionale
st.markdown("""
<style>
    /* --- FONTS & GLOBAL --- */
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
    
    .stApp {
        background-color: #0e1117;
    }

    /* --- CARD METRICHE (KPI) --- */
    .metric-card { 
        background-color: #1e2130; 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid #3e445b; 
        margin-bottom: 15px; 
        color: #ffffff !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #00CC96;
    }
    .metric-label {
        font-size: 12px;
        color: #b0b3c5;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: white;
    }

    /* --- SCONTRINO SIMULATORE --- */
    .receipt-box { 
        padding: 20px; 
        border-radius: 12px; 
        background-color: #161924; 
        border: 1px dashed #555; 
        margin-bottom: 20px; 
    }
    .receipt-row { 
        display: flex; 
        justify-content: space-between; 
        margin-bottom: 8px; 
        font-size: 15px; 
        color: #e0e0e0; 
        font-family: 'Roboto Mono', monospace;
    }
    .receipt-total { 
        display: flex; 
        justify-content: space-between; 
        margin-top: 15px; 
        padding-top: 10px; 
        border-top: 2px solid #555; 
        font-weight: bold; 
        font-size: 18px; 
    }

    /* --- SIDEBAR CUSTOM --- */
    [data-testid="stSidebar"] {
        background-color: #11141d;
        border-right: 1px solid #333;
    }
    [data-testid="stSidebar"] div.stButton > button { 
        background-color: transparent; 
        border: none; 
        text-align: left; 
        color: #e0e0e0 !important; 
        font-weight: 500;
        width: 100%;
        padding: 10px;
        margin-bottom: 2px;
    }
    [data-testid="stSidebar"] div.stButton > button:hover { 
        background-color: #262730; 
        color: #00CC96 !important;
        border-left: 3px solid #00CC96;
        padding-left: 7px;
    }
    
    /* --- BOX UTENTE --- */
    .user-box { 
        padding: 15px; 
        background: linear-gradient(90deg, #1b2d24 0%, #0e1117 100%); 
        border-left: 5px solid #00CC96; 
        border-radius: 5px; 
        margin-bottom: 25px; 
    }
    
    /* --- LEGENDA CATEGORIE --- */
    .cat-card {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: white; 
        transition: all 0.3s ease;
    }
    .cat-card:hover { filter: brightness(1.2); }
    .cat-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; }
    .cat-desc { font-size: 13px; opacity: 0.8; line-height: 1.4; }
    
    .bg-gov { background: linear-gradient(135deg, #1a4a2e 0%, #28a745 100%); }
    .bg-bank { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); }
    .bg-corp { background: linear-gradient(135deg, #1e3a5f 0%, #17a2b8 100%); }
    .bg-spec { background: linear-gradient(135deg, #581845 0%, #d63384 100%); }

    /* --- FLAGS & ALERTS --- */
    .red-flag { border-left: 5px solid #ff4b4b; background-color: rgba(255, 75, 75, 0.1); padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .green-flag { border-left: 5px solid #00cc96; background-color: rgba(0, 204, 150, 0.1); padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .warning-flag { border-left: 5px solid #ffa500; background-color: rgba(255, 165, 0, 0.1); padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    
    .main-header { font-size: 28px; font-weight: bold; color: white; letter-spacing: -1px; }
    .sub-header { font-size: 14px; color: #b0b3c5; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIGURAZIONE AVANZATA UTENTI & PERSISTENZA
# ==============================================================================

# Credenziali in chiaro (Vengono cifrate a runtime)
UTENTI_IN_CHIARO = {
    "giulio": "Giulio99mac!",
    "lorex": "mifumoleboix",
    "guest": "ospite123",
    "admin": "adminroot"
}

# Generazione Hash SHA256 per sicurezza
UTENTI_ABILITATI = {
    user: hashlib.sha256(pwd.encode()).hexdigest() 
    for user, pwd in UTENTI_IN_CHIARO.items()
}

# Configurazione Cartella Database
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# Inizializzazione Stato Sessione (State Management)
def init_session_state():
    """Inizializza tutte le variabili di sessione necessarie"""
    defaults = {
        'portfolio': [],          # Lista dei bond in portafoglio
        'confronto': None,        # Bond salvato per confronto
        'logged_in': False,       # Stato login
        'current_user': "",       # Nome utente attivo
        'connection_status': "In attesa...", # Stato rete
        'page': "Scanner",        # Pagina corrente
        'last_scrape_time': None, # Timestamp ultimo aggiornamento
        'scrape_count': 0,        # Contatore aggiornamenti
        'alerts': [],             # Lista alert attivi
        'patrimonio': 50000.0,    # Patrimonio per simulazioni
        'selected_isin': None     # ISIN selezionato dai grafici
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ==============================================================================
# 3. MAPPA FONTI ESTESA (29 Dataset)
# ==============================================================================

SOURCES_MAP = {
    "GOV_IT": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BTP_FUTURA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=btpfutura&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CCT_EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cct&yieldtype=G&timescale=DUR", "freq": 2}
    ],
    "GOV_CORE_EU": [
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT_FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUSTRIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=austria&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OLANDA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=olanda&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BELGIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=belgio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "GOV_PERIPHERY": [
        {"nome": "SPAGNA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=spagna&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "PORTOGALLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=portogallo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "GOV_WORLD": [
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "UK_GILTS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=uk&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNGHERIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=ungheria&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TURCHIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=turchia&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "FINANCIALS": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA_SP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_EUROPE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY_OIL", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "SPECIAL": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbonds&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# Categorie UI per filtro
MACRO_CATEGORIES = {
    "🌐 TUTTE": [], 
    "🏛️ GOVERNATIVI": ["GOV_IT", "GOV_CORE_EU", "GOV_PERIPHERY", "GOV_WORLD"],
    "🏦 BANCARI": ["FINANCIALS"],
    "🏭 CORPORATE": ["CORPORATE"],
    "💎 SPECIALI": ["SPECIAL"]
}

# ==============================================================================
# 4. FUNZIONI HELPER & VALIDAZIONE
# ==============================================================================

def valida_isin(isin):
    """Verifica formato ISIN: 2 lettere + 10 alfanumerici"""
    if not isin or len(isin) != 12: return False
    return isin[:2].isalpha() and isin[2:].isalnum()

def get_last_update_time():
    """Recupera timestamp dell'ultimo file CSV modificato"""
    try:
        if not os.path.exists(DB_FOLDER): return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: return None
        return datetime.fromtimestamp(os.path.getmtime(max(files, key=os.path.getmtime)))
    except: return None

def check_connection_status():
    """Ping veloce per verificare connettività"""
    try:
        requests.get("https://www.google.com", timeout=3)
        return "🟢 ONLINE"
    except: return "🔴 OFFLINE"

def pulisci_taglio(valore):
    """Normalizza il taglio minimo (es. '100k' -> 100000.0)"""
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

def get_inflazione_ufficiale():
    """Restituisce inflazione target BCE"""
    return 2.0, "Target BCE"

# ==============================================================================
# 5. DATA PROCESSING & PARSING
# ==============================================================================

def processa_riga(row, info):
    """
    Trasforma una riga grezza di Pandas in un dizionario strutturato.
    Gestisce errori di formato, valuta date e pulisce i numeri.
    """
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        
        # Mappatura intelligente colonne
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        c_isin = next((c for c in cols if 'isin' in str(c).lower()), None)
        
        if not all([c_pr, c_sc, c_de]): return None
        
        # Parsing Prezzo
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        if pr <= 0: return None
        
        # Parsing Scadenza
        sc_str = str(row[c_sc]).strip()
        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: 
            try: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
            except: return None
        if sc <= date.today(): return None
        
        # Parsing Descrizione e Cedola
        desc = str(row[c_de])
        ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        # Parsing Taglio
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]): taglio = pulisci_taglio(row[c_min])
        
        # Rating
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""
        
        return {
            "desc": descrizione_pulita(desc), 
            "pr": pr, 
            "sc": sc, 
            "ced": ced, 
            "freq": info['freq'], 
            "fonte": info['nome'], 
            "taglio": taglio, 
            "rating": rating,
            "isin": isin_val
        }
    except: return None

def descrizione_pulita(text):
    """Rimuove caratteri strani dalla descrizione"""
    return text.replace("â‚¬", "€").strip()

def aggiorna_db():
    """
    Scarica i file CSV da tutte le fonti mappate.
    Include delay anti-ban e gestione errori.
    """
    now = datetime.now()
    if st.session_state.last_scrape_time and (now - st.session_state.last_scrape_time).total_seconds() < 300:
        st.warning("⏳ Attendi qualche minuto prima di riaggiornare.")
        return
            
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_sources = sum(len(v) for v in SOURCES_MAP.values())
    c = 0
    ok = 0
    
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1
            status_text.text(f"📥 Download: {src['nome']} ({c}/{total_sources})")
            progress_bar.progress(c / total_sources)
            try:
                time.sleep(random.uniform(2, 4)) # Delay Anti-Ban
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                r = requests.get(src['url'], headers=headers, timeout=20)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1
                        break
            except Exception as e:
                print(f"Errore su {src['nome']}: {e}")
                
    st.session_state.last_scrape_time = now
    st.session_state.scrape_count += 1
    status_text.empty()
    progress_bar.empty()
    st.success(f"✅ Aggiornamento completato: {ok}/{total_sources} file scaricati.")
    time.sleep(2)
    st.rerun()

def cerca_db(isin, cat_macro):
    """
    Cerca un ISIN nel database locale.
    Supporta filtro per macro-categoria.
    """
    if not valida_isin(isin): return None, None
    
    # Determina quali file cercare
    search_keys = []
    if not cat_macro or cat_macro == "🌐 TUTTE":
        search_keys = list(SOURCES_MAP.keys())
    elif cat_macro in MACRO_CATEGORIES:
        search_keys = MACRO_CATEGORIES[cat_macro]
    
    for key in search_keys:
        sources = SOURCES_MAP.get(key, [])
        for src in sources:
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): continue
            try:
                df = pd.read_csv(path)
                col_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col_isin:
                    mask = df[col_isin].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any(): return df[mask].iloc[0], src
            except: continue
    return None, None

def calcola_rendimento_grezzo(prezzo, cedola, scadenza):
    """Calcola un YTM approssimato per le liste lunghe (veloce)"""
    try:
        anni = (scadenza - date.today()).days / 365.25
        if anni <= 0 or prezzo <= 0: return 0
        gain_annuo = (100 - prezzo) / anni
        rendimento = (cedola + gain_annuo) / prezzo * 100
        return round(rendimento, 2)
    except: return 0

@st.cache_data(ttl=3600)
def carica_tutto_mercato():
    """
    Carica tutti i CSV in un unico DataFrame per Screener e Dashboard.
    Ottimizzato con Cache.
    """
    all_data = []
    if not os.path.exists(DB_FOLDER): return pd.DataFrame()
    
    for filename in os.listdir(DB_FOLDER):
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(DB_FOLDER, filename))
                # Trova colonne
                c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
                c_sc = next((c for c in df.columns if 'scadenza' in str(c).lower()), None)
                c_isin = next((c for c in df.columns if 'isin' in str(c).lower()), None)
                c_desc = next((c for c in df.columns if 'desc' in str(c).lower()), None)
                
                if all([c_pr, c_sc, c_isin, c_desc]):
                    df = df.dropna(subset=[c_pr, c_sc])
                    # Standardizza
                    df['Prezzo'] = pd.to_numeric(df[c_pr].astype(str).str.replace(',','.').str.replace('€',''), errors='coerce')
                    df['ISIN'] = df[c_isin]
                    df['Descrizione'] = df[c_desc]
                    df['Fonte'] = filename.replace('.csv', '')
                    
                    # Parsing data
                    df['Scadenza'] = pd.to_datetime(df[c_sc], dayfirst=True, errors='coerce').dt.date
                    df = df.dropna(subset=['Scadenza'])
                    
                    # Categoria Semplificata
                    if "BTP" in filename or "BOT" in filename: df['Tipo'] = 'Governativo'
                    elif "CORP" in filename: df['Tipo'] = 'Corporate'
                    elif "BANCHE" in filename: df['Tipo'] = 'Bancario'
                    else: df['Tipo'] = 'Altro'
                    
                    # Cedola approssimata per YTM veloce
                    df['Cedola_Approx'] = df['Descrizione'].str.extract(r'(\d+(?:[.,]\d+)?)%').astype(float).fillna(0)
                    df['YTM_Grezzo'] = df.apply(lambda x: calcola_rendimento_grezzo(x['Prezzo'], x['Cedola_Approx'], x['Scadenza']), axis=1)
                    
                    all_data.append(df[['ISIN', 'Descrizione', 'Prezzo', 'Tipo', 'Fonte', 'YTM_Grezzo', 'Scadenza']])
            except: continue
            
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

# ==============================================================================
# 6. RISK ENGINE & MATEMATICA FINANZIARIA (CORE)
# ==============================================================================

def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """
    Calcola lo Yield to Maturity (YTM) usando il metodo numerico Newton-Raphson.
    Include controllo errori e stime fallback.
    """
    if prezzo <= 0 or freq == 0: return None
    cedola_annua = cedola_pct / 100
    giorni = (scadenza - date.today()).days
    anni = giorni / 365.25
    if anni <= 0: return None
    
    n_periodi = max(1, int(anni * freq))
    c = (cedola_annua * face_value) / freq
    
    # Stima iniziale (Yield corrente + Capital Gain linearizzato)
    ytm_guess = (cedola_annua + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
    
    def price_func(y):
        if y <= -1: return float('inf')
        pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n_periodi + 1)])
        pv += face_value / ((1 + y/freq) ** n_periodi)
        return pv - prezzo
    
    def price_deriv(y):
        if y <= -1: return 0
        dpv = sum([-t * c / (freq * ((1 + y/freq) ** (t + 1))) for t in range(1, n_periodi + 1)])
        dpv += -n_periodi * face_value / (freq * ((1 + y/freq) ** (n_periodi + 1)))
        return dpv
    
    try:
        ytm = newton(price_func, ytm_guess, fprime=price_deriv, maxiter=50, tol=1e-6)
        return max(0, ytm)
    except: return ytm_guess

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """
    Calcola il set completo di metriche di rischio:
    - Macaulay Duration
    - Modified Duration (Sensibilità)
    - Convexity (Curvatura)
    - DV01 (Dollar Value of 01)
    """
    if prezzo <= 0: return None
    ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value)
    if ytm is None: return None
    
    cedola = cedola_pct / 100
    anni = (scadenza - date.today()).days / 365.25
    n_periodi = max(1, int(anni * freq))
    
    if freq > 0:
        t = np.arange(1, n_periodi + 1) / freq
        cf = np.full(n_periodi, (cedola * face_value) / freq)
        cf[-1] += face_value
    else:
        t = np.array([anni]); cf = np.array([face_value]); freq = 1
    
    df = (1 + ytm / freq) ** (-t * freq)
    mac_dur = np.sum(t * cf * df) / prezzo
    mod_dur = mac_dur / (1 + ytm / freq)
    convexity = np.sum(cf * t * (t + 1/freq) * ((1 + ytm/freq) ** (-(t * freq + 2)))) / prezzo
    dv01 = mod_dur * prezzo * 0.0001
    
    return {"ytm": ytm * 100, "mod_dur": mod_dur, "convexity": convexity, "dv01": dv01, "mac_dur": mac_dur}

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    """
    Simula il prezzo del bond al variare dei tassi (Shock Analysis).
    Usa espansione di Taylor di secondo ordine (Dur + Conv).
    """
    shock = shock_bps / 10000
    delta = (-mod_dur * shock + 0.5 * convexity * (shock ** 2)) * prezzo
    return prezzo + delta

def determina_tasse(nome, desc):
    """Restituisce l'aliquota fiscale (12.5% White List, 26% Altri)"""
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "REPUBLIC", "TREASURY", "BEI", "EIB"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

# ==============================================================================
# 7. FLUSSI DI CASSA & SIMULATORE AVANZATO
# ==============================================================================

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    """
    Genera il piano di ammortamento completo per il bond.
    Calcola ratei, cedole nette, e capital gain.
    """
    flussi = []
    
    # 1. Calcolo Rateo (Interessi maturati da pagare al venditore)
    today_dt = date.today()
    rateo_pct = 0.0
    if dati['freq'] > 0:
        days_ced = 365 / dati['freq']
        data_ced = dati['sc']
        while data_ced > today_dt:
            data_ced -= timedelta(days=int(days_ced))
        # Rateo semplice
        rateo_pct = (dati['ced'] / dati['freq']) * ((today_dt - data_ced).days / days_ced)
        rateo_pct = max(0, rateo_pct)
    
    # 2. Calcolo Uscita Iniziale
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_netto = (nominale * rateo_pct / 100) * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    
    flussi.append({
        "Data": date.today(), "Tipo": "USCITA", 
        "Importo": -spesa_totale, 
        "Dettagli": "Acquisto (Prezzo + Rateo + Comm.)"
    })
    
    # 3. Generazione Cedole Future
    totale_cedole_nette = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = dati['sc']
        while curr > date.today() + timedelta(days=2):
            if curr != dati['sc']: 
                flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola Periodica"})
                totale_cedole_nette += cedola_netta
            curr -= timedelta(days=int(365 / dati['freq']))
    
    # 4. Rimborso Finale & Capital Gain
    flussi.sort(key=lambda x: x['Data'])
    
    prezzo_rimborso = 100.0 # Assumiamo rimborso alla pari
    gain = max(0, prezzo_rimborso - prezzo_acquisto)
    tassa_gain = (gain / 100) * nominale * (tax_rate/100)
    rimborso_netto = (nominale * prezzo_rimborso / 100) - tassa_gain
    
    # Ultima cedola (se c'è)
    ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    
    flussi.append({
        "Data": dati['sc'], "Tipo": "ENTRATA", 
        "Importo": rimborso_netto + ultima_ced, 
        "Dettagli": "Rimborso Capitale + Ultima Cedola"
    })
    
    incasso_totale = totale_cedole_nette + rimborso_netto + ultima_ced
    plusvalenza_netta = (gain/100)*nominale - tassa_gain
    
    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza_netta

def analizza_bond_quality(dati, risk, tax):
    """Assegna score e bandierine di avviso"""
    flags = []; score = 100
    
    # Taglio
    if dati['taglio'] > 100000: flags.append(("red", "Taglio > 100k")); score -= 20
    elif dati['taglio'] > 50000: flags.append(("warning", "Taglio > 50k")); score -= 10
    
    # Prezzo
    if dati['pr'] > 110: flags.append(("red", "Prezzo > 110")); score -= 15
    elif dati['pr'] > 105: flags.append(("warning", "Prezzo > 105")); score -= 5
    
    # Rendimento
    ytm_net = risk['ytm'] * (1 - tax / 100) if risk else 0
    if ytm_net < 2.0: flags.append(("warning", "Rendimento Basso")); score -= 10
    elif ytm_net > 4.0: flags.append(("green", "Rendimento Ottimo")); score += 10
    
    # Duration
    if risk and risk['mod_dur'] > 8: flags.append(("warning", "Alta Volatilità")); score -= 10
    
    return {"flags": flags, "score": max(0, min(100, score)), "ytm_netto": ytm_net}

# ==============================================================================
# 8. PAGINE AVANZATE (SCREENER, DASHBOARD, ALERT, DIVERSIFICAZIONE)
# ==============================================================================

def bond_screener_ui():
    """Interfaccia avanzata per filtrare database bond"""
    st.title("🎯 Bond Screener")
    
    df_all = carica_tutto_mercato()
    if df_all.empty:
        st.error("Database vuoto. Vai nella Sidebar -> Aggiorna Dati.")
        return

    # Filtri
    st.markdown("##### 🔍 Filtri di Ricerca")
    c1, c2, c3, c4 = st.columns(4)
    with c1: ytm_min = st.slider("YTM Min %", 0.0, 10.0, 3.0, 0.5)
    with c2: px_max = st.slider("Prezzo Max", 50.0, 150.0, 100.0, 1.0)
    with c3: dur_max = st.slider("Scadenza Max (Anni)", 1, 50, 10, 1)
    with c4: tipo_sel = st.multiselect("Tipo", df_all['Tipo'].unique())

    # Applicazione
    df_all['Anni'] = (pd.to_datetime(df_all['Scadenza']) - datetime.today()).dt.days / 365.25
    res = df_all[
        (df_all['YTM_Grezzo'] >= ytm_min) & 
        (df_all['Prezzo'] <= px_max) & 
        (df_all['Anni'] <= dur_max)
    ]
    if tipo_sel: res = res[res['Tipo'].isin(tipo_sel)]
    
    st.success(f"Trovati {len(res)} bond")
    st.dataframe(res, use_container_width=True)

def dashboard_mercato_ui():
    """Dashboard KPI Mercato"""
    st.title("📊 Dashboard Mercato")
    df = carica_tutto_mercato()
    
    if df.empty:
        st.warning("Nessun dato.")
        return
        
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totale Bond", len(df))
    c2.metric("YTM Medio", f"{df['YTM_Grezzo'].mean():.2f}%")
    c3.metric("Prezzo Medio", f"{df['Prezzo'].mean():.2f}€")
    c4.metric("Bond < 100 (Sotto Pari)", len(df[df['Prezzo'] < 100]))
    
    st.divider()
    
    c_ch1, c_ch2 = st.columns(2)
    with c_ch1:
        st.subheader("Distribuzione Tipologia")
        st.bar_chart(df['Tipo'].value_counts())
    
    with c_ch2:
        st.subheader("Scatter Plot: Rischio/Rendimento")
        df['Anni'] = (pd.to_datetime(df['Scadenza']) - datetime.today()).dt.days / 365.25
        # Filtro outlier
        df_clean = df[(df['YTM_Grezzo'] < 15) & (df['YTM_Grezzo'] > -2)]
        fig = px.scatter(df_clean, x='Anni', y='YTM_Grezzo', color='Tipo', hover_data=['Descrizione'], title="Curva dei Tassi Implicita")
        st.plotly_chart(fig, use_container_width=True)

def diversificazione_ui():
    """Calcolatore Bond Ladder"""
    st.title("🧮 Costruisci Portafoglio (Ladder)")
    st.info("Strategia: Dividi il capitale su scadenze diverse per ridurre il rischio.")
    
    capitale = st.number_input("Capitale Totale (€)", value=50000.0, step=1000.0)
    anni = st.slider("Orizzonte Temporale (Anni)", 3, 10, 5)
    
    steps = []
    cap_per_step = capitale / anni
    
    st.subheader("Piano di Accumulo Bond")
    for i in range(1, anni + 1):
        steps.append({
            "Scadenza": f"Tra {i} Anni",
            "Anno": date.today().year + i,
            "Importo da Investire": f"{cap_per_step:,.2f} €",
            "Obiettivo": "Reinvestire a tassi futuri"
        })
    
    st.dataframe(pd.DataFrame(steps), use_container_width=True)

def alert_manager_ui():
    """Gestione Alert (Mockup)"""
    st.title("🔔 I Miei Alert")
    
    if not st.session_state.alerts:
        st.info("Nessun alert attivo.")
    else:
        for i, a in enumerate(st.session_state.alerts):
            st.warning(f"Alert {i+1}: {a}")
            
    with st.expander("Crea Nuovo Alert"):
        isin_a = st.text_input("ISIN")
        target_p = st.number_input("Avvisami se prezzo scende sotto", value=95.0)
        if st.button("Salva Alert"):
            st.session_state.alerts.append(f"{isin_a} < {target_p}")
            st.success("Salvato")
            st.rerun()

def smart_analysis_ui():
    """Confronto intelligente tra bond"""
    st.title("🧠 Smart Analysis")
    st.write("Confronta il tuo bond con la media di mercato.")
    
    df = carica_tutto_mercato()
    if df.empty:
        st.error("Dati mancanti.")
        return
        
    isin_in = st.text_input("Inserisci ISIN da analizzare", placeholder="IT...").strip().upper()
    if isin_in:
        bond = df[df['ISIN'] == isin_in]
        if not bond.empty:
            b_data = bond.iloc[0]
            ytm_b = b_data['YTM_Grezzo']
            cat_b = b_data['Tipo']
            
            # Media categoria
            avg_cat = df[df['Tipo'] == cat_b]['YTM_Grezzo'].mean()
            
            c1, c2 = st.columns(2)
            c1.metric("Tuo Bond", f"{ytm_b:.2f}%")
            c2.metric(f"Media {cat_b}", f"{avg_cat:.2f}%", delta=f"{ytm_b-avg_cat:.2f}%")
            
            if ytm_b > avg_cat:
                st.success("✅ Questo bond rende PIÙ della media della sua categoria!")
            else:
                st.warning("⚠️ Questo bond rende MENO della media. Valuta alternative.")
        else:
            st.error("ISIN non trovato nel database aggiornato.")

# ==============================================================================
# 9. INTERFACCIA UTENTE: LOGIN & SIDEBAR
# ==============================================================================

def login():
    st.title("🔒 Bond Terminal Pro")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("---")
        u = st.text_input("Username", placeholder="es. giulio").strip()
        p = st.text_input("Password", type="password")
        if st.button("ACCEDI", use_container_width=True):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                st.success(f"Benvenuto {u}!"); time.sleep(1); st.rerun()
            else: st.error("Accesso Negato")

def main_app():
    with st.sidebar:
        st.title("🏛️ MENU")
        
        # User Box
        if st.session_state.current_user:
            st.markdown(f"""
            <div class="user-box">
                <span style="color:#aaa; font-size:12px;">UTENTE</span><br>
                <span style="color:white; font-size:16px; font-weight:bold;">👤 {st.session_state.current_user.capitalize()}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Menu Navigazione Completo
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🎯 Screener Mercato", use_container_width=True): st.session_state.page = "Screener"; st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True): st.session_state.page = "Smart"; st.rerun()
        if st.button("📊 Dashboard", use_container_width=True): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True): st.session_state.page = "Diversificazione"; st.rerun()
        if st.button("🔔 Alert Manager", use_container_width=True): st.session_state.page = "Alerts"; st.rerun()
        if st.button("⚔️ Confronto Bond", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider(); st.subheader("⚙️ SISTEMA")
        
        # Info Sistema
        last = get_last_update_time()
        if last: st.success(f"Dati: {last.strftime('%d/%m %H:%M')}")
        else: st.error("Dati: Assenti")
        
        # Aggiornamento
        if st.button("🔄 Aggiorna Dati", use_container_width=True):
            if "BANNATO" in st.session_state.connection_status: st.error("Sei bannato temporaneamente.")
            else: aggiorna_db()
            
        csv_cnt = len([f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]) if os.path.exists(DB_FOLDER) else 0
        st.caption(f"Files: {csv_cnt}/{len(SOURCES_MAP)*5}") # Approx total
        
        # Reset Protetto
        if st.session_state.current_user in ["giulio", "lorex"]:
            if st.button("🗑️ Reset DB", use_container_width=True):
                try: 
                    for f in os.listdir(DB_FOLDER): os.remove(os.path.join(DB_FOLDER,f))
                    st.toast("Pulito!"); time.sleep(1); st.rerun()
                except: pass
        
        st.divider()
        if st.button("Esci"): st.session_state.logged_in=False; st.rerun()

    # ==========================================================================
    # 10. ROUTING PAGINE
    # ==========================================================================

    # --- PAGINA: SCANNER ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Bond")
        
        # Legenda Macro
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown('<div class="cat-card bg-gov"><div class="cat-title">🏛️ GOV</div>Stati Sovrani</div>', unsafe_allow_html=True)
        c2.markdown('<div class="cat-card bg-bank"><div class="cat-title">🏦 BANK</div>Banche</div>', unsafe_allow_html=True)
        c3.markdown('<div class="cat-card bg-corp"><div class="cat-title">🏭 CORP</div>Aziende</div>', unsafe_allow_html=True)
        c4.markdown('<div class="cat-card bg-spec"><div class="cat-title">💎 SPEC</div>High Yield</div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Ricerca
        col_c, col_i = st.columns([1, 2])
        cat = col_c.selectbox("Categoria", list(MACRO_CATEGORIES.keys()))
        isin = col_i.text_input("ISIN", placeholder="IT...").strip().upper()
        
        if isin:
            if not valida_isin(isin): st.error("Formato ISIN non valido")
            else:
                with st.spinner("Analisi in corso..."):
                    row, info = cerca_db(isin, cat)
                    d = processa_riga(row, info) if row is not None else None
                
                if d:
                    # Calcoli Core
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality(d, risk, tax)
                    
                    # HEADER RISULTATO
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 25px; border-radius: 12px; border-left: 6px solid #00CC96; margin: 20px 0;">
                        <div class="main-header">{d['desc']}</div>
                        <div class="sub-header">ISIN: {isin} | Rating: {d['rating']} | Tax: {tax}%</div>
                        <div style="font-size:18px;color:#00CC96;">Score Qualità: {qual['score']}/100</div>
                    </div>""", unsafe_allow_html=True)
                    
                    # KPI GRID
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Prezzo", f"{d['pr']}€")
                    m2.metric("YTM Lordo", f"{risk['ytm']:.2f}%")
                    m3.metric("YTM Netto", f"{qual['ytm_netto']:.2f}%")
                    m4.metric("Cedola", f"{d['ced']}%")
                    m5.metric("Durata", f"{(d['sc'] - date.today()).days / 365.25:.1f} Y")
                    
                    # SIMULATORE
                    st.divider()
                    st.subheader("💰 Simulatore di Investimento Reale")
                    
                    c_sim1, c_sim2, c_sim3 = st.columns(3)
                    with c_sim1:
                        # 1.4 Formattazione input con virgola non supportata nativamente in input, ma gestita nel dataframe dopo
                        investimento = st.number_input("Quanto vuoi investire? (€)", value=10000.0, step=1000.0, format="%.2f")
                    with c_sim2:
                        commissioni = st.number_input("Commissioni Banca (€)", value=5.0, step=1.0, format="%.2f")
                    with c_sim3:
                        infl, _ = get_inflazione_ufficiale()
                        infl_sim = st.number_input("Inflazione Stimata (Annua) %", value=infl, step=0.5)
                    
                    # Calcolo Flussi
                    df_flussi, spesa_tot, incasso_tot, costo_rateo, totale_cedole_nette, plusvalenza_netta = genera_flussi_dettagliati(d, investimento, tax, commissioni, d['pr'])
                    guadagno_netto = incasso_tot - spesa_tot
                    anni_durata = (d['sc'] - date.today()).days / 365.25
                    
                    # 1.2 CALCOLO INFLAZIONE
                    # Formula corretta: Valore Attuale = Montante / (1 + tasso)^anni
                    valore_reale = incasso_tot / ((1 + infl_sim/100) ** anni_durata)
                    
                    # BOX VERDE RISULTATO
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #00CC96, #00AA76); padding: 25px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-top: 15px;">
                        <div style="font-size: 16px; opacity: 0.9;">PROFITTO NETTO NOMINALE</div>
                        <h1 style="margin: 5px 0; font-size: 42px; font-weight: bold;">+ {guadagno_netto:,.2f} €</h1>
                        <hr style="border-color: rgba(255,255,255,0.3); margin: 15px 0;">
                        <div style="display: flex; justify-content: space-around; font-size: 16px;">
                            <div>Uscita Oggi: <b style="color:#ffdddd;">-{spesa_tot:,.2f}€</b></div>
                            <div>Incasso Totale: <b>{incasso_tot:,.2f}€</b></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.divider()
                    
                    c_det1, c_det2 = st.columns([1, 1])
                    
                    # --- 1.3 SCONTRINO CHIARO ---
                    with c_det1:
                        st.subheader("🧾 Scontrino Fiscale")
                        
                        # Calcolo costo secco per display
                        costo_secco = investimento * d['pr'] / 100
                        
                        st.markdown(f"""
                        <div class="receipt-box">
                            <div style="color:gray; font-size:12px; margin-bottom:10px;">USCITE (OGGI)</div>
                            <div class="receipt-row"><span>Costo Titoli ({d['pr']:.2f}):</span> <span>{costo_secco:,.2f} €</span></div>
                            <div class="receipt-row"><span>+ Rateo (Interessi anticipati):</span> <span>{costo_rateo:,.2f} €</span></div>
                            <div class="receipt-row"><span>+ Commissioni:</span> <span>{commissioni:,.2f} €</span></div>
                            
                            <div class="receipt-total" style="color: #FF4B4B; border-top: 2px solid #FF4B4B;">
                                <span>TOTALE PAGARE:</span>
                                <span>-{spesa_tot:,.2f} €</span>
                            </div>
                            
                            <hr style="margin: 20px 0; border-top: 1px dashed gray;">
                            
                            <div style="color:gray; font-size:12px; margin-bottom:10px;">ENTRATE FUTURE (STIMA)</div>
                            <div class="receipt-row" style="color:#00CC96;">
                                <span>1. Cedole Nette Totali:</span>
                                <span>+{totale_cedole_nette:,.2f} €</span>
                            </div>
                            <div class="receipt-row" style="color:#00CC96;">
                                <span>2. Guadagno Capitale:</span>
                                <span>+{plusvalenza_netta:,.2f} €</span>
                            </div>
                            <div class="receipt-row" style="color:#FF4B4B;">
                                <span>3. Recupero Costi:</span>
                                <span>-{commissioni:,.2f} €</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # BOX INFO RICHIESTO
                        st.info("""
                        **ℹ️ Legenda Voci:**
                        * **Rateo:** Parte di cedola che anticipi al venditore. Ti rientra col primo incasso.
                        * **Cedole Nette:** Somma di tutti i bonifici interessi che riceverai.
                        * **Guadagno Capitale:** Differenza tra il valore di rimborso (es. 100) e il tuo prezzo di acquisto fiscale.
                        """)

                    # --- 1.1 GRAFICO BREAKEVEN CON PUNTO EVIDENZIATO ---
                    with c_det2:
                        st.subheader("🗓️ Recupero Capitale")
                        
                        df_flussi['Cumulativo'] = df_flussi['Importo'].cumsum()
                        
                        # Trova punto di breakeven (primo valore positivo)
                        df_pos = df_flussi[(df_flussi['Cumulativo'] >= 0) & (df_flussi['Data'] > date.today())]
                        
                        if not df_pos.empty:
                            breakeven_date = df_pos.iloc[0]['Data']
                            breakeven_val = df_pos.iloc[0]['Cumulativo']
                            giorni = (breakeven_date - date.today()).days
                            msg_p = f"Vai in pari (Breakeven) tra **{giorni} giorni** ({breakeven_date.strftime('%d/%m/%Y')})."
                            col_bg = "rgba(0, 204, 150, 0.1)"; ico = "✅"
                        else:
                            breakeven_date = None
                            msg_p = "Recupero capitale solo a scadenza."
                            col_bg = "rgba(255, 170, 0, 0.1)"; ico = "⏳"

                        st.markdown(f"""<div style="background-color: {col_bg}; padding: 15px; border-radius: 10px; border-left: 5px solid white; margin-bottom: 15px;"><span style="font-size: 20px;">{ico}</span> <span style="font-size: 16px;">{msg_p}</span></div>""", unsafe_allow_html=True)

                        # Costruzione Grafico
                        fig_pnl = go.Figure()
                        
                        # 1. Linea Rossa (Fino al Breakeven)
                        mask_neg = df_flussi['Cumulativo'] < 0
                        fig_pnl.add_trace(go.Scatter(
                            x=df_flussi[mask_neg]['Data'], 
                            y=df_flussi[mask_neg]['Cumulativo'],
                            mode='lines',
                            line=dict(color='#FF4B4B', width=3),
                            fill='tozeroy',
                            fillcolor='rgba(255, 75, 75, 0.2)',
                            name='Sotto Zero'
                        ))
                        
                        # 2. Linea Verde (Dal Breakeven in poi)
                        mask_pos = df_flussi['Cumulativo'] >= 0
                        if not df_pos.empty:
                            # Aggiungiamo l'ultimo punto negativo per collegare la linea visivamente
                            last_neg_idx = df_flussi[mask_neg].index[-1] if any(mask_neg) else None
                            if last_neg_idx is not None:
                                # Trucco visivo: colleghiamo l'ultimo rosso al primo verde
                                x_connect = [df_flussi.loc[last_neg_idx, 'Data'], df_flussi[mask_pos]['Data'].iloc[0]]
                                y_connect = [df_flussi.loc[last_neg_idx, 'Cumulativo'], df_flussi[mask_pos]['Cumulativo'].iloc[0]]
                                fig_pnl.add_trace(go.Scatter(x=x_connect, y=y_connect, mode='lines', line=dict(color='#00CC96', width=3, dash='dot'), showlegend=False))

                            fig_pnl.add_trace(go.Scatter(
                                x=df_flussi[mask_pos]['Data'], 
                                y=df_flussi[mask_pos]['Cumulativo'],
                                mode='lines',
                                line=dict(color='#00CC96', width=3),
                                fill='tozeroy',
                                fillcolor='rgba(0, 204, 150, 0.2)',
                                name='Guadagno'
                            ))
                            
                            # 3. IL PUNTO DI BREAKEVEN (Pallino)
                            fig_pnl.add_trace(go.Scatter(
                                x=[breakeven_date], 
                                y=[breakeven_val],
                                mode='markers+text',
                                marker=dict(color='#00CC96', size=12, symbol='star', line=dict(color='white', width=2)),
                                text=["BREAKEVEN"],
                                textposition="top center",
                                name='Punto Pareggio'
                            ))

                        fig_pnl.update_layout(
                            template="plotly_dark", 
                            height=300, 
                            showlegend=False, 
                            margin=dict(l=20, r=20, t=20, b=20),
                            yaxis_title="Saldo Conto (€)",
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig_pnl, use_container_width=True)
                        
                        st.warning(f"⚠️ **Inflazione:** I tuoi {incasso_tot:,.0f}€ futuri avranno un potere d'acquisto pari a **{valore_reale:,.0f}€** di oggi.", icon="💸")

                    # --- 1.4 CEDOLARIO FORMATTATO ---
                    st.subheader("📅 Cedolario & Flussi")
                    
                    def color_nums(val):
                        color = '#ff4b4b' if val < 0 else '#00cc96'
                        return f'color: {color}; font-weight: bold;'

                    st.dataframe(
                        df_flussi[['Data', 'Tipo', 'Importo', 'Dettagli']].style
                        .map(color_nums, subset=['Importo'])
                        .format({
                            'Importo': '{:,.2f} €',  # Virgola aggiunta qui
                            'Data': lambda x: x.strftime('%d/%m/%Y')
                        }),
                        use_container_width=True,
                        height=400
                    )
                    
                    # RISCHIO & AZIONI
                    st.divider()
                    c_r1, c_r2 = st.columns([1,1])
                    with c_r1:
                        st.subheader("⚠️ Stress Test")
                        shocks = [-100, -50, 0, +50, +100]
                        prices = [stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s) for s in shocks]
                        fig_s = go.Figure(go.Scatter(x=shocks, y=prices, mode='lines+markers+text', text=[f"{p:.1f}" for p in prices], textposition="top center", line=dict(color='#636EFA')))
                        fig_s.update_layout(template="plotly_dark", height=250, margin=dict(t=20,b=20), xaxis_title="Shock Bps", yaxis_title="Prezzo Stimato")
                        st.plotly_chart(fig_s, use_container_width=True)
                    
                    with c_r2:
                        st.subheader("⚙️ Azioni")
                        if st.button("📌 Salva per Confronto", use_container_width=True): st.session_state.confronto=d; st.success("Salvato!")
                        if st.button("💼 Aggiungi a Portafoglio", use_container_width=True):
                            st.session_state.portfolio.append({"ISIN":isin, "Desc":d['desc'], "Nominale":investimento, "Valore":investimento*d['pr']/100, "YTM":risk['ytm'], "Scadenza":d['sc']})
                            st.success("Aggiunto!")

                else: st.info("ISIN non trovato. Controlla o aggiorna DB.")

    # --- PAGINA: SCREENER (RICERCA AVANZATA) ---
    elif st.session_state.page == "Screener":
        bond_screener_ui()

    # --- PAGINA: DASHBOARD ---
    elif st.session_state.page == "Dashboard":
        dashboard_mercato_ui()

    # --- PAGINA: SMART ANALYSIS ---
    elif st.session_state.page == "Smart":
        smart_analysis_ui()

    # --- PAGINA: DIVERSIFICAZIONE ---
    elif st.session_state.page == "Diversificazione":
        diversificazione_ui()

    # --- PAGINA: ALERT ---
    elif st.session_state.page == "Alerts":
        alert_manager_ui()

    # --- PAGINA: CONFRONTO ---
    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto Bond")
        if st.session_state.confronto:
            a = st.session_state.confronto
            st.info(f"📌 A: {a['desc']}")
            c1, c2 = st.columns(2)
            cat_b = c1.selectbox("Cat B", list(MACRO_CATEGORIES.keys()))
            ib = c2.text_input("ISIN B").strip().upper()
            
            if st.button("VS") and ib:
                rb, info = cerca_db(ib, cat_b)
                b = processa_riga(rb, info) if rb is not None else None
                if b:
                    ra = calcola_metriche_rischio(a['pr'], a['ced'], a['sc'], a['freq'])
                    rb = calcola_metriche_rischio(b['pr'], b['ced'], b['sc'], b['freq'])
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("A YTM Net", f"{analizza_bond_quality(a, ra, 12.5)['ytm_netto']:.2f}%")
                    k2.markdown("<h2 style='text-align:center'>VS</h2>", unsafe_allow_html=True)
                    k3.metric("B YTM Net", f"{analizza_bond_quality(b, rb, 12.5)['ytm_netto']:.2f}%")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Duration'], y=[ra['mod_dur']], marker_color='#EF553B'))
                    fig.add_trace(go.Bar(name='B', x=['Duration'], y=[rb['mod_dur']], marker_color='#00CC96'))
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("B non trovato")
        else: st.warning("Salva prima un bond dallo Scanner.")

    # --- PAGINA: PORTAFOGLIO ---
    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        with st.expander("➕ Aggiungi Manuale"):
            c1, c2, c3, c4 = st.columns([2,2,2,1])
            pc = c1.selectbox("Cat", list(SOURCES_MAP.keys()), key="p_c")
            pi = c2.text_input("ISIN", key="p_i").strip().upper()
            pn = c3.number_input("Nom", 1000, key="p_n")
            if c4.button("Add") and pi:
                r, i = cerca_db(pi, pc)
                d = processa_riga(r, i) if r is not None else None
                if d:
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    st.session_state.portfolio.append({"ISIN": pi, "Desc": d['desc'], "Nominale": pn, "Valore": (pn*d['pr'])/100, "YTM": risk['ytm'] if risk else 0, "Scadenza": d['sc']})
                    st.success("Ok"); st.rerun()
        
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            tot = df['Valore'].sum()
            st.metric("Totale", f"{tot:,.0f}€")
            st.dataframe(df, use_container_width=True)
            if st.button("Reset"): st.session_state.portfolio=[]; st.rerun()
        else: st.info("Vuoto")

if st.session_state.logged_in: main_app()
else: login()
