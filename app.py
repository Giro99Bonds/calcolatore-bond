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
    /* --- CARD METRICHE E RISCHIO --- */
    .metric-card {
        background-color: #1e2130; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #3e445b; 
        margin-bottom: 10px;
        color: #ffffff !important;
    }
    .metric-card b { color: #00CC96; }

    /* --- MENU LATERALE --- */
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
        border-left: 4px solid #00CC96;
    }

    /* --- BOX UTENTE ATTIVO --- */
    .user-box {
        padding: 10px;
        background-color: #e8f5e9;
        border-left: 5px solid #00CC96;
        border-radius: 5px;
        margin-bottom: 20px;
        color: #1b5e20;
        font-weight: bold;
    }

    /* --- LEGENDA --- */
    .legend-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; color: white; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .legend-title { font-weight: bold; font-size: 16px; display: block; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px; text-transform: uppercase; }
    
    .gov { background-color: #1a4a2e; border: 1px solid #28a745; }
    .bank { background-color: #2c3e50; border: 1px solid #8e9aaf; }
    .corp { background-color: #1e3a5f; border: 1px solid #17a2b8; }
    .spec { background-color: #581845; border: 1px solid #d63384; }

    /* --- FLAGS --- */
    .red-flag { border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .green-flag { border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .warning-flag { border-left: 5px solid #ffa500; background-color: #2d2a1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    
    .main-header { font-size: 24px; font-weight: bold; color: white; }
    .sub-header { font-size: 14px; color: #b0b3c5; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIGURAZIONE UTENTI
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
    if 'portfolio' not in st.session_state: st.session_state.portfolio = []
    if 'confronto' not in st.session_state: st.session_state.confronto = None
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    if 'current_user' not in st.session_state: st.session_state.current_user = ""
    if 'connection_status' not in st.session_state: st.session_state.connection_status = "In attesa..."
    if 'page' not in st.session_state: st.session_state.page = "Scanner"
    if 'last_scrape_time' not in st.session_state: st.session_state.last_scrape_time = None
    if 'scrape_count' not in st.session_state: st.session_state.scrape_count = 0

init_session_state()

# ==============================================================================
# 3. MAPPA FONTI
# ==============================================================================

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

# ==============================================================================
# 4. FUNZIONI DI UTILITÀ
# ==============================================================================

def valida_isin(isin):
    if not isin or len(isin) != 12: return False
    if not isin[:2].isalpha() or not isin[2:].isalnum(): return False
    return True

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
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.head("https://www.simpletoolsforinvestors.eu/", headers=headers, timeout=5)
        if r.status_code == 200: return "🟢 ONLINE"
        elif r.status_code in [403, 429]: return "🔴 BANNATO (403/429)"
        else: return f"🟡 STATUS {r.status_code}"
    except: return "🔴 OFFLINE"

def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s:
        try: return float(s.replace('k', '')) * 1000
        except: return 1000.0
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

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
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating}
    except: return None

# ==============================================================================
# 5. RISK ENGINE
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
    if anni <= 0: return None
    
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
    return {"ytm": ytm * 100, "mod_dur": mod_dur, "convexity": convexity, "dv01": dv01}

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    shock = shock_bps / 10000
    delta = (-mod_dur * shock + 0.5 * convexity * (shock ** 2)) * prezzo
    return prezzo + delta

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "REPUBLIC", "TREASURY", "BEI", "EU"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def genera_flussi(dati, importo, tax_rate):
    flussi = []; nom = importo; pr = (importo * dati['pr']) / 100
    flussi.append({"Data": date.today(), "Flow": -pr, "Tipo": "Investimento"})
    
    if dati['freq'] > 0:
        ced_net = (nom * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100)
        curr = dati['sc']
        while curr > date.today() + timedelta(days=2):
            if curr != dati['sc']: flussi.append({"Data": curr, "Flow": ced_net, "Tipo": "Cedola"})
            curr -= timedelta(days=int(365 / dati['freq']))
    
    gain = max(0, nom - pr); rimb = nom - (gain * tax_rate / 100)
    ced_fin = (nom * (dati['ced'] / 100) / dati['freq']) * (1 - tax_rate / 100) if dati['freq'] > 0 else 0
    flussi.append({"Data": dati['sc'], "Flow": rimb + ced_fin, "Tipo": "Rimborso"})
    df = pd.DataFrame(flussi).sort_values("Data"); df['Cum'] = df['Flow'].cumsum()
    return df

def analizza_bond_quality(dati, risk, tax):
    flags = []; score = 100
    if dati['taglio'] > 100000: flags.append(("red", "⚠️ Taglio > 100k")); score -= 20
    elif dati['taglio'] > 50000: flags.append(("warning", "⚠️ Taglio > 50k")); score -= 10
    if dati['pr'] > 110: flags.append(("red", "⚠️ Prezzo > 110")); score -= 15
    elif dati['pr'] > 105: flags.append(("warning", "⚠️ Prezzo > 105")); score -= 5
    ytm_net = risk['ytm'] * (1 - tax / 100) if risk else 0
    if ytm_net < 1.5: flags.append(("red", "⚠️ YTM Netto < Inflazione")); score -= 20
    elif ytm_net < 2.5: flags.append(("warning", "⚠️ YTM Netto basso")); score -= 10
    else: flags.append(("green", "✅ YTM Interessante")); score += 10
    return {"flags": flags, "score": max(0, min(100, score)), "ytm_netto": ytm_net}

# ==============================================================================
# 6. MOTORE SMART ANALYSIS (AGGIORNATO RETAIL-SAFE)
# ==============================================================================

def calcola_rendimento_grezzo(prezzo, cedola, scadenza):
    """Calcolo veloce approssimativo per scansionare migliaia di bond"""
    try:
        anni = (scadenza - date.today()).days / 365.25
        if anni <= 0 or prezzo <= 0: return 0
        gain_annuo = (100 - prezzo) / anni
        rendimento = (cedola + gain_annuo) / prezzo * 100
        return round(rendimento, 2)
    except: return 0

def carica_dati_mercato():
    """Carica tutti i CSV in un unico DataFrame"""
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
                            
                            all_bonds.append({
                                "ISIN": str(row[c_isin]),
                                "Desc": desc,
                                "Prezzo": pr,
                                "Scadenza": sc,
                                "Cedola": ced,
                                "YTM_Grezzo": calcola_rendimento_grezzo(pr, ced, sc),
                                "Anni": (sc - date.today()).days / 365.25,
                                "Fonte": filename.replace('.csv', '')
                            })
                        except: continue
            except: continue
            
    return pd.DataFrame(all_bonds)

def categorizza_rischio(nome, desc, rating):
    """Assegna un livello di rischio semplificato per il retail"""
    nome = nome.upper(); desc = desc.upper()
    gov_safe = ["GERMANIA", "BUND", "FRANCIA", "OAT", "USA", "TREASURY", "BEI", "EU", "EUROPA"]
    if any(k in nome or k in desc for k in gov_safe): return 1
    gov_mid = ["ITALIA", "BTP", "BOT", "CCT", "SPAGNA", "BONOS"]
    if any(k in nome or k in desc for k in gov_mid): return 2
    if "INTESA" in nome or "UNICREDIT" in nome: return 2
    if "SUBORDINAT" in nome or "SUB" in desc: return 4
    if "ROMANIA" in nome or "TURCHIA" in nome: return 4
    return 3 # Default Corporate

def trova_alternative_migliori(bond_target, df_mercato):
    """Logica Retail Safe: Confronta solo Netto e Rischio <= Target"""
    if df_mercato.empty: return pd.DataFrame()
    
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    rischio_target = categorizza_rischio(bond_target['fonte'], bond_target['desc'], bond_target['rating'])
    
    alternative = []
    for _, row in df_mercato.iterrows():
        # 1. Filtro Durata (+/- 1.5 anni)
        if not (anni_target - 1.5 <= row['Anni'] <= anni_target + 1.5): continue
        # 2. Filtro Prezzo (< 105)
        if row['Prezzo'] > 105: continue
        # 3. Filtro Rischio (Mai maggiore)
        rischio_alt = categorizza_rischio(row['Fonte'], row['Desc'], "NR")
        if rischio_alt > rischio_target: continue
        
        # 4. Confronto Netto
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        
        extra = ytm_netto_alt - ytm_netto_target
        if extra > 0.25: # Almeno 0.25% in più
            row['YTM_Netto'] = ytm_netto_alt
            row['Extra_Yield_Netto'] = extra
            alternative.append(row)
            
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty:
        return df_alt.sort_values('Extra_Yield_Netto', ascending=False).head(5)
    return pd.DataFrame()

# ==============================================================================
# 7. FUNZIONI DATABASE
# ==============================================================================

def aggiorna_db():
    now = datetime.now()
    if st.session_state.last_scrape_time and (now - st.session_state.last_scrape_time).total_seconds() < 3600:
        st.warning("⏳ Attendi un'ora tra gli aggiornamenti"); return
            
    p = st.progress(0); s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values()); c = 0; ok = 0
    
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1; s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            p.progress(c / tot)
            try:
                time.sleep(random.uniform(3, 6))
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
            except: pass
    
    st.session_state.last_scrape_time = now
    st.session_state.scrape_count += 1
    s.empty(); p.empty(); st.success(f"✅ Finito: {ok} files aggiornati"); time.sleep(2); st.rerun()

def cerca_db(isin, cat):
    if not valida_isin(isin): return None, None
    for src in SOURCES_MAP.get(cat, []):
        path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
        if not os.path.exists(path): continue
        try:
            df = pd.read_csv(path)
            col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
            if col:
                mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                if mask.any(): return df[mask].iloc[0], src
        except: continue
    return None, None

# ==============================================================================
# 8. INTERFACCIA UTENTE
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
                st.success(f"Benvenuto {u}!"); time.sleep(1); st.rerun()
            else: st.error("Errore Credenziali")

def main_app():
    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        
        # BOX UTENTE
        if st.session_state.current_user:
            st.markdown(f"""
            <div class="user-box">
                👤 Utente: {st.session_state.current_user.capitalize()}
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True): st.session_state.page = "SmartAnalysis"; st.rerun()
        if st.button("⚔️ Confronto Bond", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider(); st.subheader("⚙️ SISTEMA")
        
        last = get_last_update_time()
        if last: st.success(f"📅 Aggiornato: {last.strftime('%d/%m %H:%M')}")
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
        
        # RESET PROTETTO
        if st.session_state.current_user in ["giulio", "guest"]:
             if st.button("🗑️ Reset Database", use_container_width=True):
                try:
                    for f in os.listdir(DB_FOLDER): os.remove(os.path.join(DB_FOLDER, f))
                    st.toast("Pulito!", icon="🧹"); time.sleep(1); st.rerun()
                except: pass
            
        st.divider(); 
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # --- PAGES ---
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.markdown("### 📍 Guida alle Categorie")
        l1, l2, l3, l4 = st.columns(4)
        with l1: st.markdown("""<div class="legend-box gov"><span class="legend-title">🏛️ GOVERNATIVI</span><b>Stati</b><br>Italia, Germania, USA, Francia</div>""", unsafe_allow_html=True)
        with l2: st.markdown("""<div class="legend-box bank"><span class="legend-title">🏦 FINANZIARI</span><b>Banche</b><br>Intesa, UniCredit, Subordinate</div>""", unsafe_allow_html=True)
        with l3: st.markdown("""<div class="legend-box corp"><span class="legend-title">🏭 CORPORATE</span><b>Aziende</b><br>Eni, Stellantis, Telecom</div>""", unsafe_allow_html=True)
        with l4: st.markdown("""<div class="legend-box spec"><span class="legend-title">💎 SPECIALI</span><b>Misti</b><br>Zero Coupon, 25y+, Callable</div>""", unsafe_allow_html=True)
        
        st.divider()
        c1, c2 = st.columns([2, 1])
        cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("ISIN", placeholder="IT...").strip().upper()
        
        if isin:
            if not valida_isin(isin): st.error("ISIN invalido")
            else:
                with st.spinner("Cercando..."):
                    row, info = cerca_db(isin, cat)
                    d = processa_riga(row, info) if row is not None else None
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality(d, risk, tax)
                    st.markdown(f"""<div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 25px; border-radius: 12px; border-left: 6px solid #00CC96; margin: 20px 0;"><div class="main-header">{d['desc']}</div><div class="sub-header">ISIN: {isin} | Rating: {d['rating']} | Tax: {tax}%</div><div style="margin-top:10px;font-size:18px;color:#00CC96;">Score: {qual['score']}/100</div></div>""", unsafe_allow_html=True)
                    
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Prezzo", f"{d['pr']}€")
                    m2.metric("YTM Lordo", f"{risk['ytm']:.2f}%" if risk else "N/A")
                    m3.metric("YTM Netto", f"{qual['ytm_netto']:.2f}%")
                    m4.metric("Cedola", f"{d['ced']}%")
                    m5.metric("Durata", f"{(d['sc'] - date.today()).days / 365.25:.1f} Y")
                    
                    st.divider(); st.subheader("💶 Simulatore"); c_sim1, c_sim2 = st.columns([1, 2])
                    with c_sim1: imp = st.number_input("Capitale (€)", value=10000, step=1000)
                    df_flussi = genera_flussi(d, imp, tax)
                    prof = df_flussi['Flow'].sum() - imp
                    with c_sim2: st.metric("Profitto Netto", f"{prof:+.2f}€", f"Su {imp:,.0f}€")
                    
                    st.divider(); r1, r2 = st.columns([1, 2])
                    with r1:
                        st.subheader("⚠️ Rischio")
                        if risk: st.markdown(f"""<div class="metric-card"><b>Duration:</b> {risk['mod_dur']:.2f}</div><div class="metric-card"><b>Convexity:</b> {risk['convexity']:.2f}</div>""", unsafe_allow_html=True)
                    with r2:
                        st.subheader("⚡ Stress Test")
                        if risk:
                            shocks = [-100, -50, 0, +50, +100]
                            prices = [stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s) for s in shocks]
                            fig = go.Figure(go.Scatter(x=shocks, y=prices, mode='lines+markers+text', text=[f"{p:.1f}" for p in prices], textposition="top center", line=dict(color='#636EFA', width=3)))
                            fig.update_layout(height=250, margin=dict(t=20,b=0), template="plotly_dark")
                            st.plotly_chart(fig, use_container_width=True)
                    
                    c_flg, c_cf = st.columns([1, 2])
                    with c_flg:
                        st.subheader("🚩 Flags")
                        for ft, txt in qual['flags']:
                            color = "red-flag" if ft=="red" else "warning-flag" if ft=="warning" else "green-flag"
                            st.markdown(f'<div class="{color}">{txt}</div>', unsafe_allow_html=True)
                        if not qual['flags']: st.markdown('<div class="green-flag">✅ Ok</div>', unsafe_allow_html=True)
                    with c_cf:
                        t1, t2 = st.tabs(["💰 Flussi", "⚙️ Azioni"])
                        with t1: st.dataframe(df_flussi, use_container_width=True)
                        with t2:
                            if st.button("📌 Salva Confronto"): st.session_state.confronto = d; st.success("Ok")
                            if st.button("💼 Aggiungi Portafoglio"):
                                st.session_state.portfolio.append({"ISIN": isin, "Desc": d['desc'], "Nominale": imp, "Valore": (imp*d['pr'])/100, "YTM": risk['ytm'] if risk else 0, "Scadenza": d['sc']})
                                st.success("Ok")
                else: st.info("Non trovato. Aggiorna DB.")

    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Fair Value")
        st.caption("Strumenti avanzati per investitori Retail per valutare il posizionamento di mercato.")
        
        with st.spinner("Analizzando l'intero mercato obbligazionario..."):
            df_market = carica_dati_mercato()
        
        if df_market.empty:
            st.warning("⚠️ Database vuoto. Vai su 'Aggiorna Database' nella sidebar.")
        else:
            col_search, col_kpi = st.columns([1, 3])
            with col_search:
                st.markdown("#### 🎯 Analizza Bond")
                isin_smart = st.text_input("Inserisci ISIN", placeholder="Cerca...").strip().upper()
                cat_smart = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
                
            if isin_smart and valida_isin(isin_smart):
                row, info = cerca_db(isin_smart, cat_smart)
                d_smart = processa_riga(row, info) if row is not None else None
                
                if d_smart:
                    d_smart['isin'] = isin_smart
                    ytm_s = calcola_rendimento_grezzo(d_smart['pr'], d_smart['ced'], d_smart['sc'])
                    dur_s = (d_smart['sc'] - date.today()).days / 365.25
                    
                    st.divider()
                    st.subheader("📊 Dove si trova il tuo Bond?")
                    st.markdown(f"Il grafico mostra il tuo bond (**🔴 Rosso**) rispetto a tutti gli altri bond censiti (**🔵 Blu**).")
                    
                    df_clean = df_market[(df_market['Prezzo'] > 50) & (df_market['Prezzo'] < 150) & (df_market['YTM_Grezzo'] < 15)]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_clean['Anni'], y=df_clean['YTM_Grezzo'], mode='markers', name='Mercato', text=df_clean['Desc'], marker=dict(color='#1f77b4', size=6, opacity=0.4)))
                    fig.add_trace(go.Scatter(x=[dur_s], y=[ytm_s], mode='markers+text', name='TUO BOND', text=['📍 TU SEI QUI'], textposition="top center", marker=dict(color='red', size=15, symbol='star')))
                    fig.update_layout(title="Curva dei Rendimenti (Yield Curve)", xaxis_title="Durata (Anni)", yaxis_title="Rendimento Annuo Stimato (%)", template="plotly_dark", height=400, showlegend=True)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    avg_yield_cluster = df_clean[(df_clean['Anni'] > dur_s-1) & (df_clean['Anni'] < dur_s+1)]['YTM_Grezzo'].mean()
                    delta = ytm_s - avg_yield_cluster
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if delta > 0.5: st.success(f"✅ **Occasione?** Questo bond rende il **{delta:.2f}% in più** della media.")
                        elif delta < -0.5: st.error(f"❌ **Caro.** Questo bond rende il **{abs(delta):.2f}% in meno** della media.")
                        else: st.info("⚖️ **Fair Value.** Il rendimento è in linea con il mercato.")
                            
                    st.divider()
                    st.subheader("🔄 Alternative Migliori (Smart Switch)")
                    st.caption("Bond con scadenza simile (+/- 1.5 anni), rischio non superiore e rendimento netto migliore.")
                    
                    alternative = trova_alternative_migliori(d_smart, df_market)
                    
                    if not alternative.empty:
                        st.dataframe(alternative[['ISIN', 'Desc', 'Prezzo', 'YTM_Netto', 'Extra_Yield_Netto']].style.format({'Prezzo': '{:.2f}€', 'YTM_Netto': '{:.2f}%', 'Extra_Yield_Netto': '+{:.2f}%'}), use_container_width=True)
                    else: st.success("🏆 Complimenti! Non ci sono alternative più sicure e redditizie nel database.")
                else: st.error("ISIN non trovato.")
            else: st.info("Inserisci un ISIN per iniziare.")

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
                    # SAFETY CHECKS
                    diff_anni = abs(((a['sc'] - date.today()).days/365.25) - ((b['sc'] - date.today()).days/365.25))
                    tax_a = determina_tasse(a['fonte'], a['desc'])
                    tax_b = determina_tasse(b['fonte'], b['desc'])
                    
                    if diff_anni > 5: st.warning(f"⚠️ Attenzione: Confronti bond con scadenza molto diversa ({diff_anni:.1f} anni diff).")
                    if tax_a != tax_b: st.info("ℹ️ Nota: Tassazioni diverse. Guarda il YTM Netto.")
                    
                    ra = calcola_metriche_rischio(a['pr'], a['ced'], a['sc'], a['freq'])
                    rb = calcola_metriche_rischio(b['pr'], b['ced'], b['sc'], b['freq'])
                    k1, k2, k3 = st.columns(3)
                    k1.metric("A YTM Net", f"{analizza_bond_quality(a, ra, tax_a)['ytm_netto']:.2f}%")
                    k2.markdown("<h2>VS</h2>", unsafe_allow_html=True)
                    k3.metric("B YTM Net", f"{analizza_bond_quality(b, rb, tax_b)['ytm_netto']:.2f}%")
                else: st.error("B non trovato")
        else: st.warning("Salva un bond prima.")

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
