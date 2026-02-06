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

    /* --- 2. MENU SIDEBAR (TESTO NERO - CLEAN LOOK) --- */
    [data-testid="stSidebar"] div.stButton > button {
        background-color: transparent; 
        border: none; 
        text-align: left; 
        color: #000000 !important; /* TESTO NERO */
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
    .red-flag {border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;}
    .green-flag {border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;}
    .warning-flag {border-left: 5px solid #ffa500; background-color: #2d2a1b; padding: 10px; margin-bottom: 5px; color: white; border-radius: 4px;}
    .main-header {font-size: 24px; font-weight: bold; color: white;}
    .sub-header {font-size: 14px; color: #b0b3c5;}
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAZIONE ---
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD_HASH = hashlib.sha256("Giulio99mac!".encode()).hexdigest()

# CARTELLA DATABASE LOCALE
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# --- STATO (Session State) ---
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

# --- MAPPA FONTI (CORRETTA) ---
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

# --- FUNZIONI DI UTILITÀ ---
def valida_isin(isin):
    if not isin or len(isin) != 12: return False
    if not isin[:2].isalpha() or not isin[2:].isalnum(): return False
    return True

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
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.head("https://www.simpletoolsforinvestors.eu/", headers=headers, timeout=5)
        if r.status_code == 200: return "🟢 ONLINE"
        elif r.status_code in [403, 429]: return "🔴 BANNATO (403/429)"
        else: return f"🟡 STATUS {r.status_code}"
    except: return "🔴 OFFLINE"

# --- RISK ENGINE ---
def calcola_ytm_preciso(prezzo, cedola_pct, scadenza, freq, face_value=100):
    if prezzo <= 0 or freq == 0: return None
    cedola_annua = cedola_pct / 100
    anni = (scadenza - date.today()).days / 365.25
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
        t = np.array([anni])
        cf = np.array([face_value])
        freq = 1
    
    df = (1 + ytm / freq) ** (-t * freq)
    mac_dur = np.sum(t * cf * df) / prezzo
    mod_dur = mac_dur / (1 + ytm / freq)
    convexity = np.sum(cf * t * (t + 1/freq) * ((1 + ytm/freq) ** (-(t * freq + 2)))) / prezzo
    dv01 = mod_dur * prezzo * 0.0001
    
    return {"ytm": ytm * 100, "mod_dur": mod_dur, "convexity": convexity, "dv01": dv01}

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    shock = shock_bps / 10000
    delta = (-mod_dur * shock + 0.5 * convexity * (shock**2)) * prezzo
    return prezzo + delta

def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "REPUBLIC", "TREASURY"]
    if any(k in nome.upper() or k in desc.upper() for k in keys): return 12.5
    return 26.0

def pulisci_taglio(v):
    s = str(v).lower().strip()
    if 'k' in s: return float(s.replace('k',''))*1000
    try: return float(s.replace('.','').replace(',','.'))
    except: return 1000.0

def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower() or 'taglio' in str(c).lower()), None)
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
        
        taglio = pulisci_taglio(row[c_min]) if c_min and pd.notna(row[c_min]) else 1000.0
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating}
    except: return None

# --- DATABASE ---
def aggiorna_db():
    p = st.progress(0); s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values()); c=0
    
    for k, v in SOURCES_MAP.items():
        for src in v:
            c+=1; s.text(f"Scarico {src['nome']} ({c}/{tot})...")
            p.progress(c/tot)
            try:
                time.sleep(random.uniform(2,4))
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        break
            except: pass
    
    st.session_state.last_scrape_time = datetime.now()
    s.empty(); p.empty(); st.toast("Aggiornamento Completato!", icon="✅"); st.rerun()

def cerca_db(isin, cat):
    if not valida_isin(isin): return None, None
    for src in SOURCES_MAP.get(cat, []):
        path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any(): return df[mask].iloc[0], src
            except: continue
    return None, None

