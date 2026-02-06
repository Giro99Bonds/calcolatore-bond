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

# --- CONFIGURAZIONE & CSS ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    .metric-card {background-color: #1e2130; padding: 15px; border-radius: 8px; border: 1px solid #3e445b; margin-bottom: 10px;}
    .red-flag {border-left: 5px solid #ff4b4b; background-color: #2d1b1b; padding: 10px; margin-bottom: 5px;}
    .green-flag {border-left: 5px solid #00cc96; background-color: #1b2d24; padding: 10px; margin-bottom: 5px;}
    .main-header {font-size: 24px; font-weight: bold; color: white;}
    .sub-header {font-size: 14px; color: #b0b3c5;}
    .legend-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 14px; }
    .gov { background-color: #155724; border-left: 5px solid #28a745; color: #d4edda; }
    .bank { background-color: #383d41; border-left: 5px solid #e2e3e5; color: #e2e3e5; }
    .corp { background-color: #0c5460; border-left: 5px solid #17a2b8; color: #d1ecf1; }
    .spec { background-color: #3e243f; border-left: 5px solid #d63384; color: #f8d7da; }
</style>
""", unsafe_allow_html=True)

# CREDENZIALI
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# CARTELLA DATABASE LOCALE
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER)

# --- STATO ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = []
if 'confronto' not in st.session_state: st.session_state.confronto = None
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'connection_status' not in st.session_state: st.session_state.connection_status = "In attesa..."

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

# --- GESTIONE FILES & STATO ---
def get_last_update_time():
    """Recupera la data dell'ultimo file CSV modificato"""
    try:
        if not os.path.exists(DB_FOLDER): return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files: return None
        newest_file = max(files, key=os.path.getmtime)
        timestamp = os.path.getmtime(newest_file)
        return datetime.fromtimestamp(timestamp)
    except: return None

def check_connection_status():
    """Prova a pingare Google e poi il sito target per vedere se siamo bannati"""
    try:
        # Test 1: Internet Generale
        requests.get("https://www.google.com", timeout=3)
        
        # Test 2: Sito Target (Solo Header per non scaricare tutto)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.head("https://www.simpletoolsforinvestors.eu/", headers=headers, timeout=5)
        
        if r.status_code == 200: return "🟢 ONLINE"
        elif r.status_code == 403 or r.status_code == 429: return "🔴 BANNATO (403/429)"
        else: return f"🟡 STATUS {r.status_code}"
    except: return "🔴 OFFLINE"

# --- MOTORE RISK & MATH ---
def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    if prezzo <= 0 or freq == 0: return None
    cedola = cedola_pct / 100; face_value = 100
    giorni = (scadenza - date.today()).days; anni = giorni / 365.25
    if anni <= 0: return None
    
    periodi = int(anni * freq) if int(anni*freq) > 0 else 1
    t = np.arange(1, periodi + 1) / freq
    cf = np.full(periodi, (cedola * face_value) / freq)
    cf[-1] += face_value
    
    ytm_est = (cedola + (100 - prezzo) / anni) / ((100 + prezzo) / 2)
    pv_factors = (1 + ytm_est / freq) ** (-t * freq)
    mac_duration = np.sum(t * cf * pv_factors) / prezzo
    mod_duration = mac_duration / (1 + ytm_est / freq)
    convexity = np.sum(cf * t * (t + 1/freq) * ((1 + ytm_est/freq)**(-(t*freq + 2)))) / prezzo
    dv01 = (mod_duration * prezzo * 0.0001)
    
    return {"ytm": ytm_est * 100, "mod_dur": mod_duration, "convexity": convexity, "dv01": dv01}

def stress_test(prezzo, mod_dur, convexity, shock_bps):
    shock = shock_bps / 10000
    delta_p = (-mod_dur * shock + 0.5 * convexity * (shock**2)) * prezzo
    return prezzo + delta_p

def determina_tasse(nome, desc):
    if any(k in nome.upper() for k in ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "TDS"]): return 12.5
    if any(k in desc.upper() for k in ["REPUBLIC", "TREASURY", "BTP", "OAT", "BUND"]): return 12.5
    return 26.0

def pulisci_taglio(v):
    s = str(v).lower().strip()
    if 'k' in s: return float(s.replace('k',''))*1000
    try: return float(s.replace('.','').replace(',','.'))
    except: return 1000.0

def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if 'prezzo' in str(c).lower() or 'last' in str(c).lower()), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'descrizione' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower() or 'taglio' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        sc_str = str(row[c_sc])
        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
        
        desc = str(row[c_de]); ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        taglio = pulisci_taglio(row[c_min]) if c_min and pd.notna(row[c_min]) else 1000.0
        rating = str(row[c_rat]) if c_rat and pd.notna(row[c_rat]) else "NR"
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'], "fonte": info['nome'], "taglio": taglio, "rating": rating}
    except: return None

# --- DATABASE LOCALE ---
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
                    if any(col for col in df.columns if 'ISIN' in str(col).upper()):
                        df.to_csv(os.path.join(DB_FOLDER, f"{src['nome']}.csv"), index=False)
                        break
            except: pass
    s.empty(); p.empty(); st.toast("Database Aggiornato!", icon="✅"); st.rerun()

def cerca_db(isin, cat):
    for src in SOURCES_MAP.get(cat, []):
        path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                c_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if c_isin and not df[df[c_isin].astype(str).str.contains(isin, na=False)].empty:
                    return df[df[c_isin].astype(str).str.contains(isin, na=False)].iloc[0], src
            except: continue
    return None, None

def genera_flussi(d, imp, tax):
    flussi = []; nom = imp; pr_acq = (imp*d['pr'])/100; sc = d['sc']
    flussi.append({"Data": date.today(), "Flow": -pr_acq, "Tipo": "Investimento"})
    if d['freq']>0:
        net_ced = (nom*(d['ced']/100)/d['freq'])*(1-tax/100)
        curr = sc
        while curr > date.today() + timedelta(days=2):
            if curr != sc: flussi.append({"Data": curr, "Flow": net_ced, "Tipo": "Cedola"})
            curr -= timedelta(days=365//d['freq'])
    gain = max(0, nom-pr_acq); rimb = nom - (gain*tax/100)
    ced_fin = (nom*(d['ced']/100)/d['freq'])*(1-tax/100) if d['freq']>0 else 0
    flussi.append({"Data": sc, "Flow": rimb+ced_fin, "Tipo": "Rimborso"})
    df = pd.DataFrame(flussi).sort_values("Data"); df['Cum'] = df['Flow'].cumsum()
    return df

# --- APP ---
def login():
    st.title("🔒 Login"); u = st.text_input("User"); p = st.text_input("Pass", type="password")
    if st.button("Go"): 
        if u==SEGRETO_UTENTE and p==SEGRETO_PASSWORD: st.session_state.logged_in=True; st.rerun()

def main_app():
    # --- SIDEBAR: PLANCIA DI COMANDO ---
    with st.sidebar:
        st.title("🏛️ MENU")
        page = st.radio("Navigazione", ["🔎 Scanner Singolo", "⚔️ Confronto", "💼 Portafoglio"])
        
        st.divider()
        st.header("⚙️ STATO SISTEMA")
        
        # 1. INFO DATA ULTIMO AGGIORNAMENTO
        last_date = get_last_update_time()
        if last_date:
            fmt = last_date.strftime("%d/%m %H:%M")
            if last_date.date() == date.today():
                st.success(f"📅 Aggiornato: {fmt}")
            else:
                st.warning(f"⚠️ Vecchio: {fmt}")
        else:
            st.error("❌ Nessun Dato")
            
        # 2. TEST CONNESSIONE (BAN CHECK)
        c1, c2 = st.columns([1,2])
        if c1.button("📶"):
            st.session_state.connection_status = check_connection_status()
        c2.markdown(f"**{st.session_state.connection_status}**")
        
        # 3. TASTO AGGIORNAMENTO
        if st.button("🔄 Aggiorna Database (Safe Mode)"):
            if "BANNATO" in st.session_state.connection_status:
                st.error("Non aggiornare! Sei bannato.")
            else:
                aggiorna_db()
        
        st.caption(f"Files Locali: {len(os.listdir(DB_FOLDER)) if os.path.exists(DB_FOLDER) else 0}/28")
        
        st.divider()
        importo = st.number_input("Capitale Sim (€)", value=10000, step=1000)
        if st.button("Esci"): st.session_state.logged_in=False; st.rerun()

    # --- PAGINA 1: SCANNER PRO ---
    if page == "🔎 Scanner Singolo":
        st.title("🔎 Scanner Obbligazionario Pro")
        
        # LEGENDA COMPLETA
        with st.expander("📍 GUIDA CATEGORIE (Clicca per espandere)", expanded=False):
            st.markdown("Ecco dove cercare il tuo titolo:")
            l1, l2, l3, l4 = st.columns(4)
            with l1:
                st.markdown("""<div class="legend-box gov"><span class="legend-title">🏛️ GOVERNATIVI</span><b>Titoli di Stato</b><br>• Italia (BTP, BOT)<br>• Germania, Francia<br>• USA, Romania<br>• EU Mix</div>""", unsafe_allow_html=True)
            with l2:
                st.markdown("""<div class="legend-box bank"><span class="legend-title">🏦 FINANZIARI</span><b>Banche</b><br>• Intesa, UniCredit<br>• Banche UE/USA<br>• Subordinate</div>""", unsafe_allow_html=True)
            with l3:
                st.markdown("""<div class="legend-box corp"><span class="legend-title">🏭 CORPORATE</span><b>Aziende</b><br>• Eni, Stellantis<br>• Auto & Energy<br>• Telecom</div>""", unsafe_allow_html=True)
            with l4:
                st.markdown("""<div class="legend-box spec"><span class="legend-title">💎 SPECIALI</span><b>Misti</b><br>• Zero Coupon<br>• Callable<br>• 25+ anni</div>""", unsafe_allow_html=True)

        # INPUT
        st.divider()
        c1, c2 = st.columns([2, 1])
        cat = c1.selectbox("Seleziona Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("Inserisci ISIN", placeholder="Cerca...").strip().upper()
        
        if isin:
            row, info = cerca_db(isin, cat)
            d = processa_riga(row, info) if row is not None else None
            
            if d:
                # Calcoli Pro
                tax = determina_tasse(d['fonte'], d['desc'])
                risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])
                df_flussi = genera_flussi(d, importo, tax)
                profitto = df_flussi['Flow'].sum() - importo
                
                # HEADER BLOOMBERG STYLE
                st.markdown(f"""
                <div style="background-color: #1e2130; padding: 20px; border-radius: 10px; border-left: 6px solid #00CC96; margin: 20px 0;">
                    <div class="main-header">{d['desc']}</div>
                    <div class="sub-header">ISIN: {isin} | Fonte: {d['fonte']} | Rating: {d['rating']}</div>
                </div>
                """, unsafe_allow_html=True)

                # 5 CORE METRICS
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Prezzo", f"{d['pr']}€")
                ytm = risk['ytm'] if risk else 0
                m2.metric("YTM (Lordo)", f"{ytm:.2f}%")
                m3.metric("Cedola", f"{d['ced']}%")
                dur_res = (d['sc'] - date.today()).days / 365.25
                m4.metric("Durata Residua", f"{dur_res:.1f} Y")
                m5.metric("Taglio Min", f"{d['taglio']:,.0f}€")

                st.divider()

                # SEZIONE RISCHIO & STRESS
                r1, r2 = st.columns([1, 2])
                with r1:
                    st.subheader("⚠️ Analisi Rischio")
                    if risk:
                        st.markdown(f"""
                        <div class="metric-card"><b>Modified Duration:</b> {risk['mod_dur']:.2f}<br><span style="font-size:12px;color:#888">Sensibilità ai tassi</span></div>
                        <div class="metric-card"><b>Convexity:</b> {risk['convexity']:.2f}</div>
                        <div class="metric-card"><b>DV01 (10k€):</b> {risk['dv01'] * (importo/100):.2f}€</div>
                        """, unsafe_allow_html=True)
                
                with r2:
                    st.subheader("⚡ Stress Test Tassi")
                    if risk:
                        shocks = [-100, -50, 0, +50, +100]
                        prices = [stress_test(d['pr'], risk['mod_dur'], risk['convexity'], s) for s in shocks]
                        fig = go.Figure(go.Scatter(x=shocks, y=prices, mode='lines+markers+text', text=[f"{p:.1f}" for p in prices], textposition="top center", line=dict(color='#636EFA', width=3)))
                        fig.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0), template="plotly_dark", xaxis_title="Variazione Bps", yaxis_title="Prezzo Stimato")
                        st.plotly_chart(fig, use_container_width=True)

                # RED FLAGS
                c_flag, c_tab = st.columns([1, 2])
                with c_flag:
                    st.subheader("🚩 Controlli")
                    if d['taglio'] > 50000: st.markdown('<div class="red-flag"><b>⚠️ Illiquido:</b> Taglio > 50k</div>', unsafe_allow_html=True)
                    if d['pr'] > 105: st.markdown('<div class="red-flag"><b>⚠️ Sopra la pari:</b> Rischio minusvalenza</div>', unsafe_allow_html=True)
                    ytm_net = ytm * (1-tax/100)
                    if ytm_net < 2.0: st.markdown(f'<div class="red-flag"><b>⚠️ Rend. Reale Basso:</b> Netto {ytm_net:.2f}% < Inflazione</div>', unsafe_allow_html=True)
                    else: st.markdown('<div class="green-flag">✅ Parametri nella norma</div>', unsafe_allow_html=True)

                with c_tab:
                    t1, t2 = st.tabs(["💰 Cash Flow", "⚙️ Azioni"])
                    with t1:
                        fig_cf = px.bar(df_flussi, x='Data', y='Flow', color='Tipo', title=f"Flussi su {importo}€", template="plotly_dark")
                        fig_cf.update_layout(height=250, margin=dict(l=0,r=0,t=30,b=0))
                        st.plotly_chart(fig_cf, use_container_width=True)
                    with t2:
                        if st.button("📌 Salva per Confronto"):
                            st.session_state.confronto = d
                            st.success("Salvato!")

            else:
                st.info("👈 Inserisci un ISIN. Se non trova nulla, clicca 'Aggiorna Database' nel menu laterale.")

    # --- PAGINA 2: CONFRONTO ---
    elif page == "⚔️ Confronto":
        st.title("⚔️ Arena Confronto")
        if st.session_state.confronto:
            saved = st.session_state.confronto
            st.info(f"📌 Titolo A: **{saved['desc']}**")
            
            c1, c2 = st.columns(2)
            cat_b = c1.selectbox("Categoria B", list(SOURCES_MAP.keys()))
            isin_b = c2.text_input("ISIN B").strip().upper()
            
            if st.button("VS") and isin_b:
                rb, ib = cerca_db(isin_b, cat_b)
                db = processa_riga(rb, ib) if rb is not None else None
                if db:
                    ra = calcola_metriche_rischio(saved['pr'], saved['ced'], saved['sc'], saved['freq'])
                    rb = calcola_metriche_rischio(db['pr'], db['ced'], db['sc'], db['freq'])
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("A: YTM", f"{ra['ytm']:.2f}%")
                    c2.markdown("<h2 style='text-align:center'>VS</h2>", unsafe_allow_html=True)
                    c3.metric("B: YTM", f"{rb['ytm']:.2f}%", delta_color="normal")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Duration'], y=[ra['mod_dur']], marker_color='#EF553B'))
                    fig.add_trace(go.Bar(name='B', x=['Duration'], y=[rb['mod_dur']], marker_color='#00CC96'))
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("B non trovato")
        else: st.warning("Salva prima un titolo dallo scanner.")

    # --- PAGINA 3: PORTAFOGLIO ---
    elif page == "💼 Portafoglio":
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
            tot = df['Valore'].sum()
            w_ytm = (df['YTM'] * (df['Valore']/tot)).sum()
            st.metric("Valore Totale", f"{tot:,.0f}€", f"YTM Ponderato: {w_ytm:.2f}%")
            st.dataframe(df, use_container_width=True)
            if st.button("Reset"): st.session_state.portfolio=[]; st.rerun()

if st.session_state.logged_in: main_app()
else: login()
