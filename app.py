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

# --- CONFIGURAZIONE & CSS ---
st.set_page_config(
    page_title="Bond Research Terminal", 
    page_icon="🏛️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* --- 1. STILE CARD RISCHIO (TESTO BIANCO) --- */
    .metric-card {
        background-color: #1e2130; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #3e445b; 
        margin-bottom: 10px;
        color: #ffffff !important;
    }
    .metric-card b {
        color: #00CC96;
    }

    /* --- 2. MENU SIDEBAR (TESTO NERO) --- */
    [data-testid="stSidebar"] div.stButton > button {
        background-color: transparent; 
        border: none; 
        text-align: left; 
        color: #000000 !important;
        box-shadow: none; 
        padding-left: 0; 
        font-size: 16px; 
        font-weight: 600;
        transition: all 0.2s;
    }
    [data-testid="stSidebar"] div.stButton > button:hover {
        color: #333333 !important;
        padding-left: 10px; 
        background-color: rgba(0,0,0,0.05); 
        border-radius: 5px;
    }
    [data-testid="stSidebar"] div.stButton > button:focus {
        box-shadow: none; 
        color: #000000 !important; 
        font-weight: bold;
        border-left: 3px solid #00CC96;
    }

    /* --- 3. LEGENDA MIGLIORATA --- */
    .legend-box { 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        font-size: 14px; 
        color: white; 
        height: 100%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        line-height: 1.5;
    }
    .legend-title { 
        font-weight: bold; 
        font-size: 16px; 
        display: block; 
        margin-bottom: 8px; 
        border-bottom: 1px solid rgba(255,255,255,0.3); 
        padding-bottom: 4px;
        text-transform: uppercase;
    }
    
    /* Colori Categorie Legenda */
    .gov { background-color: #1a4a2e; border: 1px solid #28a745; }
    .bank { background-color: #2c3e50; border: 1px solid #8e9aaf; }
    .corp { background-color: #1e3a5f; border: 1px solid #17a2b8; }
    .spec { background-color: #581845; border: 1px solid #d63384; }

    /* Altri Stili Generali */
    .red-flag {
        border-left: 5px solid #ff4b4b; 
        background-color: #2d1b1b; 
        padding: 10px; 
        margin-bottom: 5px; 
        color: white;
        border-radius: 4px;
    }
    .green-flag {
        border-left: 5px solid #00cc96; 
        background-color: #1b2d24; 
        padding: 10px; 
        margin-bottom: 5px; 
        color: white;
        border-radius: 4px;
    }
    .warning-flag {
        border-left: 5px solid #ffa500; 
        background-color: #2d2a1b; 
        padding: 10px; 
        margin-bottom: 5px; 
        color: white;
        border-radius: 4px;
    }
    .main-header {
        font-size: 24px; 
        font-weight: bold; 
        color: white;
    }
    .sub-header {
        font-size: 14px; 
        color: #b0b3c5;
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAZIONE SICURA ---
# Usa variabili d'ambiente per credenziali in produzione
SEGRETO_UTENTE = os.getenv("BOND_USER", "giulio")
SEGRETO_PASSWORD_HASH = hashlib.sha256(
    os.getenv("BOND_PASS", "Giulio99mac!").encode()
).hexdigest()

# CARTELLA DATABASE LOCALE
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# --- STATO (Session State) con inizializzazione robusta ---
def init_session_state():
    defaults = {
        'portfolio': [],
        'confronto': None,
        'logged_in': False,
        'connection_status': "In attesa...",
        'page': "Scanner",
        'last_scrape_time': None,
        'scrape_count': 0
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- MAPPA FONTI ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT_FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- VALIDAZIONE INPUT ---
def valida_isin(isin):
    """Valida formato ISIN (2 lettere + 10 alfanumerici)"""
    if not isin or len(isin) != 12:
        return False
    if not isin[:2].isalpha() or not isin[2:].isalnum():
        return False
    return True

# --- GESTIONE FILES & CONNESSIONE ---
def get_last_update_time():
    """Restituisce la data dell'ultimo aggiornamento del database"""
    try:
        if not os.path.exists(DB_FOLDER):
            return None
        files = [
            os.path.join(DB_FOLDER, f) 
            for f in os.listdir(DB_FOLDER) 
            if f.endswith('.csv')
        ]
        if not files:
            return None
        latest_file = max(files, key=os.path.getmtime)
        return datetime.fromtimestamp(os.path.getmtime(latest_file))
    except Exception as e:
        st.error(f"Errore lettura timestamp: {e}")
        return None

def check_connection_status():
    """Controlla lo stato della connessione"""
    try:
        # Test connessione internet
        requests.get("https://www.google.com", timeout=3)
        
        # Test sito target
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.head(
            "https://www.simpletoolsforinvestors.eu/", 
            headers=headers, 
            timeout=5
        )
        
        if r.status_code == 200:
            return "🟢 ONLINE"
        elif r.status_code in [403, 429]:
            return "🔴 BANNATO (403/429)"
        else:
            return f"🟡 STATUS {r.status_code}"
    except requests.exceptions.Timeout:
        return "🔴 TIMEOUT"
    except requests.exceptions.ConnectionError:
        return "🔴 OFFLINE"
    except Exception as e:
        return f"🔴 ERRORE: {str(e)[:20]}"

# --- CALCOLI FINANZIARI MIGLIORATI ---
def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """
    Calcola YTM con metodo Newton-Raphson (più preciso)
    """
    if prezzo <= 0 or freq == 0:
        return None
    
    cedola_annua = cedola_pct / 100
    giorni = (scadenza - date.today()).days
    anni = giorni / 365.25
    
    if anni <= 0:
        return None
    
    n_periodi = max(1, int(anni * freq))
    c = (cedola_annua * face_value) / freq
    
    # Stima iniziale YTM
    ytm_guess = (cedola_annua + (face_value - prezzo) / anni) / ((face_value + prezzo) / 2)
    
    def price_func(y):
        """Funzione prezzo bond"""
        if y <= -1:
            return float('inf')
        pv = sum([c / ((1 + y/freq) ** t) for t in range(1, n_periodi + 1)])
        pv += face_value / ((1 + y/freq) ** n_periodi)
        return pv - prezzo
    
    def price_deriv(y):
        """Derivata del prezzo rispetto a y"""
        if y <= -1:
            return 0
        dpv = sum([
            -t * c / (freq * ((1 + y/freq) ** (t + 1))) 
            for t in range(1, n_periodi + 1)
        ])
        dpv += -n_periodi * face_value / (freq * ((1 + y/freq) ** (n_periodi + 1)))
        return dpv
    
    try:
        ytm = newton(price_func, ytm_guess, fprime=price_deriv, maxiter=100, tol=1e-6)
        return max(0, ytm)  # YTM non può essere negativo
    except:
        # Fallback a stima semplice
        return ytm_guess

def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """
    Calcola Duration, Convexity, DV01 con YTM preciso
    """
    if prezzo <= 0:
        return None
    
    # YTM preciso
    ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value)
    if ytm is None:
        return None
    
    cedola = cedola_pct / 100
    giorni = (scadenza - date.today()).days
    anni = giorni / 365.25
    
    if anni <= 0:
        return None
    
    n_periodi = max(1, int(anni * freq))
    
    # Cash flows
    if freq > 0:
        periodi_tempo = np.arange(1, n_periodi + 1) / freq
        cash_flows = np.full(n_periodi, (cedola * face_value) / freq)
        cash_flows[-1] += face_value
    else:
        # Zero coupon
        periodi_tempo = np.array([anni])
        cash_flows = np.array([face_value])
        freq = 1  # Per calcoli
    
    # Fattori di sconto
    discount_factors = (1 + ytm / freq) ** (-periodi_tempo * freq)
    
    # Macaulay Duration
    pv_cf = cash_flows * discount_factors
    mac_duration = np.sum(periodi_tempo * pv_cf) / prezzo
    
    # Modified Duration
    mod_duration = mac_duration / (1 + ytm / freq)
    
    # Convexity
    convexity = np.sum(
        cash_flows * periodi_tempo * (periodi_tempo + 1/freq) * 
        ((1 + ytm/freq) ** (-(periodi_tempo * freq + 2)))
    ) / prezzo
    
    # DV01 (Dollar Value of 01 basis point per 100 nominale)
    dv01 = mod_duration * prezzo * 0.0001
    
    return {
        "ytm": ytm * 100,
        "mod_dur": mod_duration,
        "mac_dur": mac_duration,
        "convexity": convexity,
        "dv01": dv01
    }

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    """
    Calcola variazione prezzo con shock tassi (Taylor expansion)
    """
    shock = shock_bps / 10000
    delta_prezzo = (
        -mod_dur * shock + 
        0.5 * convexity * (shock ** 2)
    ) * prezzo
    return prezzo + delta_prezzo

def determina_tasse(nome, desc):
    """
    Determina aliquota fiscale (12.5% titoli stato, 26% corporate)
    """
    titoli_stato = [
        "BTP", "BOT", "CCT", "CTZ", "BUND", "OAT", "TREASURY", 
        "USA", "ROMANIA", "EUROPA", "REPUBLIC"
    ]
    
    nome_upper = nome.upper()
    desc_upper = desc.upper()
    
    for keyword in titoli_stato:
        if keyword in nome_upper or keyword in desc_upper:
            return 12.5
    
    return 26.0

def pulisci_taglio(valore):
    """
    Converte taglio minimo in formato numerico (gestisce 'k' per migliaia)
    """
    s = str(valore).lower().strip()
    
    if 'k' in s:
        try:
            return float(s.replace('k', '')) * 1000
        except:
            return 1000.0
    
    try:
        # Rimuove separatori migliaia e converte virgola in punto
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except:
        return 1000.0

def processa_riga(row, info):
    """
    Estrae dati da riga DataFrame con gestione errori robusta
    """
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        
        # Trova colonne in modo flessibile
        c_prezzo = next(
            (c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), 
            None
        )
        c_scadenza = next(
            (c for c in cols if 'scadenza' in str(c).lower() or 'maturity' in str(c).lower()), 
            None
        )
        c_desc = next(
            (c for c in cols if 'descrizione' in str(c).lower() or 'description' in str(c).lower()), 
            None
        )
        c_min = next(
            (c for c in cols if 'min' in str(c).lower() or 'taglio' in str(c).lower()), 
            None
        )
        c_rating = next(
            (c for c in cols if 'rating' in str(c).lower()), 
            None
        )
        
        if not all([c_prezzo, c_scadenza, c_desc]):
            return None
        
        # Estrai prezzo
        prezzo_str = str(row[c_prezzo]).replace(',', '.').replace('€', '').strip()
        prezzo = float(prezzo_str)
        
        if prezzo <= 0:
            return None
        
        # Estrai scadenza
        scadenza_str = str(row[c_scadenza]).strip()
        try:
            scadenza = datetime.strptime(scadenza_str, '%Y-%m-%d').date()
        except:
            try:
                scadenza = datetime.strptime(scadenza_str, '%d/%m/%Y').date()
            except:
                return None
        
        # Verifica scadenza futura
        if scadenza <= date.today():
            return None
        
        # Estrai descrizione e cedola
        descrizione = str(row[c_desc])
        cedola = 0.0
        
        # Pattern regex migliorato per cedola
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', descrizione)
        if match:
            cedola = float(match.group(1).replace(',', '.'))
        
        # Taglio minimo
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]):
            taglio = pulisci_taglio(row[c_min])
        
        # Rating
        rating = "NR"
        if c_rating and pd.notna(row[c_rating]):
            rating = str(row[c_rating]).strip()
        
        return {
            "desc": descrizione,
            "pr": prezzo,
            "sc": scadenza,
            "ced": cedola,
            "freq": info['freq'],
            "fonte": info['nome'],
            "taglio": taglio,
            "rating": rating
        }
        
    except Exception as e:
        st.warning(f"Errore processamento riga: {e}")
        return None

# --- AGGIORNAMENTO DB CON RATE LIMITING ---
def aggiorna_db():
    """
    Aggiorna database con rate limiting intelligente
    """
    # Controlla ultimo scrape
    now = datetime.now()
    if st.session_state.last_scrape_time:
        elapsed = (now - st.session_state.last_scrape_time).total_seconds()
        if elapsed < 3600:  # 1 ora
            st.warning(f"⏳ Attendi {int((3600 - elapsed) / 60)} minuti prima del prossimo aggiornamento")
            return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_sources = sum(len(v) for v in SOURCES_MAP.values())
    current = 0
    success_count = 0
    error_count = 0
    
    for categoria, sources in SOURCES_MAP.items():
        for src in sources:
            current += 1
            status_text.text(f"Scarico {src['nome']} ({current}/{total_sources})...")
            progress_bar.progress(current / total_sources)
            
            try:
                # Delay casuale per evitare ban (3-6 secondi)
                time.sleep(random.uniform(3, 6))
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml',
                    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8'
                }
                
                response = requests.get(
                    src['url'], 
                    headers=headers, 
                    timeout=15
                )
                response.raise_for_status()
                
                # Parse HTML tables
                dataframes = pd.read_html(response.text, decimal=",", thousands=".")
                
                # Trova tabella con ISIN
                for df in dataframes:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        filepath = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
                        df.to_csv(filepath, index=False)
                        success_count += 1
                        break
                
            except requests.exceptions.HTTPError as e:
                error_count += 1
                if e.response.status_code in [403, 429]:
                    st.error(f"⛔ BANNATO da {src['nome']}! Interrompo.")
                    break
                st.warning(f"⚠️ HTTP Error {src['nome']}: {e.response.status_code}")
                
            except Exception as e:
                error_count += 1
                st.warning(f"⚠️ Errore {src['nome']}: {str(e)[:50]}")
    
    status_text.empty()
    progress_bar.empty()
    
    # Aggiorna timestamp
    st.session_state.last_scrape_time = now
    st.session_state.scrape_count += 1
    
    st.success(f"✅ Aggiornamento completato: {success_count} OK, {error_count} errori")
    time.sleep(2)
    st.rerun()

def cerca_db(isin, categoria):
    """
    Cerca ISIN nel database locale
    """
    if not valida_isin(isin):
        return None, None
    
    sources = SOURCES_MAP.get(categoria, [])
    
    for src in sources:
        filepath = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
        
        if not os.path.exists(filepath):
            continue
        
        try:
            df = pd.read_csv(filepath)
            
            # Trova colonna ISIN
            col_isin = next(
                (c for c in df.columns if 'ISIN' in str(c).upper()), 
                None
            )
            
            if col_isin is None:
                continue
            
            # Cerca ISIN
            mask = df[col_isin].astype(str).str.contains(isin, case=False, na=False)
            
            if mask.any():
                return df[mask].iloc[0], src
                
        except Exception as e:
            st.warning(f"Errore lettura {src['nome']}: {e}")
            continue
    
    return None, None

def genera_flussi(dati, importo, tax_rate):
    """
    Genera flussi di cassa del bond
    """
    flussi = []
    nominale = importo
    prezzo_acquisto = (importo * dati['pr']) / 100
    scadenza = dati['sc']
    
    # Investimento iniziale
    flussi.append({
        "Data": date.today(),
        "Flow": -prezzo_acquisto,
        "Tipo": "Investimento"
    })
    
    # Cedole
    if dati['freq'] > 0:
        cedola_lorda = (nominale * (dati['ced'] / 100)) / dati['freq']
        cedola_netta = cedola_lorda * (1 - tax_rate / 100)
        
        current_date = scadenza
        cedole_generate = 0
        max_cedole = int(((scadenza - date.today()).days / 365.25) * dati['freq']) + 1
        
        while current_date > date.today() + timedelta(days=2) and cedole_generate < max_cedole:
            if current_date != scadenza:
                flussi.append({
                    "Data": current_date,
                    "Flow": cedola_netta,
                    "Tipo": "Cedola"
                })
                cedole_generate += 1
            
            # Sottrai periodo cedolare
            current_date -= timedelta(days=int(365 / dati['freq']))
    
    # Rimborso finale
    capital_gain = max(0, nominale - prezzo_acquisto)
    tassa_capital_gain = capital_gain * (tax_rate / 100)
    rimborso_netto = nominale - tassa_capital_gain
    
    # Ultima cedola
    cedola_finale = 0
    if dati['freq'] > 0:
        cedola_finale = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
    
    flussi.append({
        "Data": scadenza,
        "Flow": rimborso_netto + cedola_finale,
        "Tipo": "Rimborso"
    })
    
    # Crea DataFrame
    df_flussi = pd.DataFrame(flussi).sort_values("Data")
    df_flussi['Cum'] = df_flussi['Flow'].cumsum()
    
    return df_flussi

# --- ANALISI AVANZATA ---
def analizza_bond_quality(dati, risk_metrics, tax_rate):
    """
    Analisi qualitativa del bond con flags
    """
    flags = []
    score = 100  # Punteggio iniziale
    
    # 1. Taglio minimo
    if dati['taglio'] > 100000:
        flags.append(("red", "⚠️ Taglio minimo molto alto (>100k)"))
        score -= 20
    elif dati['taglio'] > 50000:
        flags.append(("warning", "⚠️ Taglio medio-alto (>50k)"))
        score -= 10
    
    # 2. Prezzo
    if dati['pr'] > 110:
        flags.append(("red", "⚠️ Prezzo molto sopra la pari (>110)"))
        score -= 15
    elif dati['pr'] > 105:
        flags.append(("warning", "⚠️ Prezzo sopra la pari (>105)"))
        score -= 5
    elif dati['pr'] < 70:
        flags.append(("warning", "⚠️ Prezzo molto sotto la pari (<70)"))
        score -= 10
    
    # 3. Rendimento netto
    if risk_metrics:
        ytm_netto = risk_metrics['ytm'] * (1 - tax_rate / 100)
        
        if ytm_netto < 1.5:
            flags.append(("red", f"⚠️ YTM netto basso ({ytm_netto:.2f}% < inflazione)"))
            score -= 20
        elif ytm_netto < 2.5:
            flags.append(("warning", f"⚠️ YTM netto modesto ({ytm_netto:.2f}%)"))
            score -= 10
        else:
            flags.append(("green", f"✅ YTM netto interessante ({ytm_netto:.2f}%)"))
            score += 10
    
    # 4. Duration (rischio tasso)
    if risk_metrics and risk_metrics['mod_dur'] > 10:
        flags.append(("warning", f"⚠️ Duration alta ({risk_metrics['mod_dur']:.1f} anni) - sensibile a tassi"))
        score -= 10
    
    # 5. Rating
    rating_lower = dati['rating'].lower()
    if any(x in rating_lower for x in ['ccc', 'd', 'nr']):
        flags.append(("red", f"⚠️ Rating basso/assente ({dati['rating']})"))
        score -= 15
    elif any(x in rating_lower for x in ['bb', 'b']):
        flags.append(("warning", f"⚠️ Rating speculativo ({dati['rating']})"))
        score -= 5
    
    # 6. Scadenza
    anni_scadenza = (dati['sc'] - date.today()).days / 365.25
    if anni_scadenza > 20:
        flags.append(("warning", f"⚠️ Scadenza molto lunga ({anni_scadenza:.0f} anni)"))
        score -= 5
    
    # Score finale
    score = max(0, min(100, score))
    
    return {
        "flags": flags,
        "score": score,
        "ytm_netto": risk_metrics['ytm'] * (1 - tax_rate / 100) if risk_metrics else 0
    }

# --- APP PRINCIPALE ---
def login():
    """Schermata di login"""
    st.title("🔒 Bond Research Terminal - Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        username = st.text_input("👤 Username", placeholder="Inserisci username")
        password = st.text_input("🔑 Password", type="password", placeholder="Inserisci password")
        
        if st.button("🚀 Accedi", use_container_width=True):
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if username == SEGRETO_UTENTE and password_hash == SEGRETO_PASSWORD_HASH:
                st.session_state.logged_in = True
                st.success("✅ Login effettuato!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Credenziali errate")
        
        st.markdown("---")
        st.caption("💡 Versione 2.0 - Bond Terminal Pro")

def main_app():
    """Applicazione principale"""
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        st.caption("Professional Edition")
        
        st.divider()
        
        # Navigation
        st.subheader("📍 NAVIGAZIONE")
        
        if st.button("🔎 Scanner Singolo", use_container_width=True):
            st.session_state.page = "Scanner"
            st.rerun()
        
        if st.button("⚔️ Confronto Bond", use_container_width=True):
            st.session_state.page = "Confronto"
            st.rerun()
        
        if st.button("💼 Portafoglio", use_container_width=True):
            st.session_state.page = "Portafoglio"
            st.rerun()
        
        st.divider()
        
        # System Status
        st.subheader("⚙️ SISTEMA")
        
        last_update = get_last_update_time()
        if last_update:
            formatted_date = last_update.strftime("%d/%m/%Y %H:%M")
            delta_hours = (datetime.now() - last_update).total_seconds() / 3600
            
            if delta_hours < 24:
                st.success(f"📅 Aggiornato: {formatted_date}")
            elif delta_hours < 72:
                st.warning(f"⚠️ Vecchio ({int(delta_hours)}h): {formatted_date}")
            else:
                st.error(f"❌ Molto vecchio ({int(delta_hours/24)}gg)")
        else:
            st.error("❌ Database vuoto")
        
        # Connection check
        col_check, col_status = st.columns([1, 2])
        
        if col_check.button("📶", help="Controlla connessione"):
            with st.spinner("Controllo..."):
                st.session_state.connection_status = check_connection_status()
        
        col_status.markdown(f"**{st.session_state.connection_status}**")
        
        # Update button
        if st.button("🔄 Aggiorna Database", use_container_width=True):
            if "BANNATO" in st.session_state.connection_status:
                st.error("🛑 Sei bannato! Attendi 1-2 ore.")
            elif "OFFLINE" in st.session_state.connection_status:
                st.error("🛑 Nessuna connessione internet")
            else:
                aggiorna_db()
        
        # Stats
        files_count = len(os.listdir(DB_FOLDER)) if os.path.exists(DB_FOLDER) else 0
        total_sources = sum(len(v) for v in SOURCES_MAP.values())
        completeness = (files_count / total_sources * 100) if total_sources > 0 else 0
        
        st.metric("Files", f"{files_count}/{total_sources}", f"{completeness:.0f}%")
        
        if st.session_state.scrape_count > 0:
            st.caption(f"Aggiornamenti effettuati: {st.session_state.scrape_count}")
        
        st.divider()
        
        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- PAGINE ---
    
    # PAGINA 1: SCANNER
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario Avanzato")
        
        # Legenda categorie
        st.markdown("### 📍 Guida alle Categorie")
        st.caption("Scegli la categoria corretta per il bond che stai cercando")
        
        leg1, leg2, leg3, leg4 = st.columns(4)
        
        with leg1:
            st.markdown("""
            <div class="legend-box gov">
                <span class="legend-title">🏛️ GOVERNATIVI</span>
                <b>Titoli di Stato</b><br>
                Debito sovrano nazionale<br>
                <i>Es: BTP, BOT, Bund, OAT, Treasury</i>
            </div>
            """, unsafe_allow_html=True)
        
        with leg2:
            st.markdown("""
            <div class="legend-box bank">
                <span class="legend-title">🏦 FINANZIARI</span>
                <b>Banche & Istituti</b><br>
                Obbligazioni bancarie<br>
                <i>Es: Intesa, UniCredit, BNP, Subordinate</i>
            </div>
            """, unsafe_allow_html=True)
        
        with leg3:
            st.markdown("""
            <div class="legend-box corp">
                <span class="legend-title">🏭 CORPORATE</span>
                <b>Aziende Private</b><br>
                Debito societario<br>
                <i>Es: Eni, Enel, Stellantis, Automotive</i>
            </div>
            """, unsafe_allow_html=True)
        
        with leg4:
            st.markdown("""
            <div class="legend-box spec">
                <span class="legend-title">💎 SPECIALI</span>
                <b>Strutture Particolari</b><br>
                Caratteristiche uniche<br>
                <i>Es: Zero Coupon, Callable, Green Bond</i>
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Input area
        col_cat, col_isin = st.columns([2, 1])
        
        with col_cat:
            categoria = st.selectbox(
                "🏷️ Categoria Bond",
                list(SOURCES_MAP.keys()),
                help="Seleziona la categoria corretta basandoti sulla legenda sopra"
            )
        
        with col_isin:
            isin_input = st.text_input(
                "🔍 Codice ISIN",
                placeholder="IT0005436693",
                help="Inserisci il codice ISIN a 12 caratteri"
            ).strip().upper()
        
        # Validazione e ricerca
        if isin_input:
            if not valida_isin(isin_input):
                st.error("❌ ISIN non valido! Deve essere formato da 2 lettere + 10 alfanumerici (es: IT0005436693)")
            else:
                with st.spinner(f"🔍 Cerco {isin_input}..."):
                    row, info = cerca_db(isin_input, categoria)
                    dati = processa_riga(row, info) if row is not None else None
                
                if dati:
                    # Calcoli finanziari
                    tax_rate = determina_tasse(dati['fonte'], dati['desc'])
                    risk_metrics = calcola_metriche_rischio(
                        dati['pr'], 
                        dati['ced'], 
                        dati['sc'], 
                        dati['freq']
                    )
                    
                    # Analisi qualità
                    quality = analizza_bond_quality(dati, risk_metrics, tax_rate)
                    
                    # HEADER PRINCIPALE
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); 
                                padding: 25px; border-radius: 12px; 
                                border-left: 6px solid #00CC96; 
                                margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        <div class="main-header">{dati['desc']}</div>
                        <div class="sub-header">
                            ISIN: {isin_input} | 
                            Fonte: {dati['fonte']} | 
                            Rating: {dati['rating']} | 
                            Tassazione: {tax_rate}%
                        </div>
                        <div style="margin-top: 10px; font-size: 18px; color: #00CC96;">
                            Score Qualità: {quality['score']}/100
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # METRICHE PRINCIPALI
                    met1, met2, met3, met4, met5 = st.columns(5)
                    
                    ytm_lordo = risk_metrics['ytm'] if risk_metrics else 0
                    ytm_netto = quality['ytm_netto']
                    durata_anni = (dati['sc'] - date.today()).days / 365.25
                    
                    met1.metric(
                        "💰 Prezzo",
                        f"{dati['pr']:.2f}€",
                        f"{dati['pr'] - 100:+.2f}" if dati['pr'] != 100 else "Alla pari"
                    )
                    met2.metric(
                        "📊 YTM Lordo",
                        f"{ytm_lordo:.2f}%"
                    )
                    met3.metric(
                        "💵 YTM Netto",
                        f"{ytm_netto:.2f}%",
                        f"Tasse: {tax_rate}%"
                    )
                    met4.metric(
                        "🎯 Cedola",
                        f"{dati['ced']:.2f}%" if dati['ced'] > 0 else "Zero Coupon"
                    )
                    met5.metric(
                        "⏱️ Scadenza",
                        f"{durata_anni:.1f} anni",
                        dati['sc'].strftime("%d/%m/%Y")
                    )
                    
                    st.divider()
                    
                    # SIMULATORE INVESTIMENTO
                    st.subheader("💶 Simulatore Rendimento")
                    
                    col_sim1, col_sim2, col_sim3 = st.columns([2, 2, 2])
                    
                    with col_sim1:
                        importo = st.number_input(
                            "Capitale da Investire (€)",
                            min_value=float(dati['taglio']),
                            value=max(10000.0, float(dati['taglio'])),
                            step=1000.0,
                            help=f"Taglio minimo: {dati['taglio']:,.0f}€"
                        )
                    
                    # Genera flussi
                    df_flussi = genera_flussi(dati, importo, tax_rate)
                    profitto_netto = df_flussi['Flow'].sum()
                    roi = (profitto_netto / importo) * 100
                    
                    with col_sim2:
                        st.metric(
                            "Profitto Totale Netto",
                            f"{profitto_netto:+,.2f}€",
                            f"ROI: {roi:+.1f}%"
                        )
                    
                    with col_sim3:
                        cedole_totali = df_flussi[df_flussi['Tipo'] == 'Cedola']['Flow'].sum()
                        st.metric(
                            "Cedole Totali Nette",
                            f"{cedole_totali:,.2f}€"
                        )
                    
                    st.divider()
                    
                    # ANALISI RISCHIO + STRESS TEST
                    col_risk, col_stress = st.columns([1, 2])
                    
                    with col_risk:
                        st.subheader("⚠️ Metriche di Rischio")
                        
                        if risk_metrics:
                            st.markdown(f"""
                            <div class="metric-card">
                                <b>Duration (Macaulay):</b> {risk_metrics['mac_dur']:.2f} anni<br>
                                <span style="font-size:12px;color:#cccccc">Tempo medio per recupero investimento</span>
                            </div>
                            <div class="metric-card">
                                <b>Modified Duration:</b> {risk_metrics['mod_dur']:.2f}<br>
                                <span style="font-size:12px;color:#cccccc">Sensibilità ai tassi di interesse</span>
                            </div>
                            <div class="metric-card">
                                <b>Convexity:</b> {risk_metrics['convexity']:.2f}<br>
                                <span style="font-size:12px;color:#cccccc">Curvatura prezzo/tasso</span>
                            </div>
                            <div class="metric-card">
                                <b>DV01 (per 10k€):</b> {risk_metrics['dv01'] * (importo / 10000):.2f}€<br>
                                <span style="font-size:12px;color:#cccccc">Perdita per +1bp sui tassi</span>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ Calcolo rischio non disponibile")
                    
                    with col_stress:
                        st.subheader("⚡ Stress Test (Shock Tassi)")
                        
                        if risk_metrics:
                            shocks_bps = [-200, -100, -50, 0, +50, +100, +200]
                            prezzi_stress = [
                                stress_test(
                                    dati['pr'], 
                                    risk_metrics['mod_dur'], 
                                    risk_metrics['convexity'], 
                                    shock
                                ) for shock in shocks_bps
                            ]
                            
                            # Calcola P&L su investimento
                            pl_values = [
                                ((p - dati['pr']) / dati['pr']) * importo 
                                for p in prezzi_stress
                            ]
                            
                            fig_stress = go.Figure()
                            
                            # Linea prezzi
                            fig_stress.add_trace(go.Scatter(
                                x=shocks_bps,
                                y=prezzi_stress,
                                mode='lines+markers+text',
                                name='Prezzo',
                                text=[f"{p:.2f}€" for p in prezzi_stress],
                                textposition="top center",
                                line=dict(color='#636EFA', width=3),
                                marker=dict(size=10)
                            ))
                            
                            # Zona di stabilità
                            fig_stress.add_hrect(
                                y0=dati['pr'] * 0.95,
                                y1=dati['pr'] * 1.05,
                                fillcolor="green",
                                opacity=0.1,
                                line_width=0
                            )
                            
                            fig_stress.update_layout(
                                height=300,
                                margin=dict(l=0, r=0, t=30, b=0),
                                template="plotly_dark",
                                xaxis_title="Shock Tassi (basis points)",
                                yaxis_title="Prezzo Bond (€)",
                                title="Simulazione Variazione Prezzo",
                                hovermode='x unified'
                            )
                            
                            st.plotly_chart(fig_stress, use_container_width=True)
                            
                            # Tabella P&L
                            st.caption("💸 Impatto su Portafoglio")
                            df_stress = pd.DataFrame({
                                'Shock': [f"{s:+d}bp" for s in shocks_bps],
                                'Prezzo': [f"{p:.2f}€" for p in prezzi_stress],
                                'P&L': [f"{pl:+,.0f}€" for pl in pl_values]
                            })
                            st.dataframe(df_stress, use_container_width=True, hide_index=True)
                        else:
                            st.warning("⚠️ Stress test non disponibile")
                    
                    st.divider()
                    
                    # FLAGS QUALITA' + CASH FLOW
                    col_flags, col_cashflow = st.columns([1, 2])
                    
                    with col_flags:
                        st.subheader("🚩 Analisi Qualità")
                        
                        for flag_type, flag_text in quality['flags']:
                            if flag_type == "red":
                                st.markdown(
                                    f'<div class="red-flag">{flag_text}</div>',
                                    unsafe_allow_html=True
                                )
                            elif flag_type == "warning":
                                st.markdown(
                                    f'<div class="warning-flag">{flag_text}</div>',
                                    unsafe_allow_html=True
                                )
                            else:  # green
                                st.markdown(
                                    f'<div class="green-flag">{flag_text}</div>',
                                    unsafe_allow_html=True
                                )
                        
                        if not quality['flags']:
                            st.markdown(
                                '<div class="green-flag">✅ Nessun problema rilevato</div>',
                                unsafe_allow_html=True
                            )
                    
                    with col_cashflow:
                        tab_cf, tab_table, tab_actions = st.tabs([
                            "💰 Grafico Flussi",
                            "📊 Tabella Dettagli",
                            "⚙️ Azioni"
                        ])
                        
                        with tab_cf:
                            fig_cashflow = px.bar(
                                df_flussi,
                                x='Data',
                                y='Flow',
                                color='Tipo',
                                title=f"Cash Flow su {importo:,.0f}€",
                                template="plotly_dark",
                                color_discrete_map={
                                    'Investimento': '#EF553B',
                                    'Cedola': '#00CC96',
                                    'Rimborso': '#636EFA'
                                }
                            )
                            fig_cashflow.update_layout(
                                height=280,
                                margin=dict(l=0, r=0, t=40, b=0)
                            )
                            st.plotly_chart(fig_cashflow, use_container_width=True)
                        
                        with tab_table:
                            st.dataframe(
                                df_flussi.style.format({
                                    'Flow': '{:+,.2f}€',
                                    'Cum': '{:,.2f}€'
                                }),
                                use_container_width=True,
                                hide_index=True
                            )
                        
                        with tab_actions:
                            if st.button("📌 Salva per Confronto", use_container_width=True):
                                st.session_state.confronto = dati.copy()
                                st.success("✅ Bond salvato per confronto!")
                            
                            if st.button("💼 Aggiungi a Portafoglio", use_container_width=True):
                                st.session_state.portfolio.append({
                                    "ISIN": isin_input,
                                    "Desc": dati['desc'][:40],
                                    "Nominale": importo,
                                    "Valore": (importo * dati['pr']) / 100,
                                    "YTM": ytm_lordo,
                                    "Scadenza": dati['sc']
                                })
                                st.success("✅ Aggiunto al portafoglio!")
                
                else:
                    st.info(f"""
                    ℹ️ ISIN **{isin_input}** non trovato nella categoria **{categoria}**
                    
                    **Suggerimenti:**
                    - Verifica di aver selezionato la categoria corretta
                    - Prova a cercare in altre categorie
                    - Aggiorna il database con il pulsante nella sidebar
                    - Controlla che l'ISIN sia corretto
                    """)
        
        else:
            st.info("👆 Seleziona una categoria e inserisci un ISIN per iniziare la ricerca")
    
    # PAGINA 2: CONFRONTO
    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto Bond")
        
        if st.session_state.confronto:
            bond_a = st.session_state.confronto
            
            st.success(f"📌 **Bond A salvato:** {bond_a['desc']}")
            
            st.divider()
            
            col_cat_b, col_isin_b = st.columns([2, 1])
            
            with col_cat_b:
                cat_b = st.selectbox(
                    "Categoria Bond B",
                    list(SOURCES_MAP.keys())
                )
            
            with col_isin_b:
                isin_b = st.text_input(
                    "ISIN Bond B",
                    placeholder="IT..."
                ).strip().upper()
            
            if st.button("⚔️ Confronta", type="primary", use_container_width=True) and isin_b:
                if not valida_isin(isin_b):
                    st.error("❌ ISIN B non valido!")
                else:
                    row_b, info_b = cerca_db(isin_b, cat_b)
                    bond_b = processa_riga(row_b, info_b) if row_b else None
                    
                    if bond_b:
                        # Calcoli
                        tax_a = determina_tasse(bond_a['fonte'], bond_a['desc'])
                        tax_b = determina_tasse(bond_b['fonte'], bond_b['desc'])
                        
                        risk_a = calcola_metriche_rischio(
                            bond_a['pr'], bond_a['ced'], bond_a['sc'], bond_a['freq']
                        )
                        risk_b = calcola_metriche_rischio(
                            bond_b['pr'], bond_b['ced'], bond_b['sc'], bond_b['freq']
                        )
                        
                        # Header confronto
                        st.markdown("### 📊 Risultati Confronto")
                        
                        comp1, comp2 = st.columns(2)
                        
                        with comp1:
                            st.markdown(f"""
                            <div style="background-color: #1e2130; padding: 20px; 
                                        border-radius: 10px; border: 2px solid #EF553B;">
                                <h3 style="color: #EF553B;">🅰️ {bond_a['desc'][:50]}</h3>
                                <p style="color: #b0b3c5;">ISIN: {bond_a.get('isin', 'N/A')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with comp2:
                            st.markdown(f"""
                            <div style="background-color: #1e2130; padding: 20px; 
                                        border-radius: 10px; border: 2px solid #00CC96;">
                                <h3 style="color: #00CC96;">🅱️ {bond_b['desc'][:50]}</h3>
                                <p style="color: #b0b3c5;">ISIN: {isin_b}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.divider()
                        
                        # Metriche comparate
                        st.markdown("#### 📈 Metriche Comparative")
                        
                        ytm_a = risk_a['ytm'] if risk_a else 0
                        ytm_b = risk_b['ytm'] if risk_b else 0
                        ytm_netto_a = ytm_a * (1 - tax_a / 100)
                        ytm_netto_b = ytm_b * (1 - tax_b / 100)
                        
                        m1, m2, m3, m4 = st.columns(4)
                        
                        m1.metric(
                            "YTM Lordo A",
                            f"{ytm_a:.2f}%",
                            delta=None
                        )
                        m2.metric(
                            "YTM Lordo B",
                            f"{ytm_b:.2f}%",
                            delta=f"{ytm_b - ytm_a:+.2f}%"
                        )
                        m3.metric(
                            "YTM Netto A",
                            f"{ytm_netto_a:.2f}%",
                            delta=None
                        )
                        m4.metric(
                            "YTM Netto B",
                            f"{ytm_netto_b:.2f}%",
                            delta=f"{ytm_netto_b - ytm_netto_a:+.2f}%"
                        )
                        
                        # Grafici comparativi
                        st.markdown("#### 📊 Analisi Visuale")
                        
                        # Duration comparison
                        if risk_a and risk_b:
                            fig_comp = go.Figure()
                            
                            fig_comp.add_trace(go.Bar(
                                name='Bond A',
                                x=['Duration', 'Convexity'],
                                y=[risk_a['mod_dur'], risk_a['convexity']],
                                marker_color='#EF553B'
                            ))
                            
                            fig_comp.add_trace(go.Bar(
                                name='Bond B',
                                x=['Duration', 'Convexity'],
                                y=[risk_b['mod_dur'], risk_b['convexity']],
                                marker_color='#00CC96'
                            ))
                            
                            fig_comp.update_layout(
                                title="Confronto Rischio",
                                template="plotly_dark",
                                barmode='group',
                                height=350
                            )
                            
                            st.plotly_chart(fig_comp, use_container_width=True)
                        
                        # Tabella riepilogativa
                        st.markdown("#### 📋 Riepilogo Completo")
                        
                        df_comparison = pd.DataFrame({
                            'Metrica': [
                                'Prezzo',
                                'Cedola',
                                'YTM Lordo',
                                'YTM Netto',
                                'Durata (anni)',
                                'Duration',
                                'Rating',
                                'Taglio Minimo',
                                'Tassazione'
                            ],
                            'Bond A': [
                                f"{bond_a['pr']:.2f}€",
                                f"{bond_a['ced']:.2f}%",
                                f"{ytm_a:.2f}%",
                                f"{ytm_netto_a:.2f}%",
                                f"{(bond_a['sc'] - date.today()).days / 365.25:.1f}",
                                f"{risk_a['mod_dur']:.2f}" if risk_a else "N/A",
                                bond_a['rating'],
                                f"{bond_a['taglio']:,.0f}€",
                                f"{tax_a:.1f}%"
                            ],
                            'Bond B': [
                                f"{bond_b['pr']:.2f}€",
                                f"{bond_b['ced']:.2f}%",
                                f"{ytm_b:.2f}%",
                                f"{ytm_netto_b:.2f}%",
                                f"{(bond_b['sc'] - date.today()).days / 365.25:.1f}",
                                f"{risk_b['mod_dur']:.2f}" if risk_b else "N/A",
                                bond_b['rating'],
                                f"{bond_b['taglio']:,.0f}€",
                                f"{tax_b:.1f}%"
                            ]
                        })
                        
                        st.dataframe(df_comparison, use_container_width=True, hide_index=True)
                        
                        # Raccomandazione
                        st.markdown("#### 💡 Raccomandazione")
                        
                        if ytm_netto_b > ytm_netto_a:
                            st.success(f"""
                            ✅ **Bond B** offre un rendimento netto superiore di **{ytm_netto_b - ytm_netto_a:.2f}%**
                            
                            Considera anche:
                            - Differenza di rischio (Duration)
                            - Rating creditizio
                            - Liquidità del titolo
                            """)
                        else:
                            st.info(f"""
                            ℹ️ **Bond A** offre un rendimento netto superiore di **{ytm_netto_a - ytm_netto_b:.2f}%**
                            
                            Considera anche:
                            - Differenza di rischio (Duration)
                            - Rating creditizio
                            - Liquidità del titolo
                            """)
                    
                    else:
                        st.error(f"❌ Bond B (ISIN: {isin_b}) non trovato nella categoria {cat_b}")
        
        else:
            st.warning("""
            ⚠️ **Nessun bond salvato per il confronto**
            
            Per iniziare:
            1. Vai alla pagina **Scanner**
            2. Cerca un bond
            3. Clicca su **"Salva per Confronto"**
            4. Torna qui per confrontarlo con un altro bond
            """)
    
    # PAGINA 3: PORTAFOGLIO
    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio Obbligazionario")
        
        # Aggiungi bond
        with st.expander("➕ Aggiungi Bond al Portafoglio", expanded=len(st.session_state.portfolio) == 0):
            col_cat, col_isin, col_nom, col_add = st.columns([2, 2, 2, 1])
            
            with col_cat:
                port_cat = st.selectbox(
                    "Categoria",
                    list(SOURCES_MAP.keys()),
                    key="port_cat"
                )
            
            with col_isin:
                port_isin = st.text_input(
                    "ISIN",
                    placeholder="IT...",
                    key="port_isin"
                ).strip().upper()
            
            with col_nom:
                port_nominal = st.number_input(
                    "Nominale (€)",
                    min_value=1000.0,
                    value=10000.0,
                    step=1000.0,
                    key="port_nom"
                )
            
            with col_add:
                st.write("")  # Spacer
                st.write("")  # Spacer
                if st.button("➕ Aggiungi", use_container_width=True):
                    if not valida_isin(port_isin):
                        st.error("ISIN non valido!")
                    else:
                        row, info = cerca_db(port_isin, port_cat)
                        dati = processa_riga(row, info) if row else None
                        
                        if dati:
                            risk = calcola_metriche_rischio(
                                dati['pr'],
                                dati['ced'],
                                dati['sc'],
                                dati['freq']
                            )
                            
                            st.session_state.portfolio.append({
                                "ISIN": port_isin,
                                "Desc": dati['desc'][:40],
                                "Nominale": port_nominal,
                                "Valore": (port_nominal * dati['pr']) / 100,
                                "YTM": risk['ytm'] if risk else 0,
                                "Scadenza": dati['sc']
                            })
                            
                            st.success(f"✅ {dati['desc'][:30]} aggiunto!")
                            st.rerun()
                        else:
                            st.error(f"Bond {port_isin} non trovato")
        
        # Visualizza portafoglio
        if st.session_state.portfolio:
            df_portfolio = pd.DataFrame(st.session_state.portfolio)
            
            # Statistiche aggregate
            st.markdown("### 📊 Riepilogo Portafoglio")
            
            total_value = df_portfolio['Valore'].sum()
            total_nominal = df_portfolio['Nominale'].sum()
            weighted_ytm = (df_portfolio['YTM'] * df_portfolio['Valore']).sum() / total_value
            num_bonds = len(df_portfolio)
            
            stat1, stat2, stat3, stat4 = st.columns(4)
            
            stat1.metric("Valore Totale", f"{total_value:,.0f}€")
            stat2.metric("Nominale Totale", f"{total_nominal:,.0f}€")
            stat3.metric("YTM Ponderato", f"{weighted_ytm:.2f}%")
            stat4.metric("Numero Bond", num_bonds)
            
            st.divider()
            
            # Tabella dettagliata
            st.markdown("### 📋 Dettaglio Posizioni")
            
            # Formatta DataFrame per visualizzazione
            df_display = df_portfolio.copy()
            df_display['Valore'] = df_display['Valore'].apply(lambda x: f"{x:,.2f}€")
            df_display['Nominale'] = df_display['Nominale'].apply(lambda x: f"{x:,.0f}€")
            df_display['YTM'] = df_display['YTM'].apply(lambda x: f"{x:.2f}%")
            df_display['Scadenza'] = df_display['Scadenza'].apply(lambda x: x.strftime("%d/%m/%Y"))
            df_display['Peso %'] = (df_portfolio['Valore'] / total_value * 100).apply(lambda x: f"{x:.1f}%")
            
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
            
            # Grafici
            st.markdown("### 📈 Analisi Visuale")
            
            chart1, chart2 = st.columns(2)
            
            with chart1:
                # Pie chart allocazione
                fig_pie = px.pie(
                    df_portfolio,
                    values='Valore',
                    names='Desc',
                    title='Allocazione per Bond',
                    template='plotly_dark'
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with chart2:
                # Bar chart YTM
                fig_bar = px.bar(
                    df_portfolio,
                    x='Desc',
                    y='YTM',
                    title='YTM per Bond',
                    template='plotly_dark',
                    color='YTM',
                    color_continuous_scale='RdYlGn'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Azioni portafoglio
            st.divider()
            
            action1, action2, action3 = st.columns(3)
            
            with action1:
                if st.button("🗑️ Svuota Portafoglio", use_container_width=True):
                    st.session_state.portfolio = []
                    st.rerun()
            
            with action2:
                # Export CSV
                csv = df_portfolio.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Esporta CSV",
                    data=csv,
                    file_name=f"portafoglio_bond_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with action3:
                if st.button("🔄 Aggiorna Prezzi", use_container_width=True):
                    st.info("Funzionalità in arrivo - aggiornamento automatico prezzi")
        
        else:
            st.info("""
            📭 **Portafoglio vuoto**
            
            Aggiungi il tuo primo bond usando il form sopra!
            """)

# --- ENTRY POINT ---
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login()
