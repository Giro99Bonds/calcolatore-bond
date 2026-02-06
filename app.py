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

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide")

# CREDENZIALI
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# CARTELLA DATABASE LOCALE
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER): os.makedirs(DB_FOLDER)

# --- INIZIALIZZAZIONE STATO ---
if 'portfolio' not in st.session_state: st.session_state.portfolio = []

# --- MAPPA FONTI ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT_FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TDS_2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI CORE (DATABASE & CALCOLO) ---
def aggiorna_database_locale():
    user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36']
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = sum(len(v) for v in SOURCES_MAP.values())
    count = 0
    
    for category, sources in SOURCES_MAP.items():
        for s in sources:
            count += 1
            status_text.markdown(f"⏳ Scarico **{s['nome']}**... ({count}/{total})")
            progress_bar.progress(count / total)
            try:
                time.sleep(random.uniform(3.0, 5.0)) # Anti-ban
                r = requests.get(s['url'], headers={'User-Agent': random.choice(user_agents)}, timeout=20)
                if r.status_code == 200:
                    dfs = pd.read_html(r.text, decimal=",", thousands=".")
                    for df in dfs:
                        if any(c for c in df.columns if 'ISIN' in str(c).upper()):
                            df.to_csv(os.path.join(DB_FOLDER, f"{s['nome']}.csv"), index=False)
                            break
            except: pass
    status_text.empty(); progress_bar.empty(); st.toast("Database Aggiornato!", icon="✅")

