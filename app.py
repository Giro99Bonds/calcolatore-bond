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
if 'confronto' not in st.session_state: st.session_state.confronto = None

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

# --- FUNZIONI CORE ---
def get_db_last_update():
    """Restituisce la data dell'ultimo file modificato"""
    if not os.path.exists(DB_FOLDER): return None
    files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
    if not files: return None
    newest = max(files, key=os.path.getmtime)
    timestamp = os.path.getmtime(newest)
    return datetime.fromtimestamp(timestamp)

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
    status_text.empty(); progress_bar.empty(); st.rerun()

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
    # BARRA LATERALE
    with st.sidebar:
        st.title("🏛️ MENU")
        page = st.radio("Vai a:", ["🔎 Scanner Singolo", "⚔️ Confronto", "💼 Portafoglio"], index=0)
        st.divider()
        st.header("⚙️ Dati")
        
        # LOGICA DATA ULTIMO AGGIORNAMENTO
        last_upd = get_db_last_update()
        if last_upd:
            fmt_date = last_upd.strftime("%d/%m %H:%M")
            if last_upd.date() == date.today():
                st.success(f"✅ Aggiornato: {fmt_date}")
            else:
                st.warning(f"⚠️ Vecchio: {fmt_date}")
        else:
            st.error("❌ Nessun Dato")

        if st.button("🔄 Scarica Tutto (Safe Mode)"):
            aggiorna_database_locale()
            
        st.divider()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # --- PAGINA 1: RICERCA ---
    if page == "🔎 Scanner Singolo":
        st.title("🔎 Scanner Obbligazionario")
        with st.expander("📍 Guida Categorie"):
            c1, c2, c3, c4 = st.columns(4)
            c1.success("🏛️ GOV"); c2.warning("🏦 BANK"); c3.info("🏭 CORP"); c4.error("💎 SPEC")

        c1, c2, c3 = st.columns([2, 1, 1])
        cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()))
        isin = c2.text_input("ISIN", placeholder="IT000...").strip().upper()
        importo = c3.number_input("Simula €", value=10000, step=1000)
        
        if c3.button("Analizza 🚀", use_container_width=True) and isin:
            row, info = cerca_nel_database_locale(isin, cat)
            d = processa_riga_bond(row, info) if row is not None else None
            
            if not d:
                with st.spinner("Cercando online..."):
                    for s in SOURCES_MAP.get(cat, []):
                        try:
                            r = requests.get(s['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                            dfs = pd.read_html(r.text, decimal=",", thousands=".")
                            for df in dfs:
                                if any(c for c in df.columns if 'ISIN' in str(c).upper()):
                                    match = df[df.iloc[:,0].astype(str).str.contains(isin, na=False)]
                                    if not match.empty: d = processa_riga_bond(match.iloc[0], s); break
                        except: pass
                        if d: break
            
            if d:
                tax = determina_tasse(d['fonte'], d['desc'])
                rn, rl = calcola_rendimenti(d, tax)
                df_flussi = genera_flussi_cassa(d, importo, tax)
                
                st.markdown(f"""<div style="background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00CC96; margin-bottom: 20px;"><h2 style="margin:0; color:white;">{d['desc']}</h2><p style="margin:0; color:#b0b3c5;">ISIN: {isin} | Tassa: {tax}%</p></div>""", unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Prezzo", f"{d['pr']}€")
                col2.metric("Rend. Netto", f"{rn*100:.2f}%", delta="Annuo")
                col3.metric("Cedola", f"{d['ced']}%")
                col4.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                
                t1, t2 = st.tabs(["📊 Grafici", "💰 Flussi"])
                with t1:
                    fig = go.Figure(go.Bar(x=[rn*100, rl*100], y=['Netto', 'Lordo'], orientation='h', marker_color=['#00CC96', '#EF553B'], text=[f"{rn*100:.2f}%", f"{rl*100:.2f}%"], textposition='auto'))
                    fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", title="Rendimento %")
                    st.plotly_chart(fig, use_container_width=True)
                with t2:
                    st.dataframe(df_flussi.style.format({"Netto": "{:.2f}€", "Capitale": "{:.2f}€"}), use_container_width=True)
                
                if st.button("📌 Salva per Confronto"):
                    st.session_state.confronto = d
                    st.success(f"Salvato: {d['desc']}")
            else: st.error("Non trovato.")

    # --- PAGINA 2: CONFRONTO ---
    elif page == "⚔️ Confronto":
        st.title("⚔️ Confronto Diretto")
        if st.session_state.confronto:
            saved = st.session_state.confronto
            st.info(f"📌 Titolo A: **{saved['desc']}**")
            
            cb1, cb2 = st.columns([1, 1])
            cat_b = cb1.selectbox("Categoria B", list(SOURCES_MAP.keys()))
            isin_b = cb2.text_input("ISIN B").strip().upper()
            
            if st.button("CONFRONTA ⚡", use_container_width=True) and isin_b:
                rb, ib = cerca_nel_database_locale(isin_b, cat_b)
                db = processa_riga_bond(rb, ib) if rb is not None else None
                
                if db:
                    da = saved
                    ta = determina_tasse(da['fonte'], da['desc']); rna, rla = calcola_rendimenti(da, ta)
                    tb = determina_tasse(db['fonte'], db['desc']); rnb, rlb = calcola_rendimenti(db, tb)
                    
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    c1.metric("TITOLO A", f"{rna*100:.2f}% Netto", f"{da['ced']}% Cedola")
                    c2.markdown("<h2 style='text-align: center;'>VS</h2>", unsafe_allow_html=True)
                    c3.metric("TITOLO B", f"{rnb*100:.2f}% Netto", f"{db['ced']}% Cedola")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Netto'], y=[rna*100], marker_color='#EF553B', text=[f"{rna*100:.2f}%"], textposition='auto'))
                    fig.add_trace(go.Bar(name='B', x=['Netto'], y=[rnb*100], marker_color='#00CC96', text=[f"{rnb*100:.2f}%"], textposition='auto'))
                    fig.update_layout(title="Rendimento Annuo (%)", yaxis_title="%", template="plotly_dark", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("Titolo B non trovato.")
            
            if st.button("❌ Resetta"): st.session_state.confronto = None; st.rerun()
        else: st.warning("Vai su 'Scanner Singolo' e salva un titolo prima.")

    # --- PAGINA 3: PORTAFOGLIO ---
    elif page == "💼 Portafoglio":
        st.title("💼 Il Tuo Portafoglio")
        with st.expander("➕ Aggiungi Titolo", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            p_cat = c1.selectbox("Categoria", list(SOURCES_MAP.keys()), key="p_cat")
            p_isin = c2.text_input("ISIN", key="p_isin").strip().upper()
            p_nom = c3.number_input("Nominale (€)", value=1000, step=1000)
            
            if c4.button("Aggiungi", use_container_width=True) and p_isin:
                row, info = cerca_nel_database_locale(p_isin, p_cat)
                d = processa_riga_bond(row, info) if row is not None else None
                if d:
                    tax = determina_tasse(d['fonte'], d['desc'])
                    rn, rl = calcola_rendimenti(d, tax)
                    st.session_state.portfolio.append({
                        "ISIN": p_isin, "Descrizione": d['desc'], "Nominale": p_nom,
                        "Prezzo": d['pr'], "Valore Mercato": (p_nom * d['pr']) / 100,
                        "Rend. Netto %": rn * 100, "Cedola": d['ced']
                    })
                    st.success("Aggiunto!")
                else: st.error("Non trovato.")

        if len(st.session_state.portfolio) > 0:
            st.divider()
            df_pf = pd.DataFrame(st.session_state.portfolio)
            tot_valore = df_pf["Valore Mercato"].sum()
            df_pf["Peso"] = df_pf["Valore Mercato"] / tot_valore
            w_netto = (df_pf["Rend. Netto %"] * df_pf["Peso"]).sum()
            
            k1, k2 = st.columns(2)
            k1.metric("Totale Portafoglio", f"{tot_valore:,.2f}€")
            k2.metric("Rendimento Netto Ponderato", f"{w_netto:.2f}%")
            
            st.dataframe(df_pf[["ISIN", "Descrizione", "Nominale", "Prezzo", "Rend. Netto %"]], use_container_width=True)
            
            c_ch1, c_ch2 = st.columns(2)
            with c_ch1:
                fig = px.pie(df_pf, values='Valore Mercato', names='Descrizione', title='Allocazione')
                st.plotly_chart(fig, use_container_width=True)
            
            if st.button("🗑️ Svuota Tutto"): st.session_state.portfolio = []; st.rerun()

if st.session_state.logged_in: main_app()
else: login()
