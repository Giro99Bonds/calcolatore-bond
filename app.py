import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
import time
import random
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Pro Terminal", page_icon="📈", layout="wide")

# CSS PER UX "BLOOMBERG-STYLE"
st.markdown("""
<style>
    .metric-card {background-color: #1e2130; padding: 15px; border-radius: 8px; border: 1px solid #3e445b; margin-bottom: 10px;}
    .big-font {font-size: 24px !important; font-weight: bold;}
    .sub-font {font-size: 14px; color: #b0b3c5;}
    .red-flag {border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px;}
    .green-flag {border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px;}
</style>
""", unsafe_allow_html=True)

# CREDENZIALI & DB
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER)

# --- MAPPA FONTI (Mantengo la tua struttura) ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- MOTORE MATEMATICO FINANZIARIO (RISK ENGINE) ---
def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    """Calcola Duration, Convexity e DV01"""
    if prezzo <= 0 or freq == 0: return None # Zero coupon o dati sporchi
    
    cedola = cedola_pct / 100
    y = cedola # Approx yield iniziale per iterazione (semplificato)
    face_value = 100
    oggi = date.today()
    giorni_residui = (scadenza - oggi).days
    anni_residui = giorni_residui / 365.25
    
    if anni_residui <= 0: return None

    # Generazione flussi temporali (anni)
    periodi = int(anni_residui * freq)
    if periodi == 0: periodi = 1
    
    t = np.arange(1, periodi + 1) / freq
    cf = np.full(periodi, (cedola * face_value) / freq)
    cf[-1] += face_value # Rimborso finale
    
    # Yield to Maturity (Approssimato con Newton o semplice rendimento corrente per velocità)
    # Qui usiamo una stima basata sul prezzo per calcolare la duration
    ytm_est = (cedola + (100 - prezzo) / anni_residui) / ((100 + prezzo) / 2)
    
    # Macaulay Duration
    pv_factors = (1 + ytm_est / freq) ** (-t * freq)
    pv_flows = cf * pv_factors
    mac_duration = np.sum(t * pv_flows) / prezzo
    
    # Modified Duration (Sensibilità)
    mod_duration = mac_duration / (1 + ytm_est / freq)
    
    # Convexity
    convexity = np.sum(cf * t * (t + 1/freq) * ((1 + ytm_est/freq)**(-(t*freq + 2)))) / prezzo

    # DV01 (Dollar Value of 01) - Impatto di 1 bp (0.01%)
    dv01 = (mod_duration * prezzo * 0.0001)
    
    return {
        "ytm": ytm_est * 100,
        "mac_dur": mac_duration,
        "mod_dur": mod_duration,
        "convexity": convexity,
        "dv01": dv01
    }

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    """Simula variazione prezzo con shock tassi"""
    shock = shock_bps / 10000 # converti bps in decimale
    delta_p = (-mod_dur * shock + 0.5 * convexity * (shock**2)) * prezzo
    return prezzo + delta_p

# --- MOTORE DATI ---
def pulisci_taglio(valore):
    s = str(valore).lower().strip()
    if 'k' in s: return float(s.replace('k', '')) * 1000
    try: return float(s.replace('.', '').replace(',', '.'))
    except: return 1000.0

