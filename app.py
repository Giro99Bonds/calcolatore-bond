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
# CONFIGURAZIONE PREMIUM UX
# ==============================================================================

st.set_page_config(
    page_title="Bond Terminal Pro", 
    page_icon="💎", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PREMIUM - Design pensato per vendibilità
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    code, .mono { font-family: 'JetBrains Mono', monospace; }
    
    /* === THEME PREMIUM === */
    :root {
        --primary: #00D9B1;
        --danger: #FF4757;
        --warning: #FFA502;
        --success: #26DE81;
        --bg-dark: #0F1419;
        --bg-card: #1A1F2E;
        --text-main: #E8EAED;
        --text-muted: #9BA1A6;
        --border: #2D3748;
    }
    
    /* === CARDS PREMIUM === */
    .premium-card {
        background: linear-gradient(135deg, var(--bg-card) 0%, #222840 100%);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
    }
    .premium-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 48px rgba(0, 217, 177, 0.15);
        border-color: var(--primary);
    }
    
    /* === ALERT SYSTEM (CRITICI) === */
    .alert-critical {
        background: linear-gradient(135deg, #FF4757 0%, #C44569 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 6px solid #FFF;
        margin: 16px 0;
        font-weight: 600;
        box-shadow: 0 4px 24px rgba(255, 71, 87, 0.3);
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 4px 24px rgba(255, 71, 87, 0.3); }
        50% { box-shadow: 0 8px 32px rgba(255, 71, 87, 0.6); }
    }
    
    .alert-warning {
        background: linear-gradient(135deg, #FFA502 0%, #E58E26 100%);
        color: white;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #FFD32A;
        margin: 16px 0;
        font-weight: 500;
    }
    
    .alert-success {
        background: linear-gradient(135deg, #26DE81 0%, #20BF6B 100%);
        color: white;
        padding: 18px;
        border-radius: 12px;
        border-left: 6px solid #0FE;
        margin: 16px 0;
        font-weight: 500;
    }
    
    /* === BOND CARD HEADER === */
    .bond-header {
        background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
        padding: 28px;
        border-radius: 16px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    .bond-title { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
    .bond-subtitle { font-size: 14px; opacity: 0.9; }
    .bond-badge {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 13px;
        margin-right: 8px;
        margin-top: 8px;
    }
    
    /* === METRICS PREMIUM === */
    .metric-premium {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-premium:hover {
        border-color: var(--primary);
        transform: scale(1.02);
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: var(--primary);
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-label {
        font-size: 12px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }
    
    /* === PROGRESS BAR === */
    .progress-bar {
        height: 8px;
        background: var(--border);
        border-radius: 10px;
        overflow: hidden;
        margin: 12px 0;
    }
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--primary) 0%, #00FFC6 100%);
        transition: width 0.5s ease;
        box-shadow: 0 0 10px var(--primary);
    }
    
    /* === SIDEBAR PREMIUM === */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A1F2E 0%, #0F1419 100%);
    }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent;
        border: 1px solid transparent;
        color: var(--text-main);
        text-align: left;
        padding: 12px 16px;
        border-radius: 8px;
        transition: all 0.2s ease;
        font-weight: 500;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(0, 217, 177, 0.1);
        border-color: var(--primary);
        transform: translateX(4px);
    }
    
    /* === TABLES === */
    .dataframe {
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    
    /* === CATEGORY CARDS === */
    .cat-card-gov { background: linear-gradient(135deg, #11998E 0%, #38EF7D 100%); }
    .cat-card-bank { background: linear-gradient(135deg, #4568DC 0%, #B06AB3 100%); }
    .cat-card-corp { background: linear-gradient(135deg, #F2994A 0%, #F2C94C 100%); }
    .cat-card-spec { background: linear-gradient(135deg, #DA22FF 0%, #9733EE 100%); }
    
    .cat-card {
        padding: 20px;
        border-radius: 16px;
        color: white;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        height: 100%;
        transition: all 0.3s ease;
    }
    .cat-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 32px rgba(0,0,0,0.3);
    }
    .cat-title { 
        font-size: 18px; 
        font-weight: 700; 
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .cat-desc { 
        font-size: 14px; 
        opacity: 0.95; 
        line-height: 1.5;
        margin-bottom: 12px;
    }
    .cat-badge {
        display: inline-block;
        background: rgba(255,255,255,0.25);
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
    }
    
    /* === BREAKEVEN VISUAL === */
    .breakeven-box {
        background: var(--bg-card);
        border: 2px solid var(--border);
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
    }
    .breakeven-positive {
        border-left: 6px solid var(--success);
        background: linear-gradient(135deg, rgba(38, 222, 129, 0.05) 0%, transparent 100%);
    }
    .breakeven-negative {
        border-left: 6px solid var(--danger);
        background: linear-gradient(135deg, rgba(255, 71, 87, 0.05) 0%, transparent 100%);
    }
    
    /* === TOOLTIPS === */
    .tooltip-icon {
        display: inline-block;
        width: 18px;
        height: 18px;
        background: var(--primary);
        color: white;
        border-radius: 50%;
        text-align: center;
        font-size: 12px;
        font-weight: 700;
        cursor: help;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CONFIGURAZIONE & CREDENZIALI
# ==============================================================================

UTENTI_IN_CHIARO = {"giulio": "Giulio99mac!", "guest": "mifumoleboix", "marco": "demo2025"}
UTENTI_ABILITATI = {user: hashlib.sha256(pwd.encode()).hexdigest() for user, pwd in UTENTI_IN_CHIARO.items()}

DB_FOLDER = "bond_database"
os.makedirs(DB_FOLDER, exist_ok=True)

def init_session_state():
    defaults = {
        'portfolio': [], 'alerts': [], 'logged_in': False, 'current_user': "",
        'page': "Scanner", 'patrimonio': 50000.0, 'connection_status': "In attesa...",
        'last_scrape_time': None, 'selected_isin_from_chart': None
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
            
    # Gestione login via URL
    query_params = st.query_params
    session_token = query_params.get("session", None)
    if session_token and not st.session_state.logged_in:
        for user, pwd_hash in UTENTI_ABILITATI.items():
            if hashlib.sha256((user + "salt").encode()).hexdigest() == session_token:
                st.session_state.logged_in = True
                st.session_state.current_user = user
                break

init_session_state()

# ==============================================================================
# MAPPA FONTI DATI
# ==============================================================================

SOURCES_MAP = {
    "GOV_IT": [
        {"nome": "BTP_FISSI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
    ],
    "GOV_EU": [
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "BANCHE": [
        {"nome": "BANCHE_SENIOR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "CORP": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
    ]
}

MACRO_CATEGORIES = {
    "🌐 TUTTE": [], 
    "🏛️ GOVERNATIVI": ["GOV_IT", "GOV_EU"],
    "🏦 BANCARI": ["BANCHE"],
    "🏭 CORPORATE": ["CORP"]
}

# ==============================================================================
# FUNZIONI CORE
# ==============================================================================

def valida_isin(isin):
    return isin and len(isin) == 12 and isin[:2].isalpha() and isin[2:].isalnum()

def determina_tasse(nome, desc):
    gov_keys = ["BTP", "BOT", "BUND", "OAT", "TREASURY", "BEI"]
    return 12.5 if any(k in nome.upper() or k in desc.upper() for k in gov_keys) else 26.0

def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    if prezzo <= 0 or freq == 0: return None
    anni = (scadenza - date.today()).days / 365.25
    if anni <= 0: return None
    
    ytm_guess = (cedola_pct/100 + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
    c = (cedola_pct/100 * face_value) / freq
    n = max(1, int(anni * freq))
    
    def price_func(y):
        if y <= -1: return float('inf')
        pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n + 1)])
        pv += face_value / ((1 + y/freq) ** n)
        return pv - prezzo
    
    try:
        ytm = newton(price_func, ytm_guess, maxiter=50)
        return max(0, ytm)
    except:
        return ytm_guess

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    if prezzo <= 0: return None
    ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq)
    if ytm is None: return None
    anni = (scadenza - date.today()).days / 365.25
    mod_dur = anni / (1 + ytm)
    return {"ytm": ytm * 100, "mod_dur": mod_dur}

def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_is = next((c for c in cols if 'isin' in str(c).lower()), None)
        
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
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        ced = float(m.group(1).replace(',', '.')) if m else 0.0
        isin = str(row[c_is]).strip() if c_is else ""
        
        return {"isin": isin, "desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome']}
    except:
        return None

def cerca_db(isin, cat_macro):
    if not valida_isin(isin): return None, None
    
    search_keys = list(SOURCES_MAP.keys()) if not cat_macro or cat_macro == "🌐 TUTTE" else MACRO_CATEGORIES.get(cat_macro, [])
    
    for key in search_keys:
        for src in SOURCES_MAP.get(key, []):
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path): continue
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any():
                        return df[mask].iloc[0], {"nome": src['nome'], "freq": src['freq'], "cat_reale": key}
            except: continue
    return None, None

@st.cache_data(ttl=3600)
def carica_dati_mercato():
    all_bonds = []
    if not os.path.exists(DB_FOLDER): return pd.DataFrame()
    
    for filename in os.listdir(DB_FOLDER):
        if not filename.endswith(".csv"): continue
        try:
            df = pd.read_csv(os.path.join(DB_FOLDER, filename))
            c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
            c_sc = next((c for c in df.columns if 'scadenza' in str(c).lower()), None)
            c_de = next((c for c in df.columns if 'desc' in str(c).lower()), None)
            c_is = next((c for c in df.columns if 'isin' in str(c).lower()), None)
            
            if all([c_pr, c_sc, c_de, c_is]):
                for _, row in df.iterrows():
                    try:
                        sc = datetime.strptime(str(row[c_sc]).strip(), '%Y-%m-%d').date()
                        if sc <= date.today(): continue
                        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
                        desc = str(row[c_de])
                        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
                        ced = float(m.group(1).replace(',', '.')) if m else 0.0
                        
                        cat = "Governativo" if any(x in desc.upper() for x in ["BTP", "BOT", "BUND"]) else "Corporate"
                        
                        all_bonds.append({
                            "ISIN": str(row[c_is]).strip(),
                            "Desc": desc,
                            "Prezzo": pr,
                            "Scadenza": sc,
                            "Cedola": ced,
                            "YTM_Grezzo": (ced + (100 - pr) / ((sc - date.today()).days / 365.25)) / pr * 100,
                            "Anni": (sc - date.today()).days / 365.25,
                            "Categoria": cat
                        })
                    except: continue
        except: continue
    return pd.DataFrame(all_bonds)

def aggiorna_db():
    for f in os.listdir(DB_FOLDER):
        try: os.unlink(os.path.join(DB_FOLDER, f))
        except: pass
    
    p = st.progress(0)
    s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values())
    c = 0
    
    for sources in SOURCES_MAP.values():
        for src in sources:
            c += 1
            s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            p.progress(c/tot)
            time.sleep(random.uniform(2, 4))
            
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        break
            except: pass
    
    st.session_state.last_scrape_time = datetime.now()
    s.empty()
    p.empty()
    st.toast("✅ Database aggiornato!", icon="✅")
    time.sleep(1)
    st.rerun()

# ==============================================================================
# 🆕 SISTEMA ALERT INTELLIGENTI (PROTEZIONE RETAIL)
# ==============================================================================

def genera_alert_protezione(bond, patrimonio, rendimento_reale):
    """
    Sistema di alert che PREVIENE ERRORI COSTOSI
    """
    alerts = []
    
    # 🚨 ALERT CRITICO 1: Concentrazione
    peso = (bond['pr'] * 1000 / 100) / patrimonio * 100
    if peso > 20:
        alerts.append({
            'level': 'critical',
            'title': '🚨 RISCHIO CONCENTRAZIONE ESTREMO',
            'message': f'Questo bond rappresenta il **{peso:.1f}%** del tuo patrimonio. La regola d\'oro dice: MAI oltre il 20% su un singolo titolo. Se questo bond ha problemi, perdi {peso:.1f}% del capitale.',
            'action': 'RIDUCI L\'IMPORTO o SCEGLI BOND PIÙ PICCOLI'
        })
    elif peso > 15:
        alerts.append({
            'level': 'warning',
            'title': '⚠️ Attenzione Concentrazione',
            'message': f'Pesa il {peso:.1f}%. Sotto il 20% ma considerando la diversificazione, prova a stare sotto il 15%.',
            'action': 'OK ma monitora'
        })
    
    # 🚨 ALERT CRITICO 2: Rendimento Reale Negativo
    if rendimento_reale < 0:
        perdita_annua = abs(rendimento_reale) * patrimonio / 100
        alerts.append({
            'level': 'critical',
            'title': '🚨 STAI PERDENDO POTERE D\'ACQUISTO',
            'message': f'Rendimento reale: **{rendimento_reale:.2f}%**. Con l\'inflazione al 2%, perdi circa **{perdita_annua:,.0f}€ all\'anno** in potere d\'acquisto. È come tenere i soldi sotto il materasso.',
            'action': 'TROVA BOND CON RENDIMENTO >2% o DIVERSIFICA'
        })
    elif rendimento_reale < 0.5:
        alerts.append({
            'level': 'warning',
            'title': '⚠️ Rendimento Reale Marginale',
            'message': f'Rendimento reale: {rendimento_reale:.2f}%. Copri APPENA l\'inflazione. Considera bond con rendimento più alto.',
            'action': 'Valuta alternative'
        })
    
    # 🚨 ALERT CRITICO 3: Prezzo Troppo Alto
    if bond['pr'] > 108:
        perdita = bond['pr'] - 100
        alerts.append({
            'level': 'warning',
            'title': '⚠️ Paghi Troppo Sopra la Pari',
            'message': f'Paghi {bond["pr"]}€ per ricevere 100€ a scadenza. PERDI {perdita:.2f}€ per ogni 100€ investiti SOLO per il prezzo. Assicurati che le cedole compensino.',
            'action': 'Verifica che il rendimento totale sia positivo'
        })
    
    # ✅ ALERT POSITIVO: Buon affare
    if bond['pr'] < 95 and rendimento_reale > 1.5:
        alerts.append({
            'level': 'success',
            'title': '✅ Buon Affare Potenziale',
            'message': f'Prezzo {bond["pr"]}€ (sotto la pari) + Rendimento reale {rendimento_reale:.2f}%. Questo bond sembra interessante!',
            'action': 'Verifica il rating e la solidità dell\'emittente'
        })
    
    return alerts

def mostra_alert_ui(alerts):
    """Mostra alert con design premium"""
    if not alerts:
        st.markdown("""
        <div class="alert-success">
            ✅ <strong>Nessun Alert Critico</strong><br>
            Questo bond sembra essere in linea con le best practice di investimento.
        </div>
        """, unsafe_allow_html=True)
        return
    
    for alert in alerts:
        if alert['level'] == 'critical':
            st.markdown(f"""
            <div class="alert-critical">
                <strong style="font-size:18px;">{alert['title']}</strong><br><br>
                {alert['message']}<br><br>
                <strong>📌 AZIONE CONSIGLIATA:</strong> {alert['action']}
            </div>
            """, unsafe_allow_html=True)
        elif alert['level'] == 'warning':
            st.markdown(f"""
            <div class="alert-warning">
                <strong style="font-size:16px;">{alert['title']}</strong><br><br>
                {alert['message']}<br><br>
                <strong>💡 Consiglio:</strong> {alert['action']}
            </div>
            """, unsafe_allow_html=True)
        elif alert['level'] == 'success':
            st.markdown(f"""
            <div class="alert-success">
                <strong style="font-size:16px;">{alert['title']}</strong><br><br>
                {alert['message']}<br><br>
                <strong>✓ Next Step:</strong> {alert['action']}
            </div>
            """, unsafe_allow_html=True)

# ==============================================================================
# UI COMPONENTS
# ==============================================================================

def login():
    st.markdown("<div style='text-align:center; padding:40px 0;'><h1 style='font-size:48px; background: linear-gradient(90deg, #667EEA 0%, #764BA2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>💎 Bond Terminal Pro</h1><p style='color:#9BA1A6; font-size:18px;'>La piattaforma professionale per investire in bond</p></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        u = st.text_input("Username", placeholder="es. giulio o marco").strip()
        p = st.text_input("Password", type="password")
        
        if st.button("🔐 Accedi", use_container_width=True, type="primary"):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                token = hashlib.sha256((u + "salt").encode()).hexdigest()
                st.query_params["session"] = token
                st.success("✅ Login riuscito!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Credenziali errate")

def sidebar_premium():
    with st.sidebar:
        st.markdown(f"<div style='text-align:center; padding:20px 0;'><h2 style='background: linear-gradient(90deg, #00D9B1, #00FFC6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>💎 BOND TERMINAL</h2><p style='color:#9BA1A6;'>Benvenuto, <strong>{st.session_state.current_user.capitalize()}</strong></p></div>", unsafe_allow_html=True)
        
        st.divider()
        st.markdown("### 🎯 ANALISI")
        if st.button("🔎 Scanner Singolo", use_container_width=True):
            st.session_state.page = "Scanner"
            st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True):
            st.session_state.page = "SmartAnalysis"
            st.rerun()
        if st.button("📊 Dashboard Mercato", use_container_width=True):
            st.session_state.page = "Dashboard"
            st.rerun()
        
        st.divider()
        st.markdown("### 🛠️ TOOLS PRO")
        if st.button("🎯 Bond Screener", use_container_width=True):
            st.session_state.page = "Screener"
            st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True):
            st.session_state.page = "Diversificazione"
            st.rerun()
        
        st.divider()
        st.markdown("### ⚙️ SISTEMA")
        
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_sources = sum(len(v) for v in SOURCES_MAP.values())
        perc = len(csv_files) / tot_sources if tot_sources > 0 else 0
        
        st.markdown(f"""
        <div style='background: var(--bg-card); padding:12px; border-radius:8px; margin-bottom:12px;'>
            <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
                <span style='color:var(--text-muted); font-size:12px;'>DATABASE</span>
                <span style='color:var(--text-main); font-weight:600;'>{len(csv_files)}/{tot_sources}</span>
            </div>
            <div class='progress-bar'>
                <div class='progress-fill' style='width:{perc*100}%'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Aggiorna Database", use_container_width=True, type="primary"):
            aggiorna_db()
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

# ==============================================================================
# PAGES
# ==============================================================================

def page_scanner():
    st.title("🔎 Scanner Bond Professionale")
    st.caption("Analisi completa con alert di protezione automatici")
    
    # Guide Cards
    st.markdown("### 📚 Guida Rapida alle Categorie")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown("""
        <div class="cat-card cat-card-gov">
            <div class="cat-title">🏛️ GOVERNATIVI</div>
            <div class="cat-desc">Titoli di Stato (BTP, Bund). Massima sicurezza.</div>
            <span class="cat-badge">Rischio: BASSO</span>
            <span class="cat-badge">Tax: 12.5%</span>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class="cat-card cat-card-bank">
            <div class="cat-title">🏦 BANCARI</div>
            <div class="cat-desc">Bond emessi da banche. Rendimento medio.</div>
            <span class="cat-badge">Rischio: MEDIO</span>
            <span class="cat-badge">Tax: 26%</span>
        </div>
        """, unsafe_allow_html=True)
    
    with c3:
        st.markdown("""
        <div class="cat-card cat-card-corp">
            <div class="cat-title">🏭 CORPORATE</div>
            <div class="cat-desc">Aziende (Eni, Enel). Rendimento alto.</div>
            <span class="cat-badge">Rischio: ALTO</span>
            <span class="cat-badge">Tax: 26%</span>
        </div>
        """, unsafe_allow_html=True)
    
    with c4:
        st.markdown("""
        <div class="cat-card cat-card-spec">
            <div class="cat-title">💎 SPECIALI</div>
            <div class="cat-desc">Zero Coupon, Callable. Per esperti.</div>
            <span class="cat-badge">Rischio: VAR</span>
            <span class="cat-badge">Tax: Mista</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Search
    col_cat, col_isin, col_btn = st.columns([2, 2, 1])
    with col_cat:
        cat_select = st.selectbox("🗂️ Categoria", list(MACRO_CATEGORIES.keys()))
    with col_isin:
        isin = st.text_input("🔍 ISIN", placeholder="IT0005436693").strip().upper()
    with col_btn:
        st.write("")
        st.write("")
        trigger = st.button("Analizza", use_container_width=True, type="primary")
    
    if isin and trigger:
        if not valida_isin(isin):
            st.error("❌ ISIN non valido (deve essere 12 caratteri)")
            return
        
        row, info = cerca_db(isin, cat_select)
        bond = processa_riga(row, info) if row is not None else None
        
        if not bond:
            st.warning("⚠️ Bond non trovato nel database. Prova ad aggiornare i dati.")
            return
        
        # Calcoli
        tax = determina_tasse(bond['fonte'], bond['desc'])
        risk = calcola_metriche_rischio(bond['pr'], bond['ced'], bond['sc'], bond['freq'])
        ytm_netto = risk['ytm'] * (1 - tax/100) if risk else 0
        ytm_reale = ytm_netto - 2.0  # Inflazione 2%
        
        # Header Premium
        anni = (bond['sc'] - date.today()).days / 365.25
        st.markdown(f"""
        <div class="bond-header">
            <div class="bond-title">{bond['desc']}</div>
            <div class="bond-subtitle">ISIN: {isin} | Fonte: {bond['fonte']}</div>
            <div style="margin-top:12px;">
                <span class="bond-badge">Cedola: {bond['ced']}%</span>
                <span class="bond-badge">Scadenza: {bond['sc'].strftime('%d/%m/%Y')}</span>
                <span class="bond-badge">Prezzo: {bond['pr']}€</span>
                <span class="bond-badge">Tasse: {tax}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Metriche Premium
        st.markdown("### 📊 Metriche Chiave")
        m1, m2, m3, m4 = st.columns(4)
        
        with m1:
            st.markdown(f"""
            <div class="metric-premium">
                <div class="metric-value">{bond['pr']:.2f}€</div>
                <div class="metric-label">Prezzo</div>
            </div>
            """, unsafe_allow_html=True)
        
        with m2:
            st.markdown(f"""
            <div class="metric-premium">
                <div class="metric-value">{ytm_netto:.2f}%</div>
                <div class="metric-label">YTM Netto</div>
            </div>
            """, unsafe_allow_html=True)
        
        with m3:
            color = "var(--danger)" if ytm_reale < 0 else "var(--success)" if ytm_reale > 1 else "var(--warning)"
            st.markdown(f"""
            <div class="metric-premium">
                <div class="metric-value" style="color:{color};">{ytm_reale:.2f}%</div>
                <div class="metric-label">YTM Reale</div>
            </div>
            """, unsafe_allow_html=True)
        
        with m4:
            st.markdown(f"""
            <div class="metric-premium">
                <div class="metric-value">{anni:.1f}</div>
                <div class="metric-label">Anni a Scadenza</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # 🆕 SISTEMA ALERT PROTEZIONE
        st.markdown("### 🚨 Alert di Protezione")
        alerts = genera_alert_protezione(bond, st.session_state.patrimonio, ytm_reale)
        mostra_alert_ui(alerts)
        
        st.divider()
        
        # Simulatore Premium
        st.markdown("### 💰 Simulatore di Investimento")
        
        col_sim1, col_sim2 = st.columns([1, 2])
        
        with col_sim1:
            inv = st.number_input("💵 Capitale da Investire (€)", value=10000.0, step=1000.0)
            comm = st.number_input("🏦 Commissioni (€)", value=5.0, step=1.0)
            infl = st.number_input("📈 Inflazione Stimata %", value=2.0, step=0.5)
        
        with col_sim2:
            # Calcoli finali
            prezzo_tot = (inv * bond['pr']) / 100
            cedola_netta_annua = inv * (bond['ced'] / 100) * (1 - tax / 100) if bond['freq'] > 0 else 0
            tot_cedole = cedola_netta_annua * anni
            rimborso = inv
            tasse_capital_gain = max(0, inv - prezzo_tot) * (tax / 100)
            incasso_finale = tot_cedole + rimborso - tasse_capital_gain - comm
            guadagno = incasso_finale - prezzo_tot
            valore_reale = incasso_finale / ((1 + infl/100) ** anni)
            
            st.markdown(f"""
            <div class="premium-card">
                <h3 style="color:var(--primary); margin-bottom:20px;">💎 Risultato Finale</h3>
                
                <div style="display:flex; justify-content:space-between; margin:12px 0; padding:12px; background:rgba(0,217,177,0.05); border-radius:8px;">
                    <span>Spesa Oggi</span>
                    <strong style="color:var(--danger);">-{prezzo_tot:,.2f}€</strong>
                </div>
                
                <div style="display:flex; justify-content:space-between; margin:12px 0; padding:12px; background:rgba(38,222,129,0.05); border-radius:8px;">
                    <span>Incasso Futuro</span>
                    <strong style="color:var(--success);">+{incasso_finale:,.2f}€</strong>
                </div>
                
                <div style="display:flex; justify-content:space-between; margin:12px 0; padding:12px; background:rgba(102,126,234,0.05); border-radius:8px; border-top:2px solid var(--primary);">
                    <span style="font-size:18px; font-weight:700;">Guadagno Netto</span>
                    <strong style="font-size:22px; color:var(--primary);">{guadagno:+,.2f}€</strong>
                </div>
                
                <hr style="border-color:var(--border); margin:20px 0;">
                
                <div style="font-size:14px; color:var(--text-muted);">
                    <div style="margin:8px 0;">✓ Cedole Nette: {tot_cedole:,.2f}€</div>
                    <div style="margin:8px 0;">✓ Rimborso: {rimborso:,.2f}€</div>
                    <div style="margin:8px 0;">✗ Tasse: -{tasse_capital_gain:,.2f}€</div>
                    <div style="margin:8px 0;">✗ Commissioni: -{comm:,.2f}€</div>
                </div>
                
                <div style="margin-top:20px; padding:16px; background:rgba(255,165,0,0.1); border-radius:8px; border-left:4px solid var(--warning);">
                    <strong>⚠️ Valore Reale (dopo inflazione {infl}%):</strong><br>
                    I tuoi {incasso_finale:,.2f}€ varranno <strong>{valore_reale:,.2f}€</strong> di oggi
                </div>
            </div>
            """, unsafe_allow_html=True)

def page_diversificazione():
    st.title("🧮 Costruttore Portafoglio Diversificato")
    st.caption("Crea un portafoglio bilanciato in modo automatico e sicuro")
    
    # Spiegazione Premium
    st.markdown("""
    <div class="premium-card" style="margin-bottom:24px;">
        <h3 style="color:var(--primary); margin-bottom:16px;">💡 Perché Diversificare?</h3>
        <p style="line-height:1.6; color:var(--text-main);">
        La diversificazione è la <strong>regola d'oro</strong> degli investimenti. Significa:<br><br>
        ✓ <strong>Mai più del 20%</strong> del capitale su un singolo bond<br>
        ✓ <strong>Distribuire le scadenze</strong> (Bond Ladder): avere bond che scadono in anni diversi<br>
        ✓ <strong>Mix di emittenti</strong>: non solo BTP, ma anche bond di altri paesi/aziende solide<br><br>
        <strong style="color:var(--warning);">⚠️ Senza diversificazione:</strong> Se un bond fallisce, perdi tutto.<br>
        <strong style="color:var(--success);">✅ Con diversificazione:</strong> Se un bond ha problemi, gli altri compensano.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Input Utente
    col1, col2, col3 = st.columns(3)
    
    with col1:
        capitale = st.number_input(
            "💰 Capitale Totale (€)",
            min_value=5000.0,
            value=50000.0,
            step=5000.0,
            help="Quanto vuoi investire in totale?"
        )
    
    with col2:
        num_bond = st.slider(
            "🎯 Numero di Bond",
            min_value=3,
            max_value=10,
            value=5,
            help="In quanti bond diversi vuoi distribuire il capitale?"
        )
    
    with col3:
        profilo = st.selectbox(
            "⚠️ Profilo di Rischio",
            ["Conservativo", "Moderato", "Aggressivo"],
            help="Conservativo = Solo Governativi | Moderato = Gov + Bancari | Aggressivo = Tutti"
        )
    
    # Opzioni Avanzate
    with st.expander("⚙️ Opzioni Avanzate"):
        col_a1, col_a2 = st.columns(2)
        solo_gov = col_a1.checkbox("Solo Governativi (BTP, Bund, ecc.)", value=(profilo == "Conservativo"))
        max_peso_pct = col_a2.slider("Max % per singolo bond", 10, 40, 20)
        anni_target = st.slider("Scadenza media target (anni)", 1, 15, 5)
    
    if st.button("🚀 Costruisci Portafoglio", type="primary", use_container_width=True):
        with st.spinner("🔍 Analisi del mercato in corso..."):
            df_market = carica_dati_mercato()
            
            if df_market.empty:
                st.error("❌ Database vuoto. Aggiorna i dati dalla sidebar.")
                return
            
            # Filtri per profilo
            if profilo == "Conservativo" or solo_gov:
                df_filt = df_market[df_market['Categoria'] == 'Governativo']
            elif profilo == "Moderato":
                df_filt = df_market[df_market['Categoria'].isin(['Governativo', 'Bancario'])]
            else:
                df_filt = df_market
            
            # Filtro scadenze
            df_filt = df_filt[
                (df_filt['Anni'] >= anni_target * 0.5) &
                (df_filt['Anni'] <= anni_target * 1.5)
            ]
            
            if len(df_filt) < num_bond:
                st.warning(f"⚠️ Trovati solo {len(df_filt)} bond. Rilassa i filtri o riduci il numero di bond.")
                return
            
            # Costruzione Ladder
            capitale_per_bond = capitale / num_bond
            max_capitale = (capitale * max_peso_pct) / 100
            
            step_anni = (df_filt['Anni'].max() - df_filt['Anni'].min()) / num_bond
            portfolio = []
            
            for i in range(num_bond):
                anni_min = df_filt['Anni'].min() + (i * step_anni)
                anni_max = anni_min + step_anni
                
                bucket = df_filt[
                    (df_filt['Anni'] >= anni_min) &
                    (df_filt['Anni'] < anni_max)
                ]
                
                if not bucket.empty:
                    best = bucket.nlargest(1, 'YTM_Grezzo').iloc[0]
                    alloc = min(capitale_per_bond, max_capitale)
                    
                    portfolio.append({
                        'ISIN': best['ISIN'],
                        'Desc': best['Desc'][:50] + "...",
                        'Categoria': best['Categoria'],
                        'YTM': best['YTM_Grezzo'],
                        'Scadenza': best['Scadenza'],
                        'Anni': best['Anni'],
                        'Allocazione': alloc,
                        'Peso %': (alloc / capitale) * 100
                    })
            
            df_port = pd.DataFrame(portfolio)
            
            # === RISULTATI PREMIUM ===
            st.success(f"✅ Portafoglio costruito con {len(df_port)} bond!")
            
            st.divider()
            
            # KPI
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            
            with col_k1:
                st.markdown(f"""
                <div class="metric-premium">
                    <div class="metric-value">{df_port['Allocazione'].sum():,.0f}€</div>
                    <div class="metric-label">Capitale Allocato</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_k2:
                ytm_ponderato = (df_port['YTM'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum()
                st.markdown(f"""
                <div class="metric-premium">
                    <div class="metric-value">{ytm_ponderato:.2f}%</div>
                    <div class="metric-label">YTM Medio</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_k3:
                scad_media = (df_port['Anni'] * df_port['Allocazione']).sum() / df_port['Allocazione'].sum()
                st.markdown(f"""
                <div class="metric-premium">
                    <div class="metric-value">{scad_media:.1f}</div>
                    <div class="metric-label">Scadenza Media (Anni)</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_k4:
                st.markdown(f"""
                <div class="metric-premium">
                    <div class="metric-value">{len(df_port['Categoria'].unique())}</div>
                    <div class="metric-label">Categorie</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            # Tabella Premium
            st.markdown("### 📋 Il Tuo Portafoglio")
            
            st.dataframe(
                df_port[['ISIN', 'Desc', 'Categoria', 'YTM', 'Anni', 'Allocazione', 'Peso %']].style.format({
                    'YTM': '{:.2f}%',
                    'Anni': '{:.1f}',
                    'Allocazione': '{:,.0f}€',
                    'Peso %': '{:.1f}%'
                }).background_gradient(subset=['YTM'], cmap='RdYlGn'),
                use_container_width=True
            )
            
            st.divider()
            
            # Grafici
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                fig_pie = px.pie(
                    df_port,
                    values='Allocazione',
                    names='Desc',
                    title='Distribuzione Capitale',
                    color_discrete_sequence=px.colors.sequential.Viridis
                )
                fig_pie.update_layout(template="plotly_dark", height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_g2:
                fig_bar = px.bar(
                    df_port,
                    x='Anni',
                    y='Allocazione',
                    color='YTM',
                    title='Ladder: Scadenze Distribuite',
                    color_continuous_scale='Viridis'
                )
                fig_bar.update_layout(template="plotly_dark", height=400)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.divider()
            
            # === VERIFICA RISCHI ===
            st.markdown("### 🛡️ Verifica Automatica Rischi")
            
            max_peso = df_port['Peso %'].max()
            
            if max_peso > 25:
                st.markdown(f"""
                <div class="alert-critical">
                    🚨 <strong>RISCHIO CONCENTRAZIONE!</strong><br><br>
                    Un bond pesa il <strong>{max_peso:.1f}%</strong> del portafoglio.<br>
                    La regola dice: <strong>mai oltre il 20%</strong>.<br><br>
                    <strong>📌 AZIONE:</strong> Riduci il peso massimo per bond o aumenta il numero di bond.
                </div>
                """, unsafe_allow_html=True)
            elif max_peso > 20:
                st.markdown(f"""
                <div class="alert-warning">
                    ⚠️ <strong>Attenzione Concentrazione</strong><br><br>
                    Un bond pesa il <strong>{max_peso:.1f}%</strong>. È al limite.<br>
                    Ideale: sotto il 20%.
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="alert-success">
                    ✅ <strong>Diversificazione Ottimale!</strong><br><br>
                    Massimo peso: <strong>{max_peso:.1f}%</strong><br>
                    Il portafoglio è ben bilanciato. Nessun bond è troppo concentrato.
                </div>
                """, unsafe_allow_html=True)
            
            # Verifica scadenze
            scad_range = df_port['Anni'].max() - df_port['Anni'].min()
            if scad_range < 2:
                st.warning(f"⚠️ Le scadenze sono troppo concentrate ({scad_range:.1f} anni di range). Ideale: almeno 3-5 anni di differenza.")
            else:
                st.success(f"✅ Bond Ladder efficace: scadenze distribuite su {scad_range:.1f} anni.")

def page_dashboard():
    st.title("📊 Dashboard Mercato")
    st.caption("Vista d'insieme del mercato obbligazionario")
    
    with st.spinner("Caricamento dati..."):
        df = carica_dati_mercato()
    
    if df.empty:
        st.error("❌ Database vuoto. Aggiorna i dati dalla sidebar.")
        return
    
    # KPI Globali
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-premium">
            <div class="metric-value">{len(df)}</div>
            <div class="metric-label">Bond Disponibili</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-premium">
            <div class="metric-value">{df['YTM_Grezzo'].mean():.2f}%</div>
            <div class="metric-label">YTM Medio</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-premium">
            <div class="metric-value">{df['Prezzo'].mean():.2f}€</div>
            <div class="metric-label">Prezzo Medio</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-premium">
            <div class="metric-value">{df['Anni'].mean():.1f}</div>
            <div class="metric-label">Scadenza Media (Anni)</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Top 10
    st.markdown("### 🏆 Top 10 Rendimenti")
    
    top10 = df.nlargest(10, 'YTM_Grezzo')
    
    col_t1, col_t2 = st.columns([1, 1])
    
    with col_t1:
        st.dataframe(
            top10[['ISIN', 'Desc', 'YTM_Grezzo', 'Prezzo']].style.format({
                'YTM_Grezzo': '{:.2f}%',
                'Prezzo': '{:.2f}€'
            }),
            use_container_width=True,
            hide_index=True
        )
    
    with col_t2:
        fig = px.bar(
            top10,
            x='YTM_Grezzo',
            y='Desc',
            orientation='h',
            color='YTM_Grezzo',
            color_continuous_scale='RdYlGn',
            title='Top 10 per Rendimento'
        )
        fig.update_layout(template="plotly_dark", height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# MAIN APP
# ==============================================================================

def main_app():
    sidebar_premium()
    
    if st.session_state.page == "Scanner":
        page_scanner()
    elif st.session_state.page == "Diversificazione":
        page_diversificazione()
    elif st.session_state.page == "Dashboard":
        page_dashboard()
    else:
        st.info("🚧 Pagina in costruzione")

if st.session_state.logged_in:
    main_app()
else:
    login()
