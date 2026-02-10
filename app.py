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
# CONFIGURAZIONE PREMIUM UX - APPLE STYLE
# ==============================================================================

st.set_page_config(
    page_title="Bond Terminal Pro", 
    page_icon="", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS "APPLE STYLE" - Minimalista, Pulito, Etereo
st.markdown("""
<style>
    /* IMPORT FONT INTER (Simile a San Francisco) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    /* GLOBAL RESET */
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }
    
    /* COLORI VARIABILI APPLE DARK MODE */
    :root {
        --bg-app: #000000;
        --bg-secondary: #1C1C1E;
        --bg-tertiary: #2C2C2E;
        --text-primary: #FFFFFF;
        --text-secondary: #98989D;
        --accent-blue: #0A84FF;
        --accent-green: #30D158;
        --accent-red: #FF453A;
        --accent-orange: #FF9F0A;
        --border-subtle: rgba(255, 255, 255, 0.1);
        --glass: rgba(28, 28, 30, 0.7);
    }

    /* BACKGROUND APP */
    .stApp {
        background-color: var(--bg-app);
    }

    /* CARD DESIGN "GLASS" */
    .apple-card {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-subtle);
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        transition: transform 0.2s ease;
    }
    
    /* TITOLI E TESTI */
    h1, h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px !important;
    }
    p, span, div {
        color: var(--text-primary);
    }
    .text-muted {
        color: var(--text-secondary) !important;
        font-size: 13px;
    }

    /* METRICHE PULITE */
    .metric-container {
        display: flex;
        flex-direction: column;
    }
    .metric-label {
        font-size: 13px;
        font-weight: 500;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 600;
        color: var(--text-primary);
        font-feature-settings: "tnum";
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #111111;
        border-right: 1px solid var(--border-subtle);
    }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent;
        border: none;
        color: var(--text-secondary);
        text-align: left;
        padding: 10px 16px;
        font-size: 15px;
        font-weight: 500;
        border-radius: 10px;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--border-subtle);
    }

    /* INPUT FIELDS */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-subtle);
        border-radius: 10px;
        color: white;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: var(--accent-blue);
        box-shadow: 0 0 0 1px var(--accent-blue);
    }

    /* PULSANTI */
    .stButton > button {
        border-radius: 12px;
        font-weight: 500;
        border: 1px solid var(--border-subtle);
        background-color: var(--bg-tertiary);
        color: white;
    }
    .stButton > button:hover {
        border-color: var(--text-secondary);
        background-color: #3A3A3C;
    }

    /* SCONTRINO STYLE (Wallet) */
    .receipt-apple {
        background: #1C1C1E;
        border-radius: 18px;
        padding: 24px;
        position: relative;
        overflow: hidden;
        border: 1px solid var(--border-subtle);
    }
    .receipt-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        font-size: 14px;
    }
    .receipt-row:last-child { border-bottom: none; }
    .receipt-total {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px dashed var(--text-secondary);
        display: flex;
        justify-content: space-between;
        font-size: 18px;
        font-weight: 700;
    }

    /* BADGES */
    .badge {
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-blue { background: rgba(10, 132, 255, 0.15); color: var(--accent-blue); }
    .badge-green { background: rgba(48, 209, 88, 0.15); color: var(--accent-green); }
    .badge-red { background: rgba(255, 69, 58, 0.15); color: var(--accent-red); }
    .badge-gray { background: rgba(142, 142, 147, 0.15); color: var(--text-secondary); }

    /* CATEGORIE CARD */
    .cat-box {
        background: var(--bg-secondary);
        border: 1px solid var(--border-subtle);
        border-radius: 16px;
        padding: 20px;
        height: 100%;
        transition: transform 0.2s;
    }
    .cat-box:hover {
        transform: scale(1.02);
        border-color: var(--accent-blue);
    }
    .cat-icon { font-size: 24px; margin-bottom: 10px; display: block; }
    .cat-name { font-weight: 600; font-size: 16px; color: var(--text-primary); }
    
    /* DATAFRAME */
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* USER BOX */
    .user-pill {
        background: var(--bg-tertiary);
        border-radius: 20px;
        padding: 8px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
        border: 1px solid var(--border-subtle);
    }
    .user-avatar {
        width: 24px;
        height: 24px;
        background: var(--accent-blue);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: bold;
        color: white;
    }

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
    if not isin or len(isin) != 12: return False
    return isin[:2].isalpha() and isin[2:].isalnum()

def get_last_update_time():
    try:
        if not os.path.exists(DB_FOLDER): return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: return None
        return datetime.fromtimestamp(os.path.getmtime(max(files, key=os.path.getmtime)))
    except: return None

def check_connection_status():
    try:
        requests.get("https://www.google.com", timeout=3)
        return "Online"
    except: return "Offline"

def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

def get_inflazione_ufficiale():
    return 2.0, "Target BCE"

# ==============================================================================
# 5. DATA PROCESSING & PARSING
# ==============================================================================

def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        
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
        isin_val = str(row.name) if 'isin' not in str(row.index).lower() else "" 

        return {
            "desc": desc.replace("â‚¬", "€").strip(), 
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

def aggiorna_db():
    now = datetime.now()
    if st.session_state.last_scrape_time and (now - st.session_state.last_scrape_time).total_seconds() < 300:
        st.warning("Attendi qualche minuto."); return
            
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_sources = sum(len(v) for v in SOURCES_MAP.values())
    c = 0; ok = 0
    
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1
            status_text.text(f"Syncing: {src['nome']}")
            progress_bar.progress(c / total_sources)
            try:
                time.sleep(random.uniform(2, 4))
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                r = requests.get(src['url'], headers=headers, timeout=20)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
            except: pass
                
    st.session_state.last_scrape_time = now
    st.session_state.scrape_count += 1
    status_text.empty(); progress_bar.empty()
    st.success(f"Sync completato. {ok} files.")
    time.sleep(1); st.rerun()

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): return None, None
    search_keys = list(SOURCES_MAP.keys()) if not cat_macro or cat_macro == "🌐 TUTTE" else MACRO_CATEGORIES.get(cat_macro, [])
    
    for key in search_keys:
        for src in SOURCES_MAP.get(key, []):
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

@st.cache_data(ttl=3600)
def carica_tutto_mercato():
    all_data = []
    if not os.path.exists(DB_FOLDER): return pd.DataFrame()
    for filename in os.listdir(DB_FOLDER):
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(DB_FOLDER, filename))
                c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
                c_sc = next((c for c in df.columns if 'scadenza' in str(c).lower()), None)
                c_isin = next((c for c in df.columns if 'isin' in str(c).lower()), None)
                c_desc = next((c for c in df.columns if 'desc' in str(c).lower()), None)
                if all([c_pr, c_sc, c_isin, c_desc]):
                    df = df.dropna(subset=[c_pr, c_sc])
                    df['Prezzo'] = pd.to_numeric(df[c_pr].astype(str).str.replace(',','.').str.replace('€',''), errors='coerce')
                    df['ISIN'] = df[c_isin]
                    df['Descrizione'] = df[c_desc]
                    df['Fonte'] = filename.replace('.csv', '')
                    if "BTP" in filename or "BOT" in filename: df['Tipo'] = 'Governativo'
                    elif "CORP" in filename: df['Tipo'] = 'Corporate'
                    elif "BANCHE" in filename: df['Tipo'] = 'Bancario'
                    else: df['Tipo'] = 'Altro'
                    df['Cedola_Approx'] = df['Descrizione'].str.extract(r'(\d+(?:[.,]\d+)?)%').astype(float).fillna(0)
                    df['Scadenza'] = pd.to_datetime(df[c_sc], dayfirst=True, errors='coerce').dt.date
                    df = df.dropna(subset=['Scadenza'])
                    df['YTM_Grezzo'] = df.apply(lambda x: calcola_rendimento_grezzo(x['Prezzo'], x['Cedola_Approx'], x['Scadenza']), axis=1)
                    all_data.append(df[['ISIN', 'Descrizione', 'Prezzo', 'Tipo', 'Fonte', 'YTM_Grezzo', 'Scadenza']])
            except: continue
    if all_data: return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

# ==============================================================================
# 6. RISK ENGINE & MATEMATICA FINANZIARIA (CORE)
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
    shock = shock_bps / 10000
    delta = (-mod_dur * shock + 0.5 * convexity * (shock ** 2)) * prezzo
    return prezzo + delta

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "REPUBLIC", "TREASURY", "BEI", "EIB"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def calcola_rendimento_grezzo(prezzo, cedola, scadenza):
    try:
        anni = (scadenza - date.today()).days / 365.25
        if anni <= 0 or prezzo <= 0: return 0
        gain_annuo = (100 - prezzo) / anni
        rendimento = (cedola + gain_annuo) / prezzo * 100
        return round(rendimento, 2)
    except: return 0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []
    today_dt = date.today()
    rateo_pct = 0.0
    if dati['freq'] > 0:
        days_ced = 365 / dati['freq']
        data_ced = dati['sc']
        while data_ced > today_dt:
            data_ced -= timedelta(days=int(days_ced))
        rateo_pct = (dati['ced'] / dati['freq']) * ((today_dt - data_ced).days / days_ced)
        rateo_pct = max(0, rateo_pct)
    
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_netto = (nominale * rateo_pct / 100) * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    
    flussi.append({"Data": date.today(), "Tipo": "USCITA", "Importo": -spesa_totale, "Dettagli": "Acquisto"})
    
    totale_cedole_nette = 0
    if dati['freq'] > 0:
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = dati['sc']
        while curr > date.today() + timedelta(days=2):
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
    plusvalenza_netta = (gain/100)*nominale - tassa_gain
    
    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza_netta

def analizza_bond_quality(dati, risk, tax):
    flags = []; score = 100
    if dati['taglio'] > 100000: flags.append(("red", "Taglio > 100k")); score -= 20
    elif dati['taglio'] > 50000: flags.append(("warning", "Taglio > 50k")); score -= 10
    if dati['pr'] > 110: flags.append(("red", "Prezzo > 110")); score -= 15
    elif dati['pr'] > 105: flags.append(("warning", "Prezzo > 105")); score -= 5
    ytm_net = risk['ytm'] * (1 - tax / 100) if risk else 0
    if ytm_net < 2.0: flags.append(("warning", "Rendimento Basso")); score -= 10
    elif ytm_net > 4.0: flags.append(("green", "Rendimento Ottimo")); score += 10
    return {"flags": flags, "score": max(0, min(100, score)), "ytm_netto": ytm_net}

# ==============================================================================
# 8. PAGINE AVANZATE
# ==============================================================================

def bond_screener_ui():
    st.title("🎯 Bond Screener")
    df_all = carica_tutto_mercato()
    if df_all.empty:
        st.error("Nessun dato. Aggiorna DB.")
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1: ytm_min = st.slider("YTM Min %", 0.0, 10.0, 3.0, 0.5)
    with c2: px_max = st.slider("Prezzo Max", 50.0, 150.0, 100.0, 1.0)
    with c3: dur_max = st.slider("Scadenza Max (Anni)", 1, 50, 10, 1)
    with c4: tipo_sel = st.multiselect("Tipo", df_all['Tipo'].unique())
    
    df_all['Anni'] = (pd.to_datetime(df_all['Scadenza']) - datetime.today()).dt.days / 365.25
    res = df_all[(df_all['YTM_Grezzo'] >= ytm_min) & (df_all['Prezzo'] <= px_max) & (df_all['Anni'] <= dur_max)]
    if tipo_sel: res = res[res['Tipo'].isin(tipo_sel)]
    st.dataframe(res, use_container_width=True)

def dashboard_mercato_ui():
    st.title("📊 Dashboard Mercato")
    df = carica_tutto_mercato()
    if df.empty: st.warning("No data"); return
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="apple-card"><div class="metric-label">Bond Totali</div><div class="metric-value">{len(df)}</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="apple-card"><div class="metric-label">YTM Medio</div><div class="metric-value">{df["YTM_Grezzo"].mean():.2f}%</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="apple-card"><div class="metric-label">Prezzo Medio</div><div class="metric-value">{df["Prezzo"].mean():.2f}€</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="apple-card"><div class="metric-label">Sotto Pari</div><div class="metric-value">{len(df[df["Prezzo"] < 100])}</div></div>', unsafe_allow_html=True)
    st.write("")
    c_ch1, c_ch2 = st.columns(2)
    with c_ch1: st.bar_chart(df['Tipo'].value_counts())
    with c_ch2:
        df['Anni'] = (pd.to_datetime(df['Scadenza']) - datetime.today()).dt.days / 365.25
        df_clean = df[(df['YTM_Grezzo'] < 15) & (df['YTM_Grezzo'] > -2)]
        fig = px.scatter(df_clean, x='Anni', y='YTM_Grezzo', color='Tipo', title="Yield Curve", template="plotly_dark")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

def diversificazione_ui():
    st.title("🧮 Bond Ladder")
    st.info("Dividi il capitale su più scadenze.")
    capitale = st.number_input("Capitale Totale (€)", value=50000.0, step=1000.0)
    anni = st.slider("Orizzonte (Anni)", 3, 10, 5)
    steps = []
    cap_per_step = capitale / anni
    for i in range(1, anni + 1):
        steps.append({"Scadenza": f"Tra {i} Anni", "Anno": date.today().year + i, "Importo": f"{cap_per_step:,.2f} €"})
    st.dataframe(pd.DataFrame(steps), use_container_width=True)

def alert_manager_ui():
    st.title("🔔 Alert")
    if not st.session_state.alerts: st.info("Nessun alert.")
    else: 
        for i, a in enumerate(st.session_state.alerts): st.warning(f"{i+1}: {a}")
    with st.expander("Crea Alert"):
        isin_a = st.text_input("ISIN")
        target = st.number_input("Prezzo <", 95.0)
        if st.button("Salva"): st.session_state.alerts.append(f"{isin_a} < {target}"); st.success("OK"); st.rerun()

def smart_analysis_ui():
    st.title("🧠 Smart Analysis")
    df = carica_tutto_mercato()
    isin_in = st.text_input("ISIN").strip().upper()
    if isin_in and not df.empty:
        bond = df[df['ISIN'] == isin_in]
        if not bond.empty:
            b = bond.iloc[0]
            avg = df[df['Tipo'] == b['Tipo']]['YTM_Grezzo'].mean()
            st.metric("Tuo Bond", f"{b['YTM_Grezzo']:.2f}%", f"{b['YTM_Grezzo']-avg:.2f}% vs Media")
        else: st.error("Non trovato")

# ==============================================================================
# 9. LOGIN & SIDEBAR
# ==============================================================================

def login():
    st.markdown("<div style='text-align:center; margin-top:50px;'><h1> Bond Terminal</h1><p style='color:#666;'>Accesso Pro</p></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Utente")
            p = st.text_input("Password", type="password")
            sub = st.form_submit_button("Entra", use_container_width=True)
            if sub:
                ph = hashlib.sha256(p.encode()).hexdigest()
                if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                    st.session_state.logged_in = True
                    st.session_state.current_user = u
                    st.rerun()
                else: st.error("Errore")

def main_app():
    with st.sidebar:
        st.markdown(f"""<div class='user-pill'><div class='user-avatar'>{st.session_state.current_user[0].upper()}</div><div style='font-weight:600; color:#fff;'>{st.session_state.current_user.capitalize()}</div></div>""", unsafe_allow_html=True)
        st.caption("STRUMENTI")
        if st.button("🔎 Scanner"): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🎯 Screener"): st.session_state.page = "Screener"; st.rerun()
        if st.button("🧠 Smart Analysis"): st.session_state.page = "Smart"; st.rerun()
        if st.button("📊 Dashboard"): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("🧮 Ladder"): st.session_state.page = "Diversificazione"; st.rerun()
        if st.button("🔔 Alerts"): st.session_state.page = "Alerts"; st.rerun()
        if st.button("⚔️ Confronto"): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio"): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider()
        st.caption("SISTEMA")
        if st.button("Aggiorna Dati"): aggiorna_db()
        if st.button("Esci"): st.session_state.logged_in = False; st.rerun()

    if st.session_state.page == "Scanner":
        st.title("Scanner Bond")
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown('<div class="cat-box"><span class="cat-icon">🏛️</span><div class="cat-name">Governativo</div></div>', unsafe_allow_html=True)
        c2.markdown('<div class="cat-box"><span class="cat-icon">🏦</span><div class="cat-name">Bancario</div></div>', unsafe_allow_html=True)
        c3.markdown('<div class="cat-box"><span class="cat-icon">🏭</span><div class="cat-name">Corporate</div></div>', unsafe_allow_html=True)
        c4.markdown('<div class="cat-box"><span class="cat-icon">💎</span><div class="cat-name">Special</div></div>', unsafe_allow_html=True)
        
        st.write("")
        c_i1, c_i2 = st.columns([1, 2])
        cat = c_i1.selectbox("Categoria", list(MACRO_CATEGORIES.keys()))
        isin = c_i2.text_input("ISIN", placeholder="IT...").strip().upper()
        
        if isin:
            if not valida_isin(isin): st.error("ISIN Invalido")
            else:
                row, info = cerca_db(isin, cat)
                d = processa_riga(row, info) if row is not None else None
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality(d, risk, tax)
                    
                    st.markdown(f"""
                    <div class="apple-card">
                        <div style="font-size:12px; color:#98989D; text-transform:uppercase; margin-bottom:4px;">{d['fonte']}</div>
                        <div style="font-size:24px; font-weight:600; color:white; margin-bottom:10px;">{d['desc']}</div>
                        <div style="display:flex; gap:10px;">
                            <span class="badge badge-blue">Cedola {d['ced']}%</span>
                            <span class="badge badge-gray">{d['sc'].strftime('%d/%m/%Y')}</span>
                            <span class="badge badge-gray">Tax {tax}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.markdown(f'<div class="apple-card"><div class="metric-label">Prezzo</div><div class="metric-value">{d["pr"]}€</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="apple-card"><div class="metric-label">YTM Lordo</div><div class="metric-value">{risk["ytm"]:.2f}%</div></div>', unsafe_allow_html=True)
                    m3.markdown(f'<div class="apple-card"><div class="metric-label">YTM Netto</div><div class="metric-value" style="color:var(--accent-green);">{qual["ytm_netto"]:.2f}%</div></div>', unsafe_allow_html=True)
                    m4.markdown(f'<div class="apple-card"><div class="metric-label">Duration</div><div class="metric-value">{risk["mod_dur"]:.2f}</div></div>', unsafe_allow_html=True)
                    
                    # SIMULATORE
                    st.divider()
                    st.markdown("### Simulatore Investimento")
                    c_sim1, c_sim2, c_sim3 = st.columns(3)
                    with c_sim1: inv = st.number_input("Investimento (€)", value=10000.0, step=1000.0, format="%.2f")
                    with c_sim2: comm = st.number_input("Commissioni (€)", value=5.0, step=1.0, format="%.2f")
                    with c_sim3: infl_val, _ = get_inflazione_ufficiale(); infl = st.number_input("Inflazione %", value=infl_val, step=0.5)
                    
                    df_flow, spesa, incasso, rateo, tot_ced, cg_net = genera_flussi_dettagliati(d, inv, tax, comm, d['pr'])
                    guadagno = incasso - spesa
                    dur_y = (d['sc'] - date.today()).days / 365.25
                    val_reale = incasso / ((1 + infl/100) ** dur_y)
                    
                    # SCONTRINO APPLE STYLE
                    st.write("")
                    col_usc, col_entr = st.columns(2)
                    with col_usc:
                        st.markdown(f"""
                        <div class="receipt-apple">
                            <div style="font-size:12px; color:#FF453A; font-weight:600; margin-bottom:12px; text-transform:uppercase;">Uscite Oggi</div>
                            <div class="receipt-row"><span>Costo Titoli</span><span>{inv*d['pr']/100:,.2f} €</span></div>
                            <div class="receipt-row"><span>Rateo Interessi</span><span>{rateo:,.2f} €</span></div>
                            <div class="receipt-row"><span>Commissioni</span><span>{comm:,.2f} €</span></div>
                            <div class="receipt-total" style="color:#FF453A;"><span>TOTALE</span><span>-{spesa:,.2f} €</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_entr:
                        st.markdown(f"""
                        <div class="receipt-apple">
                            <div style="font-size:12px; color:#30D158; font-weight:600; margin-bottom:12px; text-transform:uppercase;">Entrate Future</div>
                            <div class="receipt-row"><span>Cedole Nette</span><span>+{tot_ced:,.2f} €</span></div>
                            <div class="receipt-row"><span>Rimborso</span><span>+{inv:,.2f} €</span></div>
                            <div class="receipt-row"><span>Capital Gain</span><span>+{cg_net:,.2f} €</span></div>
                            <div class="receipt-total" style="color:#30D158;"><span>TOTALE</span><span>+{incasso:,.2f} €</span></div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.info(f"**Risultato Netto:** Investi {spesa:,.2f}€ per avere {incasso:,.2f}€. Guadagno: **+{guadagno:,.2f}€**")
                    
                    # GRAFICO BREAKEVEN
                    st.write("")
                    st.markdown("### Recupero Capitale")
                    df_flow['Cum'] = df_flow['Importo'].cumsum()
                    df_pos = df_flow[(df_flow['Cum'] >= 0) & (df_flow['Data'] > date.today())]
                    
                    breakeven_date = df_pos.iloc[0]['Data'] if not df_pos.empty else None
                    msg_p = f"✅ Pareggio tra **{(breakeven_date - date.today()).days} giorni**." if breakeven_date else "⏳ Recupero a scadenza."
                    st.caption(msg_p)
                    
                    fig = go.Figure()
                    
                    # Linea Rossa (Negativa)
                    df_neg = df_flow[df_flow['Cum'] < 0]
                    if not df_neg.empty:
                        fig.add_trace(go.Scatter(x=df_neg['Data'], y=df_neg['Cum'], mode='lines', line=dict(color='#FF453A', width=3), name='Recupero'))
                    
                    # Linea Verde (Positiva)
                    df_pos_g = df_flow[df_flow['Cum'] >= 0]
                    if not df_pos_g.empty:
                        # Collega visivamente
                        if not df_neg.empty:
                            x_conn = [df_neg.iloc[-1]['Data'], df_pos_g.iloc[0]['Data']]
                            y_conn = [df_neg.iloc[-1]['Cum'], df_pos_g.iloc[0]['Cum']]
                            fig.add_trace(go.Scatter(x=x_conn, y=y_conn, mode='lines', line=dict(color='gray', width=1, dash='dot'), showlegend=False))
                        
                        fig.add_trace(go.Scatter(x=df_pos_g['Data'], y=df_pos_g['Cum'], mode='lines', line=dict(color='#30D158', width=3), name='Guadagno'))
                        
                        # Stella su asse X
                        if breakeven_date:
                             fig.add_trace(go.Scatter(x=[breakeven_date], y=[0], mode='markers', marker=dict(color='#FFD60A', size=14, symbol='star'), name='Breakeven'))

                    fig.add_hline(y=0, line_color="#333", line_width=1)
                    fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300, margin=dict(l=0, r=0, t=20, b=20), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if infl > 0:
                         st.info(f"**Valore Reale:** I tuoi {incasso:,.2f}€ futuri varranno come **{val_reale:,.2f}€** oggi.", icon="💸")
                    
                    st.dataframe(df_flow[['Data','Tipo','Importo']].style.format({'Importo':'{:,.2f}€', 'Data': lambda x: x.strftime('%d/%m/%Y')}), use_container_width=True)
                    
                    c_b1, c_b2 = st.columns(2)
                    if c_b1.button("📌 Salva"): st.session_state.confronto = d; st.success("Salvato")
                    if c_b2.button("💼 Aggiungi"): st.session_state.portfolio.append({"ISIN":isin, "Desc":d['desc'], "Valore":inv}); st.success("Aggiunto")
                    
                else: st.warning("ISIN non trovato.")

    elif st.session_state.page == "Screener": bond_screener_ui()
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Smart": smart_analysis_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()
    elif st.session_state.page == "Confronto":
        st.title("Confronto")
        if st.session_state.confronto:
            a = st.session_state.confronto
            st.markdown(f"<div class='apple-card'><strong>Base:</strong> {a['desc']}</div>", unsafe_allow_html=True)
            ib = st.text_input("ISIN B").strip().upper()
            if st.button("Confronta") and ib:
                rb, info = cerca_db(ib, "🌐 TUTTE")
                b = processa_riga(rb, info) if rb is not None else None
                if b:
                    ra = calcola_metriche_rischio(a['pr'], a['ced'], a['sc'], a['freq'])
                    rb = calcola_metriche_rischio(b['pr'], b['ced'], b['sc'], b['freq'])
                    c1, c2 = st.columns(2)
                    c1.metric("A Netto", f"{analizza_bond_quality(a, ra, 12.5)['ytm_netto']:.2f}%")
                    c2.metric("B Netto", f"{analizza_bond_quality(b, rb, 12.5)['ytm_netto']:.2f}%")
        else: st.info("Salva un bond prima.")
        
    elif st.session_state.page == "Portafoglio":
        st.title("Portafoglio")
        if st.session_state.portfolio:
            st.dataframe(pd.DataFrame(st.session_state.portfolio), use_container_width=True)
            if st.button("Reset"): st.session_state.portfolio=[]; st.rerun()
        else: st.info("Vuoto")

if st.session_state.logged_in: main_app()
else: login()