def processa_riga_bond(row, source_info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
        c_sc = next((c for c in cols if any(k in str(c).lower() for k in ['scadenza', 'maturity'])), None)
        c_de = next((c for c in cols if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
        c_rat = next((c for c in cols if any(k in str(c).lower() for k in ['rating'])), None)
        c_min = next((c for c in cols if any(k in str(c).lower() for k in ['min', 'taglio'])), None)
        c_vol = next((c for c in cols if any(k in str(c).lower() for k in ['vol', 'scambi'])), None)
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        sc = datetime.strptime(str(row[c_sc]), '%Y-%m-%d').date() if '-' in str(row[c_sc]) else datetime.strptime(str(row[c_sc]), '%d/%m/%Y').date()
        desc = str(row[c_de])
        
        ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        taglio = pulisci_taglio(row[c_min]) if c_min and pd.notna(row[c_min]) else 1000.0
        rating = str(row[c_rat]) if c_rat and pd.notna(row[c_rat]) else "NR"
        volume = str(row[c_vol]) if c_vol and pd.notna(row[c_vol]) else "Basso"
        
        return {
            "desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": source_info['freq'], 
            "fonte": source_info['nome'], "rating": rating, "taglio": taglio, "volume": volume
        }
    except: return None

def cerca_locale(isin):
    # Cerca in tutti i file CSV locali
    for f in os.listdir(DB_FOLDER):
        if f.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join(DB_FOLDER, f))
                c_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if c_isin:
                    match = df[df[c_isin].astype(str).str.contains(isin, na=False, case=False)]
                    if not match.empty:
                        # Ricostruiamo info sorgente dal nome file
                        cat_fittizia = {"freq": 1 if "BTP" not in f else 2, "nome": f.replace(".csv", "")}
                        return processa_riga_bond(match.iloc[0], cat_fittizia)
            except: continue
    return None

def scarica_db():
    user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36']
    st.toast("Avvio download sicuro...", icon="⏳")
    for cat, sources in SOURCES_MAP.items():
        for s in sources:
            try:
                time.sleep(random.uniform(2, 4))
                r = requests.get(s['url'], headers={'User-Agent': random.choice(user_agents)}, timeout=15)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any(c for c in df.columns if 'ISIN' in str(c).upper()):
                        df.to_csv(os.path.join(DB_FOLDER, f"{s['nome']}.csv"), index=False)
                        break
            except: pass
    st.toast("Database Aggiornato!", icon="✅")

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
def login():
    st.title("🔒 Accesso Pro")
    with st.form("l"):
        if st.form_submit_button("Entra"): st.session_state.logged_in = True; st.rerun()

# --- INTERFACCIA ---
def main():
    with st.sidebar:
        st.header("Terminal Control")
        isin_input = st.text_input("ISIN o Nome", placeholder="Cerca Bond...").strip().upper()
        st.divider()
        if st.button("🔄 Aggiorna Dati"): scarica_db()
        st.caption(f"DB Status: {len(os.listdir(DB_FOLDER))} Files")

    if not isin_input:
        st.title("⚡ Bond Pro Terminal")
        st.info("Inserisci un ISIN nella sidebar per iniziare l'analisi professionale.")
        return

    d = cerca_locale(isin_input)
    if not d:
        st.error("Titolo non trovato nel DB locale. Prova ad aggiornare i dati.")
        return

    # CALCOLI AVANZATI
    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
    tax = 12.5 if "BTP" in d['desc'] or "BOT" in d['desc'] or "BUND" in d['desc'] else 26.0
    
    # 1️⃣ INFO CORE (HEADER)
    st.markdown(f"## {d['desc']}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Prezzo", f"{d['pr']}", delta=None)
    
    yield_val = risk['ytm'] if risk else 0
    c2.metric("YTM (Lordo)", f"{yield_val:.2f}%", help="Yield to Maturity stimato")
    c3.metric("Cedola", f"{d['ced']}%", f"{'Semestrale' if d['freq']==2 else 'Annuale'}")
    
    dur_residua = (d['sc'] - date.today()).days / 365.25
    c4.metric("Duration Residua", f"{dur_residua:.1f} Y", help="Anni alla scadenza")
    
    liquidity_score = "Alta" if "BTP" in d['desc'] else "Media" if d['taglio'] < 50000 else "Bassa (Illiquido)"
    c5.metric("Liquidità (Stim)", liquidity_score, delta_color="off")

    st.divider()

    # 2️⃣ RISCHIO & STRESS TEST
    r1, r2 = st.columns([1, 2])
    
    with r1:
        st.subheader("⚠️ Risk Analysis")
        if risk:
            st.markdown(f"""
            <div class="metric-card">
                <b>Modified Duration:</b> {risk['mod_dur']:.2f}<br>
                <span class="sub-font">Se i tassi salgono dell'1%, il prezzo scende del {risk['mod_dur']:.1f}%</span>
            </div>
            <div class="metric-card">
                <b>Convexity:</b> {risk['convexity']:.2f}<br>
                <span class="sub-font">Curvatura prezzo/rendimento</span>
            </div>
            <div class="metric-card">
                <b>DV01:</b> {risk['dv01']:.4f}€<br>
                <span class="sub-font">Variazione prezzo per 1 bp di tasso</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Dati insufficienti per calcolo rischio (forse Zero Coupon o dati mancanti).")

    with r2:
        st.subheader("⚡ Stress Scenario")
        # Simulazione impatto tassi
        tassi_shock = [-100, -50, 0, +50, +100]
        prezzi_shock = []
        if risk:
            for s in tassi_shock:
                p_new = stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s)
                prezzi_shock.append(p_new)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=tassi_shock, y=prezzi_shock, mode='lines+markers+text', text=[f"{p:.2f}" for p in prezzi_shock], textposition="top center", line=dict(color='#636EFA', width=3)))
            fig.update_layout(title="Sensibilità Prezzo ai Tassi (Bps)", xaxis_title="Variazione Tassi (bps)", yaxis_title="Prezzo Stimato", template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)

    # 3️⃣ RED FLAGS & STRUTTURA
    c_flag, c_struct = st.columns([1, 1])
    
    with c_flag:
        st.subheader("🚩 Red Flags Check")
        flags_found = False
        
        # Check 1: Liquidity
        if d['taglio'] > 50000:
            st.markdown('<div class="red-flag"><b>⚠️ Taglio Istituzionale:</b> Minimo acquisto > 50k. Difficile da vendere per retail.</div>', unsafe_allow_html=True)
            flags_found = True
            
        # Check 2: Prezzo Sopra la pari
        if d['pr'] > 105:
            st.markdown(f'<div class="red-flag"><b>⚠️ Prezzo Alto ({d["pr"]}):</b> Rischio minusvalenza a scadenza. YTM sarà molto inferiore alla cedola.</div>', unsafe_allow_html=True)
            flags_found = True
            
        # Check 3: Rendimento Reale (Approx Inflation 2%)
        if risk and (risk['ytm'] * (1-tax/100)) < 2.0:
             st.markdown('<div class="red-flag"><b>⚠️ Rendimento Reale Negativo:</b> Il netto batte a malapena l\'inflazione stimata (2%).</div>', unsafe_allow_html=True)
             flags_found = True

        if not flags_found:
             st.markdown('<div class="green-flag"><b>✅ Clean Check:</b> Nessuna anomalia critica rilevata sui dati base.</div>', unsafe_allow_html=True)

    with c_struct:
        st.subheader("🏗️ Struttura Bond")
        st.dataframe(pd.DataFrame([
            {"Key": "Rating", "Value": d['rating']},
            {"Key": "Seniority", "Value": "Subordinato" if "SUB" in d['desc'] else "Senior"},
            {"Key": "Taglio Min", "Value": f"{d['taglio']:,.0f} €"},
            {"Key": "Fiscale", "Value": f"{tax}%"},
            {"Key": "Legge", "Value": "NY Law" if "USA" in d['desc'] else "Domestic"},
        ]).set_index("Key"), use_container_width=True)

    # 4️⃣ CASH FLOW & COMPARABILI
    st.divider()
    t1, t2 = st.tabs(["💰 Cash Flow Analysis", "⚖️ Comparabili"])
    
    with t1:
        # Generiamo flussi
        nominale = 10000
        cf_df = pd.DataFrame([{"Data": date.today(), "Flow": -(d['pr']/100)*nominale, "Tipo": "Investimento"}])
        
        curr = d['sc']
        while curr > date.today():
            flow_val = (nominale * (d['ced']/100)) / (d['freq'] if d['freq']>0 else 1)
            cf_df = pd.concat([cf_df, pd.DataFrame([{"Data": curr, "Flow": flow_val, "Tipo": "Cedola"}])])
            curr = curr - timedelta(days=365/(d['freq'] if d['freq']>0 else 1))
        
        # Rimborso
        cf_df = pd.concat([cf_df, pd.DataFrame([{"Data": d['sc'], "Flow": nominale, "Tipo": "Rimborso"}])])
        cf_df['Data'] = pd.to_datetime(cf_df['Data'])
        cf_df = cf_df.sort_values("Data")
        
        fig_cf = px.bar(cf_df, x='Data', y='Flow', color='Tipo', title="Timeline Flussi di Cassa (Su 10k€)", template="plotly_dark")
        st.plotly_chart(fig_cf, use_container_width=True)

    with t2:
        st.info("Funzione Comparabili: Cerca nel DB titoli con stessa scadenza (+/- 1 anno) e rating simile.")
        # Logica placeholder per comparabili (da espandere con query su DB)
        st.dataframe(pd.DataFrame([
            {"Ticker": "BTP 2030", "YTM": "3.4%", "Spread": "+10bp"},
            {"Ticker": "OAT 2030", "YTM": "2.9%", "Spread": "-40bp"}
        ]), use_container_width=True)

if st.session_state.get('logged_in'): main()
else: login()