def genera_flussi(d, imp, tax):
    flussi = []; nom = imp; pr = (imp*d['pr'])/100; sc = d['sc']
    flussi.append({"Data": date.today(), "Flow": -pr, "Tipo": "Investimento"})
    
    if d['freq'] > 0:
        ced_net = (nom*(d['ced']/100)/d['freq'])*(1-tax/100)
        curr = sc
        while curr > date.today() + timedelta(days=2):
            if curr != sc: flussi.append({"Data": curr, "Flow": ced_net, "Tipo": "Cedola"})
            curr -= timedelta(days=365//d['freq'])
            
    gain = max(0, nom-pr); rimb = nom - (gain*tax/100)
    ced_fin = (nom*(d['ced']/100)/d['freq'])*(1-tax/100) if d['freq']>0 else 0
    flussi.append({"Data": sc, "Flow": rimb+ced_fin, "Tipo": "Rimborso"})
    
    df = pd.DataFrame(flussi).sort_values("Data")
    df['Cum'] = df['Flow'].cumsum()
    return df

# --- MAIN ---
def login():
    st.title("🔒 Login"); u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Accedi"):
        ph = hashlib.sha256(p.encode()).hexdigest()
        if u == SEGRETO_UTENTE and ph == SEGRETO_PASSWORD_HASH:
            st.session_state.logged_in = True; st.rerun()
        else: st.error("Errore")

def main_app():
    # SIDEBAR
    with st.sidebar:
        st.title("🏛️ MENU")
        if st.button("🔎 Scanner Singolo", use_container_width=True): st.session_state.page = "Scanner"; st.rerun()
        if st.button("⚔️ Confronto", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider()
        st.subheader("SISTEMA")
        
        ld = get_last_update_time()
        if ld:
            fmt = ld.strftime("%d/%m %H:%M")
            if ld.date() == date.today(): st.success(f"📅 Aggiornato: {fmt}")
            else: st.warning(f"⚠️ Vecchio: {fmt}")
        else: st.error("❌ Nessun Dato")
        
        c1, c2 = st.columns([1,2])
        if c1.button("📶"): st.session_state.connection_status = check_connection_status()
        c2.markdown(f"**{st.session_state.connection_status}**")
        
        with st.expander("ℹ️ Legenda Stato"):
            st.caption("🟢 ONLINE: Puoi aggiornare.\n🔴 BANNATO: Attendi 1h.")
            
        if st.button("🔄 Aggiorna Database (Safe)", use_container_width=True):
            if "BANNATO" in st.session_state.connection_status: st.error("Sei bannato.")
            else: aggiorna_db()
            
        # FIX FILES COUNT + RESET BUTTON
        csv_files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot_src = sum(len(v) for v in SOURCES_MAP.values())
        st.caption(f"Files: {len(csv_files)}/{tot_src}")
        
        if st.button("🗑️ Reset Database", use_container_width=True):
            for f in os.listdir(DB_FOLDER):
                os.remove(os.path.join(DB_FOLDER, f))
            st.toast("Database pulito!", icon="🧹"); time.sleep(1); st.rerun()
            
        st.divider()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # PAGE 1: SCANNER
    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario Pro")
        
        with st.expander("📍 GUIDA CATEGORIE", expanded=True):
            l1, l2, l3, l4 = st.columns(4)
            with l1: st.markdown("""<div class="legend-box gov"><span class="legend-title">🏛️ GOVERNATIVI</span><b>Stati Sovrani</b><br>Italia, Germania, USA, Francia</div>""", unsafe_allow_html=True)
            with l2: st.markdown("""<div class="legend-box bank"><span class="legend-title">🏦 FINANZIARI</span><b>Banche</b><br>Intesa, UniCredit, Subordinate</div>""", unsafe_allow_html=True)
            with l3: st.markdown("""<div class="legend-box corp"><span class="legend-title">🏭 CORPORATE</span><b>Aziende</b><br>Eni, Stellantis, Telecom, Energy</div>""", unsafe_allow_html=True)
            with l4: st.markdown("""<div class="legend-box spec"><span class="legend-title">💎 SPECIALI</span><b>Misti</b><br>Zero Coupon, Callable, Green</div>""", unsafe_allow_html=True)

        st.divider()
        c1, c2 = st.columns([2, 1])
        cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("ISIN", placeholder="Cerca...").strip().upper()
        
        if isin:
            row, info = cerca_db(isin, cat)
            d = processa_riga(row, info) if row is not None else None
            
            if d:
                tax = determina_tasse(d['fonte'], d['desc'])
                risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                
                st.markdown(f"""<div style="background-color:#1e2130;padding:20px;border-radius:10px;border-left:6px solid #00CC96;margin:20px 0;"><div class="main-header">{d['desc']}</div><div class="sub-header">ISIN: {isin} | Fonte: {d['fonte']} | Rating: {d['rating']}</div></div>""", unsafe_allow_html=True)
                
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Prezzo", f"{d['pr']}€")
                ytm = risk['ytm'] if risk else 0
                m2.metric("YTM Lordo", f"{ytm:.2f}%")
                m3.metric("Cedola", f"{d['ced']}%")
                dur = (d['sc'] - date.today()).days / 365.25
                m4.metric("Durata", f"{dur:.1f} Y")
                m5.metric("Taglio", f"{d['taglio']:,.0f}€")
                
                # SIMULATORE POST-RICERCA
                st.divider()
                st.subheader("💶 Simulatore Rendimento")
                c_sim1, c_sim2 = st.columns([1,2])
                with c_sim1: importo = st.number_input("Capitale (€)", value=10000, step=1000)
                df_flussi = genera_flussi(d, importo, tax)
                prof = df_flussi['Flow'].sum() - importo
                with c_sim2: st.metric("Profitto Netto Totale", f"{prof:+.2f}€", f"Su {importo:,.0f}€")
                
                st.divider()
                r1, r2 = st.columns([1, 2])
                with r1:
                    st.subheader("⚠️ Rischio")
                    if risk: st.markdown(f"""<div class="metric-card"><b>Mod. Duration:</b> {risk['mod_dur']:.2f}</div><div class="metric-card"><b>Convexity:</b> {risk['convexity']:.2f}</div><div class="metric-card"><b>DV01:</b> {risk['dv01']*(importo/100):.2f}€</div>""", unsafe_allow_html=True)
                with r2:
                    st.subheader("⚡ Stress Test")
                    if risk:
                        shocks = [-100, -50, 0, +50, +100]
                        prices = [stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s) for s in shocks]
                        fig = go.Figure(go.Scatter(x=shocks, y=prices, mode='lines+markers+text', text=[f"{p:.1f}" for p in prices], textposition="top center", line=dict(color='#636EFA', width=3)))
                        fig.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0), template="plotly_dark", xaxis_title="Bps", yaxis_title="Prezzo")
                        st.plotly_chart(fig, use_container_width=True)
                
                c_flg, c_tab = st.columns([1,2])
                with c_flg:
                    st.subheader("🚩 Flags")
                    if d['taglio'] > 50000: st.markdown('<div class="red-flag">⚠️ Taglio > 50k</div>', unsafe_allow_html=True)
                    if d['pr'] > 105: st.markdown('<div class="red-flag">⚠️ Sopra la pari</div>', unsafe_allow_html=True)
                    if (ytm*(1-tax/100)) < 2.0: st.markdown('<div class="red-flag">⚠️ Rend < Inflazione</div>', unsafe_allow_html=True)
                    else: st.markdown('<div class="green-flag">✅ Ok</div>', unsafe_allow_html=True)
                
                with c_tab:
                    t1, t2 = st.tabs(["💰 Flussi", "⚙️ Azioni"])
                    with t1:
                        fig_cf = px.bar(df_flussi, x='Data', y='Flow', color='Tipo', title="Cash Flow", template="plotly_dark")
                        fig_cf.update_layout(height=250, margin=dict(l=0,r=0,t=30,b=0))
                        st.plotly_chart(fig_cf, use_container_width=True)
                    with t2:
                        if st.button("📌 Salva Confronto"): st.session_state.confronto = d; st.success("Salvato!")
            else: st.info("ISIN non trovato o database vuoto.")

    # PAGE 2: CONFRONTO
    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto")
        if st.session_state.confronto:
            saved = st.session_state.confronto
            st.info(f"📌 A: **{saved['desc']}**")
            c1, c2 = st.columns(2)
            cat_b = c1.selectbox("Cat B", list(SOURCES_MAP.keys()))
            isin_b = c2.text_input("ISIN B").strip().upper()
            if st.button("VS") and isin_b:
                rb, ib = cerca_db(isin_b, cat_b)
                db = processa_riga(rb, ib) if rb is not None else None
                if db:
                    ra = calcola_metriche_rischio(saved['pr'], saved['ced'], saved['sc'], saved['freq'])
                    rb = calcola_metriche_rischio(db['pr'], db['ced'], db['sc'], db['freq'])
                    c1, c2, c3 = st.columns(3)
                    c1.metric("A YTM", f"{ra['ytm']:.2f}%")
                    c2.markdown("<h2 style='text-align:center'>VS</h2>", unsafe_allow_html=True)
                    c3.metric("B YTM", f"{rb['ytm']:.2f}%", delta_color="normal")
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Dur'], y=[ra['mod_dur']], marker_color='#EF553B'))
                    fig.add_trace(go.Bar(name='B', x=['Dur'], y=[rb['mod_dur']], marker_color='#00CC96'))
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("B non trovato")
        else: st.warning("Salva prima un titolo.")

    # PAGE 3: PORTAFOGLIO
    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        with st.expander("➕ Aggiungi"):
            c1, c2, c3, c4 = st.columns([2,1,1,1])
            pc = c1.selectbox("Cat", list(SOURCES_MAP.keys()), key="pc")
            pi = c2.text_input("ISIN", key="pi").strip().upper()
            pn = c3.number_input("Nominale", 1000)
            if c4.button("Add") and pi:
                r, i = cerca_db(pi, pc)
                d = processa_riga(r, i) if r is not None else None
                if d:
                    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                    st.session_state.portfolio.append({"ISIN": pi, "Desc": d['desc'], "Valore": (pn*d['pr'])/100, "YTM": risk['ytm']})
                    st.success("OK")
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            tot = df['Valore'].sum(); w_ytm = (df['YTM'] * (df['Valore']/tot)).sum()
            st.metric("Totale", f"{tot:,.0f}€", f"YTM Pond: {w_ytm:.2f}%")
            st.dataframe(df, use_container_width=True)
            if st.button("Reset"): st.session_state.portfolio=[]; st.rerun()

if st.session_state.logged_in: main_app()
else: login()
