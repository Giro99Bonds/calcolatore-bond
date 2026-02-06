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

# Blocco CSS per il Design "Pro" (Nero/Verde/Bianco)
st.markdown("""
<style>
    /* --- CARD METRICHE E RISCHIO (Sfondo Scuro, Testo Bianco) --- */
    .metric-card {
        background-color: #1e2130; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #3e445b; 
        margin-bottom: 10px;
        color: #ffffff !important;
    }
    .metric-card b {
        color: #00CC96; /* Verde per i titoli */
    }

    /* --- MENU LATERALE (Testo Nero, Niente Riquadri) --- */
    /* Rimuove lo stile bottone standard */
    [data-testid="stSidebar"] div.stButton > button {
        background-color: transparent; 
        border: none; 
        text-align: left; 
        color: #000000 !important; /* Testo NERO */
        box-shadow: none; 
        padding-left: 0; 
        font-size: 16px; 
        font-weight: 600;
        transition: all 0.2s;
    }
    /* Effetto quando passi sopra col mouse */
    [data-testid="stSidebar"] div.stButton > button:hover {
        color: #333333 !important;
        padding-left: 10px; 
        background-color: rgba(0,0,0,0.05); 
        border-radius: 5px;
    }
    /* Effetto bottone cliccato/attivo */
    [data-testid="stSidebar"] div.stButton > button:focus {
        box-shadow: none; 
        color: #000000 !important; 
        font-weight: bold;
        border-left: 4px solid #00CC96; /* Barra verde a sinistra */
    }

    /* --- LEGENDA CATEGORIE --- */
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
    
    /* Colori specifici per le box della legenda */
    .gov { background-color: #1a4a2e; border: 1px solid #28a745; }
    .bank { background-color: #2c3e50; border: 1px solid #8e9aaf; }
    .corp { background-color: #1e3a5f; border: 1px solid #17a2b8; }
    .spec { background-color: #581845; border: 1px solid #d63384; }

    /* --- FLAG DI ALLERTA --- */
    .red-flag {
        border-left: 5px solid #ff4b4b; 
        background-color: #2d1b1b; 
        padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;
    }
    .green-flag {
        border-left: 5px solid #00cc96; 
        background-color: #1b2d24; 
        padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;
    }
    .warning-flag {
        border-left: 5px solid #ffa500; 
        background-color: #2d2a1b; 
        padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;
    }
    
    /* Headers personalizzati */
    .main-header { font-size: 24px; font-weight: bold; color: white; }
    .sub-header { font-size: 14px; color: #b0b3c5; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIGURAZIONE CREDENZIALI E DATI
# ==============================================================================

# Credenziali di accesso
SEGRETO_UTENTE = "giulio"
# Hash della password per sicurezza base
SEGRETO_PASSWORD_HASH = hashlib.sha256("Giulio99mac!".encode()).hexdigest()

# Cartella dove salvare i file CSV
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# Inizializzazione dello Stato dell'Applicazione (Session State)
def init_session_state():
    if 'portfolio' not in st.session_state: st.session_state.portfolio = []
    if 'confronto' not in st.session_state: st.session_state.confronto = None
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'connection_status' not in st.session_state: st.session_state.connection_status = "In attesa..."
    if 'page' not in st.session_state: st.session_state.page = "Scanner"
    if 'last_scrape_time' not in st.session_state: st.session_state.last_scrape_time = None
    if 'scrape_count' not in st.session_state: st.session_state.scrape_count = 0

init_session_state()

# ==============================================================================
# 3. MAPPA DELLE FONTI DATI (Database Link)
# ==============================================================================

SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT_FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI_TITOLI_EUROPEI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI_TITOLI_EX_EUROPEI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
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
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# ==============================================================================
# 4. FUNZIONI DI UTILITÀ (Database, Network, Parsing)
# ==============================================================================

def valida_isin(isin):
    """Controlla se l'ISIN ha il formato corretto (12 caratteri)"""
    if not isin or len(isin) != 12: return False
    if not isin[:2].isalpha() or not isin[2:].isalnum(): return False
    return True

def get_last_update_time():
    """Controlla la data dell'ultimo file CSV scaricato"""
    try:
        if not os.path.exists(DB_FOLDER): return None
        # FILTRO FONDAMENTALE: Conta solo i file che finiscono con .csv
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: return None
        # Trova il più recente
        latest_file = max(files, key=os.path.getmtime)
        return datetime.fromtimestamp(os.path.getmtime(latest_file))
    except Exception as e:
        return None

def check_connection_status():
    """Test Anti-Ban e Connessione Internet"""
    try:
        # Step 1: Test Google (Internet c'è?)
        requests.get("https://www.google.com", timeout=3)
        
        # Step 2: Test Sito Target (Solo Header, niente download pesante)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.head("https://www.simpletoolsforinvestors.eu/", headers=headers, timeout=5)
        
        if r.status_code == 200: return "🟢 ONLINE"
        elif r.status_code in [403, 429]: return "🔴 BANNATO (403/429)"
        else: return f"🟡 STATUS {r.status_code}"
    except requests.exceptions.Timeout: return "🔴 TIMEOUT"
    except requests.exceptions.ConnectionError: return "🔴 OFFLINE"
    except Exception as e: return f"🔴 ERRORE: {str(e)[:20]}"

def pulisci_taglio(valore):
    """Converte '100k' in 100000.0"""
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try:
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except: return 1000.0

def processa_riga(row, info):
    """Estrae i dati da una riga grezza del database"""
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        # Mappatura colonne intelligente (cerca parole chiave)
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower() or 'maturity' in str(c).lower()), None)
        c_de = next((c for c in cols if 'descrizione' in str(c).lower() or 'description' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower() or 'taglio' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        
        if not all([c_pr, c_sc, c_de]): return None
        
        # Pulizia Prezzo
        prezzo_str = str(row[c_pr]).replace(',', '.').replace('€', '').strip()
        prezzo = float(prezzo_str)
        if prezzo <= 0: return None
        
        # Pulizia Scadenza
        scadenza_str = str(row[c_sc]).strip()
        try: scadenza = datetime.strptime(scadenza_str, '%Y-%m-%d').date()
        except: 
            try: scadenza = datetime.strptime(scadenza_str, '%d/%m/%Y').date()
            except: return None
        
        if scadenza <= date.today(): return None # Bond scaduto
        
        # Estrazione Cedola
        descrizione = str(row[c_de])
        cedola = 0.0
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', descrizione)
        if match: cedola = float(match.group(1).replace(',', '.'))
        
        # Dati Extra
        taglio = 1000.0
        if c_min and pd.notna(row[c_min]): taglio = pulisci_taglio(row[c_min])
        
        rating = "NR"
        if c_rating and pd.notna(row[c_rating]): rating = str(row[c_rating]).strip()
        
        return {
            "desc": descrizione, "pr": prezzo, "sc": scadenza, 
            "ced": cedola, "freq": info['freq'], "fonte": info['nome'], 
            "taglio": taglio, "rating": rating
        }
    except: return None

# ==============================================================================
# 5. MOTORE MATEMATICO (Risk Engine)
# ==============================================================================

def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    """Calcola lo Yield to Maturity usando l'algoritmo di Newton-Raphson"""
    if prezzo <= 0 or freq == 0: return None
    cedola_annua = cedola_pct / 100
    giorni = (scadenza - date.today()).days
    anni = giorni / 365.25
    if anni <= 0: return None
    
    n_periodi = max(1, int(anni * freq))
    c = (cedola_annua * face_value) / freq
    # Stima iniziale
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
    """Calcola Duration, Convexity e DV01"""
    if prezzo <= 0: return None
    ytm = calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value)
    if ytm is None: return None
    
    cedola = cedola_pct / 100
    anni = (scadenza - date.today()).days / 365.25
    if anni <= 0: return None
    
    n_periodi = max(1, int(anni * freq))
    
    # Generazione flussi temporali
    if freq > 0:
        periodi_tempo = np.arange(1, n_periodi + 1) / freq
        cash_flows = np.full(n_periodi, (cedola * face_value) / freq)
        cash_flows[-1] += face_value
    else: # Zero Coupon
        periodi_tempo = np.array([anni])
        cash_flows = np.array([face_value])
        freq = 1
    
    # Calcoli finanziari
    discount_factors = (1 + ytm / freq) ** (-periodi_tempo * freq)
    pv_cf = cash_flows * discount_factors
    mac_duration = np.sum(periodi_tempo * pv_cf) / prezzo
    mod_duration = mac_duration / (1 + ytm / freq)
    convexity = np.sum(cash_flows * periodi_tempo * (periodi_tempo + 1/freq) * ((1 + ytm/freq) ** (-(periodi_tempo * freq + 2)))) / prezzo
    dv01 = mod_duration * prezzo * 0.0001
    
    return {"ytm": ytm * 100, "mod_dur": mod_duration, "mac_dur": mac_duration, "convexity": convexity, "dv01": dv01}

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    """Simula il prezzo se i tassi cambiano"""
    shock = shock_bps / 10000
    delta_prezzo = (-mod_dur * shock + 0.5 * convexity * (shock ** 2)) * prezzo
    return prezzo + delta_prezzo

def determina_tasse(nome, desc):
    """Capisce se tassare al 12.5% o al 26%"""
    titoli_stato = ["BTP", "BOT", "CCT", "CTZ", "BUND", "OAT", "TREASURY", "USA", "ROMANIA", "EUROPA", "REPUBLIC"]
    if any(k in nome.upper() or k in desc.upper() for k in titoli_stato): return 12.5
    return 26.0

def genera_flussi(dati, importo, tax_rate):
    """Crea la tabella dei pagamenti futuri"""
    flussi = []
    nominale = importo
    prezzo_acquisto = (importo * dati['pr']) / 100
    
    # Riga 1: Acquisto oggi
    flussi.append({"Data": date.today(), "Flow": -prezzo_acquisto, "Tipo": "Investimento"})
    
    # Righe Cedole
    if dati['freq'] > 0:
        cedola_lorda = (nominale * (dati['ced'] / 100)) / dati['freq']
        cedola_netta = cedola_lorda * (1 - tax_rate / 100)
        curr = dati['sc']
        while curr > date.today() + timedelta(days=2):
            if curr != dati['sc']: 
                flussi.append({"Data": curr, "Flow": cedola_netta, "Tipo": "Cedola"})
            curr -= timedelta(days=int(365 / dati['freq']))
    
    # Riga Finale: Rimborso + Ultima Cedola
    gain = max(0, nominale - prezzo_acquisto)
    tassa_gain = gain * (tax_rate / 100)
    rimborso_netto = nominale - tassa_gain
    cedola_finale = (nominale * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    
    flussi.append({"Data": dati['sc'], "Flow": rimborso_netto + cedola_finale, "Tipo": "Rimborso"})
    
    df = pd.DataFrame(flussi).sort_values("Data")
    df['Cum'] = df['Flow'].cumsum()
    return df

def analizza_bond_quality(dati, risk_metrics, tax_rate):
    """Assegna bandierine rosse/verdi al titolo"""
    flags = []; score = 100
    
    # Check Taglio
    if dati['taglio'] > 100000: flags.append(("red", "⚠️ Taglio > 100k")); score -= 20
    elif dati['taglio'] > 50000: flags.append(("warning", "⚠️ Taglio > 50k")); score -= 10
    
    # Check Prezzo
    if dati['pr'] > 110: flags.append(("red", "⚠️ Prezzo > 110 (Alto Rischio Minus)")); score -= 15
    elif dati['pr'] > 105: flags.append(("warning", "⚠️ Prezzo > 105")); score -= 5
    
    # Check Rendimento
    ytm_netto = risk_metrics['ytm'] * (1 - tax_rate / 100) if risk_metrics else 0
    if ytm_netto < 1.5: flags.append(("red", "⚠️ YTM Netto < Inflazione")); score -= 20
    elif ytm_netto < 2.5: flags.append(("warning", "⚠️ YTM Netto basso")); score -= 10
    else: flags.append(("green", "✅ YTM Interessante")); score += 10
    
    return {"flags": flags, "score": max(0, min(100, score)), "ytm_netto": ytm_netto}

# ==============================================================================
# 6. FUNZIONI DATABASE (Scraping e Ricerca)
# ==============================================================================

def aggiorna_db():
    now = datetime.now()
    if st.session_state.last_scrape_time:
        elapsed = (now - st.session_state.last_scrape_time).total_seconds()
        if elapsed < 3600:
            st.warning(f"⏳ Attendi {int((3600 - elapsed) / 60)} minuti prima di riaggiornare.")
            return
            
    progress_bar = st.progress(0)
    status_text = st.empty()
    total_sources = sum(len(v) for v in SOURCES_MAP.values())
    current = 0
    success_count = 0
    
    for categoria, sources in SOURCES_MAP.items():
        for src in sources:
            current += 1
            status_text.text(f"Scarico {src['nome']} ({current}/{total_sources})...")
            progress_bar.progress(current / total_sources)
            try:
                # Delay Random per Anti-Ban
                time.sleep(random.uniform(3, 6))
                
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                response = requests.get(src['url'], headers=headers, timeout=15)
                response.raise_for_status()
                
                dataframes = pd.read_html(response.text, decimal=",", thousands=".")
                for df in dataframes:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        filepath = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
                        df.to_csv(filepath, index=False)
                        success_count += 1
                        break
            except Exception as e:
                st.warning(f"Errore {src['nome']}: {e}")
                
    status_text.empty(); progress_bar.empty()
    st.session_state.last_scrape_time = now
    st.session_state.scrape_count += 1
    st.success(f"✅ Finito: {success_count} files aggiornati"); time.sleep(2); st.rerun()

def cerca_db(isin, categoria):
    if not valida_isin(isin): return None, None
    
    for src in SOURCES_MAP.get(categoria, []):
        filepath = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
        if not os.path.exists(filepath): continue
        try:
            df = pd.read_csv(filepath)
            col_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
            if col_isin:
                mask = df[col_isin].astype(str).str.contains(isin, case=False, na=False)
                if mask.any(): return df[mask].iloc[0], src
        except: continue
    return None, None

# ==============================================================================
# 7. INTERFACCIA UTENTE (GUI)
# ==============================================================================

def login():
    st.title("🔒 Login Terminale")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("---")
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u == SEGRETO_UTENTE and ph == SEGRETO_PASSWORD_HASH:
                st.session_state.logged_in = True; st.rerun()
            else: st.error("Errore Credenziali")

def main_app():
    # --- BARRA LATERALE ---
    with st.sidebar:
        st.title("🏛️ MENU")
        
        # Pulsanti Navigazione (Testo Nero)
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("⚔️ Confronto Bond", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider(); st.subheader("⚙️ SISTEMA")
        
        # Info Data
        last = get_last_update_time()
        if last:
            fmt = last.strftime("%d/%m %H:%M")
            if last.date() == date.today(): st.success(f"📅 Aggiornato: {fmt}")
            else: st.warning(f"⚠️ Vecchio: {fmt}")
        else: st.error("❌ Nessun Dato")
        
        # Test Connessione
        c1, c2 = st.columns([1, 2])
        if c1.button("📶"): st.session_state.connection_status = check_connection_status()
        c2.markdown(f"**{st.session_state.connection_status}**")
        
        # Tasto Aggiorna
        if st.button("🔄 Aggiorna Database", use_container_width=True):
            if "BANNATO" in st.session_state.connection_status: st.error("Sei bannato! Aspetta.")
            else: aggiorna_db()
            
        # Conteggio File Corretto (Conta solo .csv)
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_sources = sum(len(v) for v in SOURCES_MAP.values())
        st.caption(f"Files: {len(csv_files)}/{tot_sources}")
        
        # Tasto RESET (Per pulire file doppi)
        if st.button("🗑️ Reset Database", use_container_width=True, help="Cancella tutto e ripara errori"):
            for f in os.listdir(DB_FOLDER):
                os.remove(os.path.join(DB_FOLDER, f))
            st.toast("Database pulito!", icon="🧹"); time.sleep(1); st.rerun()
            
        st.divider()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # --- PAGINA 1: SCANNER ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        
        # Legenda Fissa (No tendina)
        st.markdown("### 📍 Guida alle Categorie")
        l1, l2, l3, l4 = st.columns(4)
        with l1: st.markdown("""<div class="legend-box gov"><span class="legend-title">🏛️ GOVERNATIVI</span><b>Stati Sovrani</b><br>Italia, Germania, USA, Francia</div>""", unsafe_allow_html=True)
        with l2: st.markdown("""<div class="legend-box bank"><span class="legend-title">🏦 FINANZIARI</span><b>Banche</b><br>Intesa, UniCredit, Subordinate</div>""", unsafe_allow_html=True)
        with l3: st.markdown("""<div class="legend-box corp"><span class="legend-title">🏭 CORPORATE</span><b>Aziende</b><br>Eni, Stellantis, Telecom, Energy</div>""", unsafe_allow_html=True)
        with l4: st.markdown("""<div class="legend-box spec"><span class="legend-title">💎 SPECIALI</span><b>Misti</b><br>Zero Coupon, Callable, Green</div>""", unsafe_allow_html=True)
        
        st.divider()
        c1, c2 = st.columns([2, 1])
        cat = c1.selectbox("Seleziona Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("Inserisci ISIN", placeholder="Cerca...").strip().upper()
        
        if isin:
            if not valida_isin(isin): st.error("ISIN non valido")
            else:
                with st.spinner("Ricerca in corso..."):
                    row, info = cerca_db(isin, cat)
                    d = processa_riga(row, info) if row is not None else None
                
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality(d, risk, tax)
                    
                    # HEADER RISULTATO
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 25px; border-radius: 12px; border-left: 6px solid #00CC96; margin: 20px 0;">
                        <div class="main-header">{d['desc']}</div>
                        <div class="sub-header">ISIN: {isin} | Fonte: {d['fonte']} | Rating: {d['rating']} | Tax: {tax}%</div>
                        <div style="margin-top:10px;font-size:18px;color:#00CC96;">Score Qualità: {qual['score']}/100</div>
                    </div>""", unsafe_allow_html=True)
                    
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Prezzo", f"{d['pr']}€")
                    m2.metric("YTM Lordo", f"{risk['ytm']:.2f}%" if risk else "N/A")
                    m3.metric("YTM Netto", f"{qual['ytm_netto']:.2f}%")
                    m4.metric("Cedola", f"{d['ced']}%")
                    m5.metric("Durata", f"{(d['sc'] - date.today()).days / 365.25:.1f} Y")
                    
                    # SIMULATORE (Spostato qui come richiesto)
                    st.divider()
                    st.subheader("💶 Simulatore Rendimento")
                    c_sim1, c_sim2 = st.columns([1, 2])
                    with c_sim1: imp = st.number_input("Capitale da Investire (€)", value=10000, step=1000)
                    df_flussi = genera_flussi(d, imp, tax)
                    prof = df_flussi['Flow'].sum() - imp
                    with c_sim2: st.metric("Profitto Netto Totale", f"{prof:+.2f}€", f"Su {imp:,.0f}€")
                    
                    st.divider()
                    r1, r2 = st.columns([1, 2])
                    with r1:
                        st.subheader("⚠️ Rischio")
                        if risk: st.markdown(f"""
                            <div class="metric-card"><b>Mod. Duration:</b> {risk['mod_dur']:.2f}</div>
                            <div class="metric-card"><b>Convexity:</b> {risk['convexity']:.2f}</div>
                            <div class="metric-card"><b>DV01 (10k€):</b> {risk['dv01']*(imp/10000):.2f}€</div>
                            """, unsafe_allow_html=True)
                    with r2:
                        st.subheader("⚡ Stress Test")
                        if risk:
                            shocks = [-100, -50, 0, +50, +100]
                            prices = [stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s) for s in shocks]
                            fig = go.Figure(go.Scatter(x=shocks, y=prices, mode='lines+markers+text', text=[f"{p:.1f}" for p in prices], textposition="top center", line=dict(color='#636EFA', width=3)))
                            fig.update_layout(height=250, margin=dict(t=20,b=0), template="plotly_dark", xaxis_title="Variazione Bps", yaxis_title="Prezzo")
                            st.plotly_chart(fig, use_container_width=True)
                    
                    c_flg, c_cf = st.columns([1, 2])
                    with c_flg:
                        st.subheader("🚩 Flags")
                        for ft, txt in qual['flags']:
                            color = "red-flag" if ft=="red" else "warning-flag" if ft=="warning" else "green-flag"
                            st.markdown(f'<div class="{color}">{txt}</div>', unsafe_allow_html=True)
                        if not qual['flags']: st.markdown('<div class="green-flag">✅ Nessun problema rilevato</div>', unsafe_allow_html=True)
                    
                    with c_cf:
                        t1, t2 = st.tabs(["💰 Flussi", "⚙️ Azioni"])
                        with t1:
                            fig_cf = px.bar(df_flussi, x='Data', y='Flow', color='Tipo', title="Cash Flow", template="plotly_dark")
                            fig_cf.update_layout(height=250, margin=dict(t=30,b=0))
                            st.plotly_chart(fig_cf, use_container_width=True)
                        with t2:
                            if st.button("📌 Salva per Confronto"): st.session_state.confronto = d; st.success("Salvato!")
                            if st.button("💼 Aggiungi a Portafoglio"):
                                st.session_state.portfolio.append({"ISIN": isin, "Desc": d['desc'], "Nominale": imp, "Valore": (imp*d['pr'])/100, "YTM": risk['ytm'] if risk else 0, "Scadenza": d['sc']})
                                st.success("Aggiunto!")
                else: st.info("ISIN non trovato. Prova ad aggiornare il database.")

    # --- PAGINA 2: CONFRONTO ---
    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto Bond")
        if st.session_state.confronto:
            a = st.session_state.confronto
            st.info(f"📌 Bond A: {a['desc']}")
            c1, c2 = st.columns(2)
            cb = c1.selectbox("Categoria B", list(SOURCES_MAP.keys()))
            ib = c2.text_input("ISIN B").strip().upper()
            if st.button("VS") and ib:
                rb, info = cerca_db(ib, cb)
                b = processa_riga(rb, info) if rb is not None else None
                if b:
                    ra = calcola_metriche_rischio(a['pr'], a['ced'], a['sc'], a['freq'])
                    rb = calcola_metriche_rischio(b['pr'], b['ced'], b['sc'], b['freq'])
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("A YTM Netto", f"{analizza_bond_quality(a, ra, determina_tasse(a['fonte'], a['desc']))['ytm_netto']:.2f}%")
                    k2.markdown("<h2 style='text-align:center'>VS</h2>", unsafe_allow_html=True)
                    k3.metric("B YTM Netto", f"{analizza_bond_quality(b, rb, determina_tasse(b['fonte'], b['desc']))['ytm_netto']:.2f}%")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Duration'], y=[ra['mod_dur']], marker_color='#EF553B'))
                    fig.add_trace(go.Bar(name='B', x=['Duration'], y=[rb['mod_dur']], marker_color='#00CC96'))
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("Bond B non trovato")
        else: st.warning("Salva prima un bond dalla pagina Scanner.")

    # --- PAGINA 3: PORTAFOGLIO ---
    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        with st.expander("➕ Aggiungi Manualmente"):
            c1, c2, c3, c4 = st.columns([2,2,2,1])
            pc = c1.selectbox("Cat", list(SOURCES_MAP.keys()), key="pc")
            pi = c2.text_input("ISIN", key="pi").strip().upper()
            pn = c3.number_input("Nominale", 1000, key="pn")
            if c4.button("Add") and pi:
                r, i = cerca_db(pi, pc)
                d = processa_riga(r, i) if r is not None else None
                if d:
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    st.session_state.portfolio.append({"ISIN": pi, "Desc": d['desc'], "Nominale": pn, "Valore": (pn*d['pr'])/100, "YTM": risk['ytm'] if risk else 0, "Scadenza": d['sc']})
                    st.success("Aggiunto")
                    st.rerun()
        
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            tot = df['Valore'].sum()
            st.metric("Valore Totale Portafoglio", f"{tot:,.0f}€")
            st.dataframe(df, use_container_width=True)
            if st.button("Reset Portafoglio"): st.session_state.portfolio=[]; st.rerun()
        else: st.info("Il portafoglio è vuoto.")

if st.session_state.logged_in: main_app()
else: login()
