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
        padding: 15px; border-radius: 10px; margin-bottom: 10px; height: 100%;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: white;
    }
    .cat-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; }
    .cat-desc { font-size: 14px; opacity: 0.95; margin-bottom: 8px; line-height: 1.4; }
    .cat-meta { font-size: 12px; font-weight: bold; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
    
    .bg-gov { background: linear-gradient(135deg, #1a4a2e 0%, #28a745 100%); }
    .bg-bank { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); }
    .bg-corp { background: linear-gradient(135deg, #1e3a5f 0%, #17a2b8 100%); }
    .bg-spec { background: linear-gradient(135deg, #581845 0%, #d63384 100%); }

    /* --- SCONTRINO --- */
    .receipt-box { border-radius: 8px; padding: 15px; margin-bottom: 10px; background-color: rgba(255, 255, 255, 0.02); }
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
# 4. FUNZIONI CORE: MATEMATICA E LOGICA FINANZIARIA (UNIFICATE)
# ==============================================================================

def identifica_tipo_bond(desc):
    """Capisce il tipo di struttura del bond dalla descrizione."""
    desc = desc.upper()
    if "ZERO COUPON" in desc or " ZC " in desc: return "ZC"
    if "CUMULATIVE" in desc or " CUM " in desc: return "CUMULATIVE"
    if "STEP UP" in desc: return "STEP_UP"
    return "STANDARD"

def stima_tassazione(desc, emittente=""):
    """Determina l'aliquota fiscale corretta (12.5% vs 26%)."""
    s = (str(desc) + " " + str(emittente)).upper()
    white_list = ["BTP", "BOT", "CCT", "CTZ", "ITALIA", "REPUBBLICA", "GERMANIA", "BUND", "SCHATZ", 
                  "BOBL", "OAT", "FRANCE", "USA", "TREASURY", "T-NOTE", "T-BOND", "SPAIN", "BONOS", 
                  "BEI", "EIB", "EBRD", "WORLD BANK", "EU ", "EUROPEAN UNION", "KFW", "IADB", "ROMANIA", 
                  "HUNGARY", "POLAND", "SUPRANATIONAL"]
    if any(k in s for k in white_list): return 12.5
    return 26.0

def calcola_rendimento_smart(prezzo, cedola, scadenza_date, descrizione, isin):
    """
    Calcola il rendimento (YTM) gestendo correttamente:
    1. Bond Standard (Cedola annuale)
    2. Zero Coupon (Nessuna cedola)
    3. Cumulative/Callable (Accumulo finale, es. Barclays 2044)
    """
    try:
        if prezzo <= 0: return 0.0, 0.0
        oggi = date.today()
        if scadenza_date <= oggi: return 0.0, 0.0
        anni_residui = (scadenza_date - oggi).days / 365.25
        desc = descrizione.upper()
        
        # 1. IDENTIFICAZIONE TIPO
        is_cumulative = False
        keywords_cumulative = ["CUMULATIVE", "ACCUMULATE", "ZERO COUPON", " ZC ", "STRIP"]
        if any(k in desc for k in keywords_cumulative): is_cumulative = True
        elif cedola > 5.0 and prezzo < 98.0 and anni_residui > 5: is_cumulative = True # Euristica per Callable Cumulative

        # 2. DETERMINAZIONE TASSE
        tax_rate = stima_tassazione(desc) / 100.0

        # 3. CALCOLO YTM LORDO
        ytm_lordo = 0.0
        if is_cumulative or cedola == 0:
            # ZC o Cumulative: Tutto alla fine
            # Rimborso Finale Stima = 100 + (Cedola * Anni) se Cumulative, altrimenti 100
            valore_rimborso = 100.0 + (cedola * anni_residui if "CUM" in desc or cedola > 0 else 0)
            ytm_lordo = ((valore_rimborso / prezzo) ** (1 / anni_residui) - 1) * 100
        else:
            # Standard
            guadagno_capitale_annuo = (100 - prezzo) / anni_residui
            capitale_medio = (100 + prezzo) / 2
            ytm_lordo = ((cedola + guadagno_capitale_annuo) / capitale_medio) * 100

        # 4. CALCOLO YTM NETTO
        ytm_netto = 0.0
        if is_cumulative or cedola == 0:
             ytm_netto = ytm_lordo * (1 - tax_rate)
        else:
            cedola_netta = cedola * (1 - tax_rate)
            plusvalenza_netta = max(0, (100 - prezzo)/anni_residui) * (1 - tax_rate)
            capitale_medio = (100 + prezzo) / 2
            ytm_netto = ((cedola_netta + plusvalenza_netta) / capitale_medio) * 100

        return round(ytm_lordo, 2), round(ytm_netto, 2)
    except Exception as e:
        return 0.0, 0.0

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq, desc, isin):
    """Wrapper per compatibilità che usa la logica smart."""
    yld_lordo, yld_netto = calcola_rendimento_smart(prezzo, cedola_pct, scadenza, desc, isin)
    
    # Calcolo Duration semplificata
    try:
        anni = (scadenza - date.today()).days / 365.25
        # Modified Duration approx
        mod_dur = anni / (1 + (yld_lordo/100)) if yld_lordo > -90 else 0
    except: mod_dur = 0
    
    return {"ytm": yld_lordo, "mod_dur": mod_dur, "ytm_netto": yld_netto}

def get_settlement_date():
    """T+2 lavorativi."""
    d = date.today()
    added = 0
    while added < 2:
        d += timedelta(days=1)
        if d.weekday() < 5: added += 1
    return d

def calcola_rateo(dati, data_valuta):
    """Calcola rateo ACT/ACT ICMA."""
    try:
        if dati['freq'] == 0: return 0.0
        scadenza = dati['sc']
        if data_valuta >= scadenza: return 0.0
        
        # Semplificazione per rateo (assumiamo cedola regolare annuale/semestrale)
        freq = int(dati['freq']) if dati['freq'] > 0 else 1
        months = 12 // freq
        
        # Trova ultimo stacco cedola teorico
        prev_c = scadenza
        while prev_c > data_valuta:
             prev_c = prev_c - timedelta(days=int(365.25/freq)) # Approx
        
        days_passed = (data_valuta - prev_c).days
        days_total = 365.25 / freq
        
        cedola_periodo = dati['ced'] / freq
        rateo = cedola_periodo * (days_passed / days_total)
        return max(0.0, rateo)
    except: return 0.0

def genera_flussi_dettagliati(dati, nominale, tax_rate, commissioni, prezzo_acquisto):
    """Genera flussi di cassa per analisi dettagliata."""
    flussi = []
    settlement = get_settlement_date()
    
    # Acquisto
    rateo_pct = calcola_rateo(dati, settlement) 
    costo_titolo = (nominale * prezzo_acquisto) / 100 
    costo_rateo_netto = (nominale * rateo_pct) / 100 * (1 - tax_rate/100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    
    flussi.append({"Data": settlement, "Tipo": "USCITA", "Importo": -spesa_totale, "Dettagli": f"Acquisto (Valuta {settlement.strftime('%d/%m')})"})
    
    # Cedole
    totale_cedole_nette = 0
    if dati['freq'] > 0 and identifica_tipo_bond(dati['desc']) == "STANDARD":
        cedola_netta = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = settlement + timedelta(days=180) # Start approx
        # Qui servirebbe logica precisa date cedola, usiamo approx per visualizzazione
        # Generiamo cedole fino a scadenza
        while curr < dati['sc']:
             flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola"})
             totale_cedole_nette += cedola_netta
             curr += timedelta(days=int(365.25/dati['freq']))
    
    # Rimborso (Gestione Cumulative)
    rimborso_lordo = nominale
    if identifica_tipo_bond(dati['desc']) == "CUMULATIVE":
        anni_tot = (dati['sc'] - settlement).days / 365.25
        rimborso_lordo += (nominale * (dati['ced']/100) * anni_tot)

    gain_prezzo = max(0, 100 - prezzo_acquisto) # Semplificato
    plusvalenza_lorda = (gain_prezzo / 100) * nominale
    tassa_gain = plusvalenza_lorda * (tax_rate / 100)
    
    rimborso_netto = rimborso_lordo - tassa_gain
    
    # Ultima cedola (se standard)
    ultima_ced = 0
    if identifica_tipo_bond(dati['desc']) == "STANDARD" and dati['freq'] > 0:
        ultima_ced = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
    
    flussi.append({"Data": dati['sc'], "Tipo": "ENTRATA", "Importo": rimborso_netto + ultima_ced, "Dettagli": "Rimborso + Ultima Cedola"})
    
    incasso_totale = totale_cedole_nette + rimborso_netto + ultima_ced
    totale_cedole_nette += ultima_ced # Add last coupon to total
    
    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole_nette, plusvalenza_lorda

# ==============================================================================
# 5. GESTIONE DATI E HELPER UI
# ==============================================================================

def valida_isin(isin):
    if not isin or len(isin) != 12: return False
    return isin[:2].isalpha() and isin[2:].isalnum()

def get_last_update_time():
    try:
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

def detect_valuta(desc, isin):
    desc = desc.upper()
    if "USA" in desc or "TREASURY" in desc or "DOLLAR" in desc: return "USD"
    if "TURCHIA" in desc or "LIRA" in desc or "TRY" in desc: return "TRY"
    if "BRASILE" in desc or "REAL" in desc: return "BRL"
    if "ROMANIA" in desc or "LEU" in desc or "RON" in desc: return "RON"
    if "GB" in isin[:2] or "UK" in desc: return "GBP"
    return "EUR"

@st.cache_data(ttl=3600)
def get_tasso_cambio_live(da, a):
    da = da.upper(); a = a.upper()
    if da == a: return 1.0
    ticker = f"{da}{a}=X"
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty: return float(data['Close'].iloc[-1])
        ticker_inv = f"{a}{da}=X"
        data_inv = yf.Ticker(ticker_inv).history(period="1d")
        if not data_inv.empty: return 1.0 / float(data_inv['Close'].iloc[-1])
    except: pass
    fallback = {"EURUSD": 1.05, "EURTRY": 36.00, "EURBRL": 6.10, "EURGBP": 0.85, "EURRON": 4.97}
    return fallback.get(f"{da}{a}", 1.0)

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
        if c_min and pd.notna(row[c_min]): 
            s = str(row[c_min]).lower().strip()
            if 'k' in s: taglio = float(s.replace('k', '')) * 1000
            else: 
                try: taglio = float(s.replace('.', '').replace(',', '.'))
                except: pass

        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating, "isin": isin_val}
    except: return None
# --- INIZIO NUOVO BLOCCO MATEMATICO ---
def calcola_rendimento_smart(prezzo, cedola, scadenza, desc):
    """
    Calcola YTM gestendo correttamente:
    1. Bond Standard (Cedola annuale) -> Usa formula classica
    2. Cumulative/Zero Coupon (Es. Barclays 2044) -> Usa formula interesse composto
    """
    try:
        if prezzo <= 0: return 0.0
        
        oggi = date.today()
        if scadenza <= oggi: return 0.0
        
        anni_residui = (scadenza - oggi).days / 365.25
        if anni_residui <= 0: return 0.0
        
        desc = str(desc).upper()
        
        # LOGICA DI RICONOSCIMENTO
        # Capisce se è un bond "Cumulative" (che paga tutto alla fine)
        is_cumulative = False
        keywords = ["CUMULATIVE", "ACCUMULATE", "ZERO COUPON", " ZC ", "STRIP"]
        
        if any(k in desc for k in keywords):
            is_cumulative = True
        # Euristica: se ha cedola alta (>5%) ma quota basso (<98) su scadenze lunghe, è accumulazione
        elif cedola > 5.0 and prezzo < 98.0 and anni_residui > 5:
            is_cumulative = True 

        # CALCOLO
        if is_cumulative or cedola == 0:
            # Formula Zero Coupon / Accumulazione
            # Valore finale = 100 + tutte le cedole accumulate (se ci sono)
            montante = 100.0 + (cedola * anni_residui if cedola > 0 else 0)
            ytm = ((montante / prezzo) ** (1 / anni_residui) - 1) * 100
        else:
            # Formula Standard (Approssimata)
            guadagno_annuo = (100 - prezzo) / anni_residui
            capitale_medio = (100 + prezzo) / 2
            ytm = ((cedola + guadagno_annuo) / capitale_medio) * 100
            
        return round(ytm, 2)
    except:
        return 0.0
# --- FINE NUOVO BLOCCO MATEMATICO ---
def carica_dati_mercato():
    all_bonds = []
    if not os.path.exists(DB_FOLDER): return pd.DataFrame()
    for filename in os.listdir(DB_FOLDER):
        if filename.endswith(".csv"):
            try:
                path = os.path.join(DB_FOLDER, filename)
                df = pd.read_csv(path)
                # Semplificazione: usiamo processa_riga simulato o custom parsing veloce
                # Qui replichiamo logica processa_riga ma vettoriale se possibile, o loop
                # Per brevità, assumiamo colonne standard o le cerchiamo
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
                            
                            # ... (codice precedente dentro il ciclo: pr, desc, ced, isin_v) ...
                            
                            cat = "Altro"
                            if any(x in desc.upper() for x in ["BTP", "BOT", "BUND", "TREASURY"]): cat = "Governativo"
                            elif any(x in desc.upper() for x in ["INTESA", "UNICREDIT", "BANCA"]): cat = "Bancario"
                            elif any(x in desc.upper() for x in ["ENI", "ENEL", "STELLANTIS"]): cat = "Corporate"
                            
                            # ### MODIFICA 1: CALCOLA IL RENDIMENTO CON LA NUOVA FUNZIONE ###
                            ytm_corretto = calcola_rendimento_smart(pr, ced, sc, desc)
                            
                            all_bonds.append({
                                "ISIN": isin_v, 
                                "Desc": desc, 
                                "Prezzo": pr, 
                                "Scadenza": sc, 
                                "Cedola": ced,
                                "YTM_Grezzo": ytm_corretto,  # ### MODIFICA 2: USA LA VARIABILE CALCOLATA SOPRA ###
                                "Anni": (sc - date.today()).days / 365.25, 
                                "Fonte": filename.replace('.csv', ''),
                                "Categoria": cat
                            })
                        except: continue
            except: continue
    return pd.DataFrame(all_bonds)

def aggiorna_db():
    if os.path.exists(DB_FOLDER):
        for f in os.listdir(DB_FOLDER):
            try: os.unlink(os.path.join(DB_FOLDER, f))
            except: pass
    
    p = st.progress(0); s = st.empty(); tot = sum(len(v) for v in SOURCES_MAP.values()); c = 0; ok = 0
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1
            s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            p.progress(c/tot)
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
                time.sleep(1) # Rispetto rate limit
            except: pass
                
    st.session_state.last_scrape_time = datetime.now()
    s.empty(); p.empty(); st.toast(f"Database Rigenerato: {ok} files.", icon="🛡️"); time.sleep(1); st.rerun()

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
                        return row, {"nome": src['nome'], "freq": src['freq'], "cat_reale": key}
            except: continue
    return None, None

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

def analizza_bond_quality_dettagliata(dati, risk, tax, patrimonio):
    breakdown = []
    score = 100
    peso_bond = (dati['taglio'] / patrimonio) * 100
    
    # 1. Sostenibilità
    if peso_bond > 20: p=-30; msg=f"Pesa {peso_bond:.1f}%"; col="score-bad"
    elif peso_bond > 10: p=-10; msg=f"Pesa {peso_bond:.1f}%"; col="score-neutral"
    else: p=0; msg="Sostenibile"; col="score-good"
    score += p
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{dati['taglio']/1000:.0f}k", "msg": msg, "pts": p, "col": col})

    # 2. Prezzo
    if dati['pr'] > 110: p=-15; msg=">110"; col="score-bad"
    elif dati['pr'] > 102: p=-5; msg=">102"; col="score-neutral"
    elif dati['pr'] < 95: p=+5; msg="<95"; col="score-good"
    else: p=0; msg="Fair"; col="score-good"
    score += p
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{dati['pr']:.2f}", "msg": msg, "pts": p, "col": col})

    # 3. Rendimento (usando YTM Netto da calcolo smart)
    if risk['ytm_netto'] < 1.5: p=-20; msg="Basso"; col="score-bad"
    elif risk['ytm_netto'] > 3.0: p=+15; msg="Ottimo"; col="score-good"
    else: p=0; msg="Medio"; col="score-neutral"
    score += p
    breakdown.append({"cat": "📈 Rend. Netto", "val": f"{risk['ytm_netto']:.2f}%", "msg": msg, "pts": p, "col": col})

    return {"score": max(0, min(100, score)), "breakdown": breakdown}

def categorizza_rischio(isin, nome, desc):
    nome = str(nome).upper(); desc = str(desc).upper(); isin = str(isin).upper()
    gov_safe = ["GERMANIA", "BUND", "FRANCIA", "OAT", "USA", "TREASURY", "BEI", "EU", "EUROPA"]
    if any(k in nome or k in desc for k in gov_safe): return 1
    gov_mid = ["ITALIA", "BTP", "BOT", "CCT", "SPAGNA", "BONOS", "INTESA", "UNICREDIT"]
    if any(k in nome or k in desc for k in gov_mid): return 2
    if isin.startswith("XS"): return 3
    if "SUB" in desc or "ROMANIA" in nome or "TURCHIA" in nome: return 4
    return 3

def trova_alternative_migliori(bond_target, df_mercato):
    if df_mercato.empty: return pd.DataFrame()
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    ytm_netto_target = bond_target.get('ytm_netto', 0) # Assumiamo sia passato o calcolato prima
    # Se non è passato, lo ricalcoliamo al volo (lento) o usiamo approx
    if ytm_netto_target == 0:
         _, ytm_netto_target = calcola_rendimento_smart(bond_target['pr'], bond_target['ced'], bond_target['sc'], bond_target['desc'], bond_target['isin'])
    
    rischio_target = categorizza_rischio(bond_target['isin'], bond_target['fonte'], bond_target['desc'])
    
    alternative = []
    for _, row in df_mercato.iterrows():
        if row['ISIN'] == bond_target['isin']: continue
        if not (anni_target - 3.0 <= row['Anni'] <= anni_target + 3.0): continue
        if row['Prezzo'] > 120: continue
        
        rischio_alt = categorizza_rischio(row['ISIN'], row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Netto']
        extra = ytm_netto_alt - ytm_netto_target
        
        tipo_switch = ""
        if rischio_alt <= rischio_target and extra > 0.01: tipo_switch = "✅ Gemello (+Safe)"
        elif rischio_alt == rischio_target + 1 and extra > 0.30: tipo_switch = "⚠️ Boost (Rischio+)"
        elif rischio_alt < rischio_target and extra > -0.20: tipo_switch = "🛡️ Rifugio (Safe)"
        elif row['Anni'] < anni_target - 1 and extra > -0.10: tipo_switch = "⏳ Scade Prima"

        if tipo_switch:
            row_dict = row.to_dict()
            row_dict['Tipologia'] = tipo_switch
            row_dict['Extra'] = extra
            row_dict['Link'] = f"https://www.google.com/search?q={row['ISIN']}+bond"
            alternative.append(row_dict)
            
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty:
        return df_alt.sort_values('Extra', ascending=False).head(10)
    return pd.DataFrame()

# ==============================================================================
# 6. UI: PAGINE SPECIFICHE
# ==============================================================================

def dashboard_mercato_ui():
    st.title("📊 Dashboard Mercato")
    st.caption("Panoramica dei rendimenti e delle opportunità attuali.")
    with st.spinner("Analisi macro in corso..."):
        df = carica_dati_mercato()
        if df.empty: st.error("❌ Database vuoto. Aggiorna i dati dalla sidebar."); return

    # KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bond Censiti", len(df))
    c2.metric("YTM Medio (Lordo)", f"{df['YTM_Grezzo'].mean():.2f}%")
    c3.metric("Prezzo Medio", f"{df['Prezzo'].mean():.2f}€")
    c4.metric("Duration Media", f"{df['Anni'].mean():.1f} anni")
    st.divider()

    # Top 10
    st.subheader("🏆 Top 10 Rendimenti Reali (Netto)")
    st.caption("Classifica basata sul rendimento netto stimato.")
    top10 = df.nlargest(10, 'YTM_Netto').sort_values('YTM_Netto', ascending=True)
    
    c_chart, c_tab = st.columns([2, 1])
    with c_chart:
        fig_top = px.bar(top10, x='YTM_Netto', y='Desc', orientation='h', text='YTM_Netto', color='YTM_Netto', color_continuous_scale='Viridis')
        fig_top.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig_top.update_layout(showlegend=False, height=400, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_top, use_container_width=True)
    with c_tab:
        st.dataframe(top10[['ISIN', 'YTM_Netto', 'Prezzo']].sort_values('YTM_Netto', ascending=False), use_container_width=True, height=400, hide_index=True)

    # Settori
    st.divider()
    st.subheader("📊 Rendimenti per Settore")
    if 'Categoria' in df.columns:
        df_cat = df.groupby('Categoria').agg({'YTM_Netto': 'mean', 'ISIN': 'count'}).reset_index()
        fig_cat = px.bar(df_cat, x='Categoria', y='YTM_Netto', text='YTM_Netto', color='Categoria')
        fig_cat.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        st.plotly_chart(fig_cat, use_container_width=True)

def bond_screener_ui():
    """Screener UX 6.0 (Trasparente e Funzionante)."""
    st.title("🌐 Global Fixed Income Ranking")
    st.caption("Analisi professionale dei rendimenti reali.")
    
    defaults = {"EUR": 2.50, "USD": 4.10, "GBP": 4.25, "CHF": 0.75, "JPY": 0.90, "CAD": 3.20, "AUD": 4.10, "TRY": 28.00, "BRL": 12.00, "ZAR": 9.50, "MXN": 9.00, "RON": 6.50, "HUF": 6.00}
    
    with st.spinner("Caricamento market data..."):
        df_market = carica_dati_mercato()
        if df_market.empty: st.error("Database offline."); return
        if 'Valuta' not in df_market.columns:
            df_market['Valuta'] = df_market.apply(lambda x: detect_valuta(x.get('Desc', ''), x.get('ISIN', '')), axis=1)

    st.divider()
    c_wal, c_scope = st.columns(2)
    with c_wal: valuta_wallet = st.selectbox("1️⃣ Valuta Portafoglio", ["EUR", "USD"], index=0)
    with c_scope: scope = st.radio("2️⃣ Universo Investibile", [f"🔒 Mercato Locale ({valuta_wallet})", "🌍 Mercato Globale (Hedged)"], index=1)

    RISK_FREE_RATES = defaults.copy()
    try:
        usd_data = yf.Ticker("^TNX").history(period="1d")
        if not usd_data.empty: RISK_FREE_RATES["USD"] = float(usd_data['Close'].iloc[-1])
    except: pass

    if "Mercato Globale" in scope:
        with st.expander("⚙️ Parametri di Mercato & Tassi (Clicca per info)", expanded=False):
            st.info("Nota Metodologica: Usiamo un approccio ibrido (USD Live + Benchmark) per i tassi risk-free.")
            cols = st.columns(5)
            keys = ["EUR", "USD", "TRY", "BRL", "ZAR"] + [k for k in RISK_FREE_RATES.keys() if k not in ["EUR", "USD", "TRY", "BRL", "ZAR"]]
            for i, key in enumerate(keys):
                with cols[i % 5]:
                    RISK_FREE_RATES[key] = st.number_input(f"{key} (%)", value=float(RISK_FREE_RATES.get(key, 0.0)), step=0.25, format="%.2f", key=f"rate_{key}")

    tasso_base = RISK_FREE_RATES.get(valuta_wallet, 3.0)
    df_work = df_market.copy()
    
    tassi_spot = {v: (1.0 if v == valuta_wallet else get_tasso_cambio_live(valuta_wallet, v)) for v in df_work['Valuta'].unique()}
    df_work['FX_Rate'] = df_work['Valuta'].map(tassi_spot).fillna(1.0)
    df_work['Prezzo_Wallet'] = df_work.apply(lambda x: x['Prezzo']/x['FX_Rate'] if x['FX_Rate']>0 else x['Prezzo'], axis=1)

    def calcola_reale(row):
        if row['Valuta'] == valuta_wallet: return row['YTM_Grezzo']
        rf_locale = RISK_FREE_RATES.get(row['Valuta'], 5.0)
        return row['YTM_Grezzo'] - (rf_locale - tasso_base)

    df_work['YTM_Reale'] = df_work.apply(calcola_reale, axis=1)
    if "Mercato Locale" in scope: df_work = df_work[df_work['Valuta'] == valuta_wallet]

    st.subheader("🛠️ Criteri di Selezione")
    c1, c2, c3, c4 = st.columns(4)
    with c1: min_y = st.number_input(f"Yield {valuta_wallet} Min (%)", value=2.0, step=0.5)
    with c2: max_p = st.number_input(f"Prezzo Max ({valuta_wallet})", value=120.0, step=1.0)
    with c3: min_d = st.number_input("Scadenza Min (Anni)", value=0.0, step=1.0)
    with c4: max_d = st.number_input("Scadenza Max (Anni)", value=30.0, step=1.0)

    cats = ["🌐 TUTTE"] + sorted(df_work['Categoria'].unique().tolist())
    sel_cat = st.multiselect("Settore Emittente", cats, default=["🌐 TUTTE"])

    st.write("")
    if st.button("🚀 TROVA OPPORTUNITÀ", type="primary", use_container_width=True):
        res = df_work[(df_work['YTM_Reale'] >= min_y) & (df_work['Anni'] >= min_d) & (df_work['Anni'] <= max_d) & (df_work['Prezzo_Wallet'] <= max_p)]
        if sel_cat and "🌐 TUTTE" not in sel_cat: res = res[res['Categoria'].isin(sel_cat)]
        res = res.sort_values('YTM_Reale', ascending=False)

        if res.empty: st.warning("Nessun risultato.")
        else:
            st.success(f"Trovati **{len(res)}** titoli.")
            st.dataframe(res[['Desc', 'Valuta', 'Prezzo_Wallet', 'YTM_Reale', 'YTM_Grezzo', 'Anni', 'ISIN']].head(100), use_container_width=True, height=600, hide_index=True)

def diversificazione_portfolio_ui():
    st.title("🧩 Costruisci il tuo Portafoglio (Robo-Advisor)")
    st.caption("Il sistema seleziona i titoli migliori escludendo i bond rischiosi o complessi.")

    with st.spinner("Analisi database..."):
        df = carica_dati_mercato()
        if df.empty: st.error("Database vuoto."); return

    # INPUT
    st.subheader("1️⃣ Obiettivi")
    c1, c2 = st.columns(2)
    with c1: capitale = st.number_input("Capitale (€)", 5000.0, 500000.0, 20000.0, step=1000.0)
    with c2: n_bond = st.slider("Numero Titoli", 3, 10, 5)

    st.divider()
    
    # PROFILI
    PROFILI = {
        "🛡️ Prudente": {"alloc": {"Gov": 1.0, "Corp": 0.0, "HY": 0.0}, "max_anni": 5, "desc": "Solo Governativi (BTP/Bund) a breve termine."},
        "⚖️ Bilanciato": {"alloc": {"Gov": 0.6, "Corp": 0.4, "HY": 0.0}, "max_anni": 10, "desc": "Mix Governativi e Aziendali solidi."},
        "🚀 Aggressivo": {"alloc": {"Gov": 0.2, "Corp": 0.4, "HY": 0.4}, "max_anni": 30, "desc": "Punta al massimo rendimento (include High Yield)."}
    }
    
    scelta = st.radio("2️⃣ Profilo Rischio", list(PROFILI.keys()), horizontal=True, index=1)
    p_data = PROFILI[scelta]
    st.info(f"💡 **Strategia:** {p_data['desc']}")

    if st.button("✨ Genera Portafoglio", type="primary", use_container_width=True):
        # Logica di selezione
        df_work = df.copy()
        
        # Filtra via i bond 'strani' o cumulative per sicurezza
        df_work = df_work[~df_work['Desc'].str.contains("CUMULATIVE|ZC", case=False, na=False)]

        def get_type(row):
            s = (str(row['Desc']) + str(row['Categoria'])).upper()
            if any(x in s for x in ["TRY", "ZAR", "PEMEX", "SUB", "BRL"]): return "HY"
            if any(x in s for x in ["BTP", "BOT", "BUND", "TREASURY", "USA"]): return "Gov"
            return "Corp"
        
        df_work['Asset'] = df_work.apply(get_type, axis=1)
        
        portfolio = []
        used = []
        
        # Calcolo slot
        for asset, peso in p_data['alloc'].items():
            count = int(round(n_bond * peso))
            # Cerca i migliori per quell'asset
            cands = df_work[
                (df_work['Asset'] == asset) & 
                (df_work['Anni'] <= p_data['max_anni']) & 
                (~df_work['ISIN'].isin(used))
            ]
            
            # Criterio: Prudente -> Meno anni / Aggressivo -> Più rendimento
            if scelta == "🛡️ Prudente":
                cands = cands.sort_values('Anni', ascending=True)
            else:
                cands = cands.sort_values('YTM_Grezzo', ascending=False)
            
            # Prendi i top N
            for _, row in cands.head(count).iterrows():
                portfolio.append(row)
                used.append(row['ISIN'])
        
        # Visualizzazione
        if portfolio:
            res = pd.DataFrame(portfolio)
            res['Investimento'] = capitale / len(res)
            
            st.success("✅ Portafoglio Generato!")
            
            # KPI
            cedola_media = res['Cedola'].mean()
            ytm_medio = res['YTM_Grezzo'].mean()
            k1, k2, k3 = st.columns(3)
            k1.metric("Rendimento Medio", f"{ytm_medio:.2f}%")
            k2.metric("Cedola Media", f"{cedola_media:.2f}%")
            k3.metric("Scadenza Media", f"{res['Anni'].mean():.1f} anni")
            
            st.dataframe(
                res[['Desc', 'Asset', 'Prezzo', 'Cedola', 'YTM_Grezzo', 'Anni', 'Investimento']], 
                use_container_width=True,
                column_config={
                    "Investimento": st.column_config.NumberColumn("Allocato", format="%.0f €"),
                    "YTM_Grezzo": st.column_config.NumberColumn("Rendimento", format="%.2f%%"),
                    "Prezzo": st.column_config.NumberColumn("Prezzo", format="%.2f"),
                    "Anni": st.column_config.NumberColumn("Durata", format="%.1f y"),
                }
            )
        else:
            st.warning("Non ho trovato abbastanza bond per soddisfare i criteri.")

def alert_manager_ui():
    st.title("🔔 Alert Intelligenti")
    st.info("Funzione di simulazione.")
    if st.button("➕ Crea Alert Prezzo < 95"):
        st.session_state.alerts.append({"Tipo": "Prezzo", "Target": 95, "Data": date.today()})
        st.success("Alert Aggiunto!")
    if st.session_state.alerts:
        st.write(st.session_state.alerts)

def smart_analysis_ui():
    st.title("🧠 Smart Analysis")
    with st.spinner("Caricamento..."):
        df = carica_dati_mercato()
    
    isin = st.text_input("Inserisci ISIN", value=st.session_state.selected_isin_from_chart or "").strip().upper()
    if st.session_state.selected_isin_from_chart: st.session_state.selected_isin_from_chart = None

    if isin:
        row, info = cerca_db(isin, None)
        if row is not None:
            d = processa_riga(row, info)
            st.success(f"Trovato: {d['desc']}")
            
            # Grafico
            st.subheader("Mappa Mercato")
            fig = px.scatter(df, x='Anni', y='YTM_Grezzo', color='Categoria', hover_data=['Desc', 'ISIN'])
            fig.add_trace(go.Scatter(x=[(d['sc']-date.today()).days/365.25], y=[d['ced']], mode='markers', marker=dict(color='red', size=15, symbol='star'), name='TUO BOND'))
            st.plotly_chart(fig, use_container_width=True)

            # Alternative
            st.subheader("Alternative Migliori")
            alt = trova_alternative_migliori(d, df) # Assumiamo d abbia i campi giusti, se no bisogna adattare
            if not alt.empty: st.dataframe(alt[['Tipologia', 'Desc', 'YTM_Netto', 'Extra']])
            else: st.info("Nessuna alternativa migliore trovata.")
        else: st.error("ISIN non trovato.")

def scanner_ui():
    st.title("🔎 Scanner Singolo")
    col1, col2 = st.columns([3,1])
    with col1: isin = st.text_input("ISIN").strip().upper()
    with col2: 
        st.write("") 
        btn = st.button("Analizza", type="primary", use_container_width=True)
    
    if isin and btn:
        if not valida_isin(isin): st.error("ISIN non valido")
        else:
            row, info = cerca_db(isin, None)
            if row is not None:
                d = processa_riga(row, info)
                
                # Header Style
                st.markdown(f"""
                <div style="background:#1e2130; padding:20px; border-radius:10px; border-left:5px solid #00CC96;">
                    <h2 style="margin:0; color:white;">{d['desc']}</h2>
                    <p style="color:#00CC96; margin:0;">{d['fonte']} | Cedola {d['ced']}%</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Metriche
                risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'], d['desc'], d['isin'])
                tax = stima_tassazione(d['desc'])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Prezzo", f"{d['pr']}€")
                c2.metric("YTM Lordo", f"{risk['ytm']:.2f}%")
                c3.metric("YTM Netto", f"{risk['ytm_netto']:.2f}%") # Ora corretto anche per ZC/Cumulative
                c4.metric("Duration", f"{risk['mod_dur']:.2f}")

                st.divider()
                
                # Flussi
                df_flussi, spesa, incasso, _, _, _ = genera_flussi_dettagliati(d, 10000, tax, 5, d['pr'])
                
                col_sx, col_dx = st.columns(2)
                with col_sx:
                    st.subheader("📉 Uscite")
                    st.error(f"Totale Spesa: {spesa:.2f}€")
                with col_dx:
                    st.subheader("📈 Entrate")
                    st.success(f"Totale Incasso: {incasso:.2f}€")
                    st.caption(f"Guadagno Netto: {incasso-spesa:.2f}€")

                st.dataframe(df_flussi, use_container_width=True)

            else: st.error("Bond non trovato.")

# ==============================================================================
# 7. MAIN APP ROUTING
# ==============================================================================

def main_app():
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        if st.session_state.current_user:
            st.markdown(f"""<div class="user-box">👤 {st.session_state.current_user.capitalize()}</div>""", unsafe_allow_html=True)
        
        st.subheader("🧭 MENU")
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🎯 Screener Avanzato", use_container_width=True): st.session_state.page = "Screener"; st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True): st.session_state.page = "SmartAnalysis"; st.rerun()
        if st.button("📊 Dashboard Mercato", use_container_width=True): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True): st.session_state.page = "Diversificazione"; st.rerun()
        if st.button("🔔 Alert Manager", use_container_width=True): st.session_state.page = "Alerts"; st.rerun()

        st.divider()
        if st.button("🔄 AGGIORNA DATI", type="primary", use_container_width=True):
            aggiorna_db()
        
        if st.button("🚪 Logout"): 
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

    if st.session_state.page == "Scanner": scanner_ui()
    elif st.session_state.page == "Screener": bond_screener_ui()
    elif st.session_state.page == "SmartAnalysis": smart_analysis_ui()
    elif st.session_state.page == "Dashboard": dashboard_mercato_ui()
    elif st.session_state.page == "Diversificazione": diversificazione_portfolio_ui()
    elif st.session_state.page == "Alerts": alert_manager_ui()

def login():
    st.title("🔒 Login Terminale")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        u = st.text_input("Utente", placeholder="es. giulio").strip()
        p = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                st.query_params["session"] = hashlib.sha256((u + "salt").encode()).hexdigest()
                st.rerun()
            else: st.error("Credenziali Errate")

if st.session_state.logged_in:
    main_app()
else:
    login()