def cerca_nel_database_locale(isin, category):
    target_list = SOURCES_MAP.get(category, [])
    for s in target_list:
        path = os.path.join(DB_FOLDER, f"{s['nome']}.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                c_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if c_isin:
                    match = df[df[c_isin].astype(str).str.contains(isin, na=False, case=False)]
                    if not match.empty: return match.iloc[0], s
            except: continue
    return None, None

def processa_riga_bond(row, source_info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
        c_sc = next((c for c in cols if any(k in str(c).lower() for k in ['scadenza', 'data'])), None)
        c_de = next((c for c in cols if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        sc_str = str(row[c_sc])
        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: 
            try: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
            except: return None
        
        desc = str(row[c_de])
        ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": source_info['freq'], "fonte": source_info['nome']}
    except: return None

def determina_tasse(nome_fonte, descrizione_titolo):
    whitelist = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "TDS"]
    if any(w in nome_fonte.upper() for w in whitelist): return 12.5
    if any(k in descrizione_titolo.upper() for k in ["REPUBLIC", "TREASURY", "BTP", "OAT", "BUND"]): return 12.5
    return 26.0

def calcola_rendimenti(dati, tax):
    t_val = tax / 100
    oggi = date.today(); valuta = today_plus_2(oggi)
    anni = (dati['sc'] - valuta).days / 365.25
    if anni <= 0: return 0, 0
    rend_n = (((100 - dati['pr'])*(1-t_val) + (dati['ced'] * anni * (1-t_val))) / dati['pr']) / anni
    rend_l = (((100 - dati['pr']) + (dati['ced'] * anni)) / dati['pr']) / anni
    return rend_n, rend_l

def today_plus_2(d): return d + timedelta(days=2)

def genera_flussi_cassa(dati, importo, tax_rate):
    flussi = []
    nominale = importo
    prezzo_acq = (importo * dati['pr']) / 100
    scadenza = dati['sc']
    freq = dati['freq']
    
    flussi.append({"Data": today_plus_2(date.today()), "Evento": "🔴 Acquisto", "Netto": -prezzo_acq})
    
    if freq > 0:
        ced_netta = (nominale * (dati['ced']/100) / freq) * (1 - tax_rate/100)
        curr = scadenza
        while curr > today_plus_2(date.today()):
            if curr != scadenza: flussi.append({"Data": curr, "Evento": "🟢 Cedola", "Netto": ced_netta})
            curr = curr - timedelta(days=365//freq)
    
    gain = max(0, nominale - prezzo_acq)
    rimborso = nominale - (gain * tax_rate/100)
    ced_finale = (nominale * (dati['ced']/100) / freq) * (1 - tax_rate/100) if freq > 0 else 0
    
    flussi.append({"Data": scadenza, "Evento": "🏁 Rimborso", "Netto": rimborso + ced_finale})
    df = pd.DataFrame(flussi).sort_values(by="Data")
    df['Capitale'] = df['Netto'].cumsum()
    return df

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
def login():
    st.title("🔐 Accesso Terminale")
    with st.form("login"):
        u = st.text_input("Utente"); p = st.text_input("Password", type="password")
        if st.form_submit_button("Entra"):
            if u == SEGRETO_UTENTE and p == SEGRETO_PASSWORD:
                st.session_state.logged_in = True; st.rerun()
            else: st.error("Errore")

# --- APP NAVIGATION ---
def main_app():
    # BARRA LATERALE PER NAVIGAZIONE
    with st.sidebar:
        st.title("🏛️ MENU")
        
        page = st.radio("Vai a:", ["🔎 Scanner Singolo", "⚔️ Confronto", "💼 Portafoglio"], index=0)
        
        st.divider()
        st.header("⚙️ Dati")
        if st.button("🔄 Scarica Tutto (Safe Mode)"):
            aggiorna_database_locale()
        
        files = len([n for n in os.listdir(DB_FOLDER) if n.endswith('.csv')]) if os.path.exists(DB_FOLDER) else 0
        st.caption(f"Database Locale: {files}/28 files")
        
        st.divider()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # --- PAGINA 1: RICERCA SINGOLA ---
    if page == "🔎 Scanner Singolo":
        st.title("🔎 Scanner Obbligazionario")
        
        # LEGENDA
        with st.expander("📍 Guida Categorie (Clicca per espandere)"):
            c1, c2, c3, c4 = st.columns(4)
            c1.success("🏛️ **GOVERNATIVI**: Stati (BTP, Bund, USA)"); c2.warning("🏦 **FINANZIARI**: Banche")
            c3.info("🏭 **CORPORATE**: Aziende"); c4.error("💎 **SPECIALI**: Zero Coupon")

        c1, c2, c3 = st.columns([2, 1, 1])
        cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("ISIN", placeholder="IT000...").strip().upper()
        importo = c3.number_input("Simula €", value=10000, step=1000)
        
        if c3.button("Analizza 🚀", use_container_width=True) and isin:
            # LOGICA RICERCA
            row, info = cerca_nel_database_locale(isin, cat)
            d = processa_riga_bond(row, info) if row is not None else None
            
            if not d: # Fallback Online
                with st.spinner("Cercando online..."):
                    for s in SOURCES_MAP.get(cat, []):
                        try:
                            r = requests.get(s['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                            dfs = pd.read_html(r.text, decimal=",", thousands=".")
                            for df in dfs:
                                if any(c for c in df.columns if 'ISIN' in str(c).upper()):
                                    match = df[df.iloc[:,0].astype(str).str.contains(isin, na=False)] # Generic check
                                    if not match.empty:
                                        d = processa_riga_bond(match.iloc[0], s)
                                        break
                        except: pass
                        if d: break
            
            if d:
                tax = determina_tasse(d['fonte'], d['desc'])
                rn, rl = calcola_rendimenti(d, tax)
                df_flussi = genera_flussi_cassa(d, importo, tax)
                
                st.success(f"Trovato: **{d['desc']}**")
                
                # METRICHE
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Prezzo", f"{d['pr']}€")
                col2.metric("Rend. Netto", f"{rn*100:.2f}%", delta="Annuo")
                col3.metric("Cedola", f"{d['ced']}%")
                col4.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                
                # TABS
                t1, t2 = st.tabs(["📊 Grafici", "💰 Flussi"])
                with t1:
                    fig = go.Figure(go.Bar(x=[rn*100, rl*100], y=['Netto', 'Lordo'], orientation='h', marker_color=['#00CC96', '#EF553B']))
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)
                with t2:
                    st.dataframe(df_flussi.style.format({"Netto": "{:.2f}€", "Capitale": "{:.2f}€"}), use_container_width=True)
            else:
                st.error("Non trovato.")

    # --- PAGINA 2: CONFRONTO ---
    elif page == "⚔️ Confronto":
        st.title("⚔️ Confronto Diretto")
        st.caption("Inserisci due ISIN per vedere chi vince.")
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Titolo A")
            cat_a = st.selectbox("Categoria A", list(SOURCES_MAP.keys()), key="cat_a")
            isin_a = st.text_input("ISIN A", key="isin_a").strip().upper()
        
        with col_b:
            st.subheader("Titolo B")
            cat_b = st.selectbox("Categoria B", list(SOURCES_MAP.keys()), key="cat_b")
            isin_b = st.text_input("ISIN B", key="isin_b").strip().upper()

        if st.button("CONFRONTA ORA ⚡", use_container_width=True):
            if isin_a and isin_b:
                # Recupero A
                ra, ia = cerca_nel_database_locale(isin_a, cat_a)
                da = processa_riga_bond(ra, ia) if ra is not None else None
                # Recupero B
                rb, ib = cerca_nel_database_locale(isin_b, cat_b)
                db = processa_riga_bond(rb, ib) if rb is not None else None
                
                if da and db:
                    ta = determina_tasse(da['fonte'], da['desc'])
                    tb = determina_tasse(db['fonte'], db['desc'])
                    rna, rla = calcola_rendimenti(da, ta)
                    rnb, rlb = calcola_rendimenti(db, tb)
                    
                    # Tabella Vincitore
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("TITOLO A", f"{rna*100:.2f}% Netto", f"{da['ced']}% Cedola")
                    c2.metric("VS", "⚡")
                    c3.metric("TITOLO B", f"{rnb*100:.2f}% Netto", f"{db['ced']}% Cedola", delta_color="normal")
                    
                    # Grafico Confronto
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Rend. Netto'], y=[rna*100], marker_color='#EF553B'))
                    fig.add_trace(go.Bar(name='B', x=['Rend. Netto'], y=[rnb*100], marker_color='#00CC96'))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.info(f"A: {da['desc']}\n\nB: {db['desc']}")
                else:
                    st.error("Uno dei due titoli non è stato trovato nel database locale.")

    # --- PAGINA 3: PORTAFOGLIO ---
    elif page == "💼 Portafoglio":
        st.title("💼 Il Tuo Portafoglio")
        st.caption("Aggiungi i tuoi bond per calcolare il rendimento complessivo.")
        
        # Form Aggiunta
        with st.expander("➕ Aggiungi Titolo al Portafoglio", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            p_cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()), key="p_cat")
            p_isin = c2.text_input("ISIN", key="p_isin").strip().upper()
            p_nom = c3.number_input("Nominale Posseduto (€)", value=1000, step=1000)
            
            if c4.button("Aggiungi", use_container_width=True):
                if p_isin:
                    row, info = cerca_nel_database_locale(p_isin, p_cat)
                    d = processa_riga_bond(row, info) if row is not None else None
                    if d:
                        tax = determina_tasse(d['fonte'], d['desc'])
                        rn, rl = calcola_rendimenti(d, tax)
                        # Aggiungi a session state
                        st.session_state.portfolio.append({
                            "ISIN": p_isin,
                            "Descrizione": d['desc'],
                            "Nominale": p_nom,
                            "Prezzo": d['pr'],
                            "Valore Mercato": (p_nom * d['pr']) / 100,
                            "Rend. Netto %": rn * 100,
                            "Rend. Lordo %": rl * 100,
                            "Cedola": d['ced']
                        })
                        st.success("Aggiunto!")
                    else:
                        st.error("Non trovato nel database locale.")

        # Tabella e Calcoli
        if len(st.session_state.portfolio) > 0:
            st.divider()
            df_pf = pd.DataFrame(st.session_state.portfolio)
            
            # CALCOLO PONDERATO
            tot_valore = df_flussi = df_pf["Valore Mercato"].sum()
            
            # Peso = Valore Mercato / Totale
            df_pf["Peso"] = df_pf["Valore Mercato"] / tot_valore
            
            # Contributo al rendimento = Rendimento * Peso
            w_netto = (df_pf["Rend. Netto %"] * df_pf["Peso"]).sum()
            w_lordo = (df_pf["Rend. Lordo %"] * df_pf["Peso"]).sum()
            cedola_media = (df_pf["Cedola"] * df_pf["Peso"]).sum()
            
            # VISUALIZZAZIONE KPI
            k1, k2, k3 = st.columns(3)
            k1.metric("Valore Totale", f"{tot_valore:,.2f}€")
            k2.metric("Rendimento Netto Ponderato", f"{w_netto:.2f}%", help="Il rendimento reale annuo del tuo portafoglio")
            k3.metric("Cedola Media Ponderata", f"{cedola_media:.2f}%")
            
            # Tabella
            st.dataframe(df_pf[["ISIN", "Descrizione", "Nominale", "Prezzo", "Rend. Netto %"]], use_container_width=True)
            
            # Grafico Torta
            c_chart1, c_chart2 = st.columns(2)
            with c_chart1:
                fig = px.pie(df_pf, values='Valore Mercato', names='Descrizione', title='Allocazione Portafoglio')
                st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🗑️ Svuota Tutto"):
                st.session_state.portfolio = []
                st.rerun()
        else:
            st.info("Il portafoglio è vuoto. Aggiungi dei titoli sopra.")

if st.session_state.logged_in: main_app()
else: login()
