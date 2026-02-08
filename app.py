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
    /* --- CARD METRICHE --- */
    .metric-card {
        background-color: #1e2130; 
        padding: 15px; 
        border-radius: 8px; 
        border: 1px solid #3e445b; 
        margin-bottom: 10px;
        color: #ffffff !important;
    }
    
    /* --- MENU SIDEBAR --- */
    [data-testid="stSidebar"] div.stButton > button {
        background-color: transparent; border: none; text-align: left; 
        color: #000000 !important; box-shadow: none; padding-left: 0; 
        font-size: 16px; font-weight: 600;
    }
    [data-testid="stSidebar"] div.stButton > button:hover {
        color: #333333 !important; padding-left: 10px; 
        background-color: rgba(0,0,0,0.05); border-radius: 5px;
    }

    /* --- LEGENDA --- */
    .legend-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; color: white; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    .legend-title { font-weight: bold; font-size: 16px; display: block; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 4px; text-transform: uppercase; }
    
    .gov { background-color: #1a4a2e; border: 1px solid #28a745; }
    .bank { background-color: #2c3e50; border: 1px solid #8e9aaf; }
    .corp { background-color: #1e3a5f; border: 1px solid #17a2b8; }
    .spec { background-color: #581845; border: 1px solid #d63384; }

    /* --- SCORECARD TRASPARENTE --- */
    .score-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 0; border-bottom: 1px solid #3e445b;
    }
    .score-good { color: #00CC96; font-weight: bold; }
    .score-bad { color: #FF4B4B; font-weight: bold; }
    .score-neutral { color: #FFAA00; font-weight: bold; }
    
    /* --- FLAGS --- */
    .red-flag { border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .green-flag { border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }
    .warning-flag { border-left: 5px solid #ffa500; background-color: #2d2a1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px; }

    /* --- BOX UTENTE --- */
    .user-box { padding: 10px; background-color: #e8f5e9; border-left: 5px solid #00CC96; border-radius: 5px; margin-bottom: 20px; color: #1b5e20; font-weight: bold; }
    
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
    if 'patrimonio' not in st.session_state: st.session_state.patrimonio = 50000.0
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
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
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
# 5. RISK ENGINE E SCORECARD DETTAGLIATA
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
    mod_dur = anni / (1 + ytm) # Approx veloce
    return {"ytm": ytm * 100, "mod_dur": mod_dur}

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def analizza_bond_quality_dettagliata(dati, risk, tax, patrimonio):
    breakdown = []
    score = 100
    
    # 1. SOSTENIBILITÀ (Concentrazione)
    peso_bond = (dati['taglio'] / patrimonio) * 100
    if peso_bond > 20:
        punti = -30
        msg = f"Rischio alto: pesa il {peso_bond:.1f}% del patrimonio"
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
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{dati['taglio']/1000:.0f}k €", "msg": msg, "pts": punti, "col": colore})

    # 2. PREZZO
    if dati['pr'] > 110:
        punti = -15
        msg = "Molto sopra la pari (Minusvalenza)"
        colore = "score-bad"
    elif dati['pr'] > 102:
        punti = -5
        msg = "Sopra la pari (Leggera inefficienza)"
        colore = "score-neutral"
    elif dati['pr'] < 95:
        punti = +5
        msg = "Sotto la pari (Genera Plusvalenza)"
        colore = "score-good"
    else:
        punti = 0
        msg = "Prezzo Fair (Vicino a 100)"
        colore = "score-good"
    score += punti
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{dati['pr']:.2f}", "msg": msg, "pts": punti, "col": colore})

    # 3. RENDIMENTO
    ytm_net = risk['ytm'] * (1 - tax / 100) if risk else 0
    if ytm_net < 1.5:
        punti = -20
        msg = "Rendimento troppo basso (rischio inflazione)"
        colore = "score-bad"
    elif ytm_net > 3.0:
        punti = +15
        msg = "Ottimo rendimento netto"
        colore = "score-good"
    else:
        punti = 0
        msg = "Rendimento nella media"
        colore = "score-neutral"
    score += punti
    breakdown.append({"cat": "📈 Rendimento", "val": f"{ytm_net:.2f}%", "msg": msg, "pts": punti, "col": colore})

    # 4. TASSAZIONE
    if tax < 20:
        punti = +5
        msg = "Tassazione agevolata (White List)"
        colore = "score-good"
    else:
        punti = -5
        msg = "Tassazione piena (Corporate)"
        colore = "score-neutral"
    score += punti
    breakdown.append({"cat": "🏛️ Tassazione", "val": f"{tax}%", "msg": msg, "pts": punti, "col": colore})

    # Flags per compatibilità
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
    if df_mercato.empty: return pd.DataFrame()
    
    anni_target = (bond_target['sc'] - date.today()).days / 365.25
    tax_target = determina_tasse(bond_target['fonte'], bond_target['desc'])
    ytm_netto_target = calcola_rendimento_grezzo(bond_target['pr'], bond_target['ced'], bond_target['sc']) * (1 - tax_target/100)
    rischio_target = categorizza_rischio(bond_target['fonte'], bond_target['desc'], bond_target['rating'])
    
    alternative = []
    for _, row in df_mercato.iterrows():
        if not (anni_target - 1.5 <= row['Anni'] <= anni_target + 1.5): continue
        if row['Prezzo'] > 105: continue
        
        rischio_alt = categorizza_rischio(row['Fonte'], row['Desc'], "NR")
        if rischio_alt > rischio_target: continue
        
        tax_alt = determina_tasse(row['Fonte'], row['Desc'])
        ytm_netto_alt = row['YTM_Grezzo'] * (1 - tax_alt/100)
        
        extra = ytm_netto_alt - ytm_netto_target
        if extra > 0.25: 
            row['YTM_Netto'] = ytm_netto_alt
            row['Extra_Yield_Netto'] = extra
            alternative.append(row)
            
    df_alt = pd.DataFrame(alternative)
    if not df_alt.empty:
        return df_alt.sort_values('Extra_Yield_Netto', ascending=False).head(5)
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
    return pd.DataFrame(flussi).sort_values("Data")

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
        
        # --- SEZIONE SISTEMA ---
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
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Inserisci un ISIN per analizzare il bond.")
        
        # --- LEGENDA ---
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
            if not valida_isin(isin): st.error("❌ ISIN non valido")
            else:
                row, info = cerca_db(isin, cat)
                d = processa_riga(row, info) if row is not None else None
                
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    qual = analizza_bond_quality_dettagliata(d, risk, tax, st.session_state.patrimonio)
                    
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 20px;">
                        <h3 style="color:white; margin:0;">{d['desc']}</h3>
                        <div style="color:#b0b3c5; font-size:14px; margin-top:5px;">
                            ISIN: <b>{isin}</b> | Prezzo: <b>{d['pr']}€</b> | Scadenza: <b>{d['sc'].strftime('%d/%m/%Y')}</b> | Tax: <b>{tax}%</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_metrics, col_score = st.columns([2, 1])
                    
                    with col_metrics:
                        t1, t2, t3 = st.tabs(["📊 Analisi", "🔮 Simulatore", "📅 Cedole"])
                        
                        with t1:
                            m1, m2, m3 = st.columns(3)
                            m1.metric("YTM Netto", f"{qual['ytm_netto']:.2f}%")
                            m2.metric("Cedola", f"{d['ced']}%")
                            m3.metric("Duration", f"{risk['mod_dur']:.2f}" if risk else "N/A")
                            
                            st.write("---")
                            st.caption("🍔 **Rendimento Reale**")
                            inf = st.slider("Inflazione attesa", 0.0, 10.0, 2.0, 0.5)
                            real = qual['ytm_netto'] - inf
                            if real > 0: st.success(f"Guadagno Reale: +{real:.2f}%")
                            else: st.error(f"Perdita Reale: {real:.2f}%")
                        
                        with t2:
                            st.warning("🔮 **Sfera di Cristallo:** Cosa succede se vendi PRIMA della scadenza e i tassi cambiano?")
                            if risk:
                                # Calcolo anni residui esatti
                                anni_residui_float = (d['sc'] - date.today()).days / 365.25
                                max_anni_slider = int(anni_residui_float)
                                
                                # FIX PER ERRORI SLIDER
                                if max_anni_slider < 1:
                                    st.info("ℹ️ Il bond scade tra meno di un anno. Simulazione non necessaria.")
                                else:
                                    cw1, cw2 = st.columns(2)
                                    with cw1:
                                        if max_anni_slider == 1:
                                            st.write("Anni detenzione: **1 anno**")
                                            hold = 1
                                        else:
                                            hold = st.slider("Anni detenzione", 1, max_anni_slider, 1)
                                    with cw2:
                                        shock = st.slider("Variazione Tassi", -3.0, 3.0, 0.0, 0.5)
                                    
                                    dur_res = max(0, risk['mod_dur'] - hold)
                                    p_fut = d['pr'] - (dur_res * (shock/100) * d['pr']) + ((100-d['pr']) * (hold/anni_residui_float))
                                    st.metric("Prezzo Stimato", f"{p_fut:.2f}€", delta=f"{p_fut-d['pr']:.2f}")
                            else: st.error("Dati insufficienti")
                        
                        with t3:
                            st.write("📅 **Calendario Incassi**")
                            df_cf = genera_flussi(d, 10000, tax)
                            st.dataframe(df_cf[df_cf['Data'] > date.today()].style.format({'Flow': '{:.2f}€'}), use_container_width=True)

                    with col_score:
                        st.markdown(f"### 🏆 Score: {qual['score']}/100")
                        for item in qual['breakdown']:
                            st.markdown(f"""
                            <div class="score-row">
                                <div>
                                    <div>{item['cat']}</div>
                                    <div style="font-size:12px; color:#aaa;">{item['msg']}</div>
                                </div>
                                <div class="{item['col']}">{item['pts']:+d}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        st.write("")
                        if st.button("💼 Aggiungi a Portafoglio", use_container_width=True):
                            st.session_state.portfolio.append(d)
                            st.toast("Aggiunto!")

                else: st.warning("Bond non trovato. Aggiorna il DB.")

    elif st.session_state.page == "SmartAnalysis":
        st.title("🧠 Smart Analysis & Fair Value")
        st.caption("Strumenti avanzati per investitori Retail per valutare il posizionamento di mercato.")
        with st.spinner("Analizzando l'intero mercato obbligazionario..."):
            df_market = carica_dati_mercato()
        
        if df_market.empty: st.warning("⚠️ Database vuoto. Vai su 'Aggiorna Database' nella sidebar.")
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
