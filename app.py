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

    /* --- SCORECARD TRASPARENTE --- */
    .score-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 0; border-bottom: 1px solid #3e445b;
    }
    .score-good { color: #00CC96; font-weight: bold; }
    .score-bad { color: #FF4B4B; font-weight: bold; }
    .score-neutral { color: #FFAA00; font-weight: bold; }
    
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
    ]
}

# ==============================================================================
# 4. FUNZIONI UTILI & DATABASE
# ==============================================================================

def valida_isin(isin):
    if not isin or len(isin) != 12: return False
    return isin[:2].isalpha() and isin[2:].isalnum()

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
    """
    Restituisce non solo lo score, ma il breakdown dei punti
    """
    breakdown = []
    score = 100 # Partiamo da 100
    
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

    # 2. PREZZO (Efficienza)
    if dati['pr'] > 110:
        punti = -15
        msg = "Molto sopra la pari (Minusvalenza a scadenza)"
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

    # 3. RENDIMENTO (Profitto)
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

    return {"score": max(0, min(100, score)), "breakdown": breakdown, "ytm_netto": ytm_net}

# ==============================================================================
# 6. LOGICHE SMART & DB
# ==============================================================================

def aggiorna_db():
    p = st.progress(0); s = st.empty()
    tot = sum(len(v) for v in SOURCES_MAP.values()); c = 0; ok = 0
    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            c += 1; p.progress(c/tot)
            try:
                r = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any('ISIN' in str(col).upper() for col in df.columns):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        ok += 1; break
            except: pass
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
        if st.button("⚔️ Confronto", use_container_width=True): st.session_state.page = "Confronto"; st.rerun()
        if st.button("💼 Portafoglio", use_container_width=True): st.session_state.page = "Portafoglio"; st.rerun()
        
        st.divider()
        st.write("💰 **Il tuo Patrimonio**")
        st.session_state.patrimonio = st.number_input("Totale investibile (€)", min_value=10000.0, value=st.session_state.patrimonio, step=5000.0)
        
        st.divider()
        if st.button("🔄 Aggiorna DB"): aggiorna_db()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    if st.session_state.page == "Scanner":
        st.title("🔎 Scanner Obbligazionario")
        st.caption("Inserisci un ISIN per analizzare il bond.")
        
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
                    # USIAMO LA NUOVA FUNZIONE DETTAGLIATA
                    qual = analizza_bond_quality_dettagliata(d, risk, tax, st.session_state.patrimonio)
                    
                    # HEADER
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e2130 0%, #2a2d4a 100%); padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 20px;">
                        <h3 style="color:white; margin:0;">{d['desc']}</h3>
                        <div style="color:#b0b3c5; font-size:14px; margin-top:5px;">
                            ISIN: <b>{isin}</b> | Prezzo: <b>{d['pr']}€</b> | Scadenza: <b>{d['sc'].strftime('%d/%m/%Y')}</b> | Tax: <b>{tax}%</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # COLONNE PRINCIPALI
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
                            st.write("📉 **Cosa succede se vendo prima?**")
                            if risk:
                                hold = st.slider("Anni detenzione", 1, max(1, int((d['sc'] - date.today()).days/365.25)), 1)
                                shock = st.slider("Variazione Tassi", -3.0, 3.0, 0.0, 0.5)
                                dur_res = max(0, risk['mod_dur'] - hold)
                                p_fut = d['pr'] - (dur_res * (shock/100) * d['pr']) + ((100-d['pr']) * (hold/risk['mod_dur']))
                                st.metric("Prezzo Stimato", f"{p_fut:.2f}€", delta=f"{p_fut-d['pr']:.2f}")
                        
                        with t3:
                            st.write("📅 **Calendario Incassi**")
                            df_cf = genera_flussi(d, 10000, tax)
                            st.dataframe(df_cf[df_cf['Data'] > date.today()].style.format({'Flow': '{:.2f}€'}), use_container_width=True)

                    # --- SEZIONE SCORECARD TRASPARENTE ---
                    with col_score:
                        st.markdown(f"### 🏆 Score: {qual['score']}/100")
                        
                        # Visualizzazione Punti
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

    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            st.dataframe(df)
            if st.button("Reset"): st.session_state.portfolio = []
        else: st.info("Portafoglio vuoto.")

if st.session_state.logged_in: main_app()
else: login()
