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
    if not os.path.exists(DB_FOLDER): return None
    files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
    if not files: return None
    newest = max(files, key=os.path.getmtime)
    return datetime.fromtimestamp(os.path.getmtime(newest))

def aggiorna_database_locale():
    user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36']
    progress_bar = st.progress(0); status_text = st.empty()
    total = sum(len(v) for v in SOURCES_MAP.values()); count = 0
    
    for category, sources in SOURCES_MAP.items():
        for s in sources:
            count += 1
            status_text.markdown(f"⏳ Scarico **{s['nome']}**... ({count}/{total})")
            progress_bar.progress(count / total)
            try:
                time.sleep(random.uniform(3.0, 5.0)) 
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

def pulisci_taglio(valore_grezzo):
    """Converte '100k', '1.000', '1k' in numero"""
    s = str(valore_grezzo).lower().strip()
    if 'k' in s:
        s = s.replace('k', '')
        return float(s) * 1000
    return float(s.replace('.', '').replace(',', '.')) if s.replace('.', '').replace(',', '').isdigit() else 1000.0

def processa_riga_bond(row, source_info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        # Mapping Colonne Flessibile
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if any(k in str(c).lower() for k in ['scadenza', 'maturity'])), None)
        c_de = next((c for c in cols if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
        c_dur = next((c for c in cols if any(k in str(c).lower() for k in ['dur', 'modified'])), None)
        c_rat = next((c for c in cols if any(k in str(c).lower() for k in ['rating', 's&p'])), None)
        c_min = next((c for c in cols if any(k in str(c).lower() for k in ['min', 'taglio', 'lot'])), None)
        c_vol = next((c for c in cols if any(k in str(c).lower() for k in ['vol', 'scambi'])), None)
        
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
        
        # Dati Extra
        duration = float(str(row[c_dur]).replace(',', '.')) if c_dur and pd.notna(row[c_dur]) else 0.0
        rating = str(row[c_rat]) if c_rat and pd.notna(row[c_rat]) else "N/A"
        taglio = pulisci_taglio(row[c_min]) if c_min and pd.notna(row[c_min]) else 1000.0
        volume = str(row[c_vol]) if c_vol and pd.notna(row[c_vol]) else "N/A"
        
        return {
            "desc": desc, "pr": pr, "sc": sc, "ced": ced, 
            "freq": source_info['freq'], "fonte": source_info['nome'],
            "duration": duration, "rating": rating, "taglio": taglio, "volume": volume
        }
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
    with st.sidebar:
        st.title("🏛️ MENU")
        page = st.radio("Vai a:", ["🔎 Scanner Singolo", "⚔️ Confronto", "💼 Portafoglio"], index=0)
        st.divider()
        st.header("⚙️ Dati")
        last = get_db_last_update()
        if last:
            st.caption(f"Ultimo agg: {last.strftime('%d/%m %H:%M')}")
            if last.date() != date.today(): st.warning("⚠️ Dati vecchi")
            else: st.success("✅ Dati aggiornati")
        
        if st.button("🔄 Scarica Tutto (Safe Mode)"): aggiorna_database_locale()
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
            
            # Fallback Online (Singolo tentativo)
            if not d:
                with st.spinner("Ricerca online..."):
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
                
                # --- HEADER TITOLO ---
                st.markdown(f"""
                <div style="background-color: #1e2130; padding: 20px; border-radius: 12px; border-left: 6px solid #00CC96; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                    <h2 style="margin:0; color:white; font-size: 24px;">{d['desc']}</h2>
                    <p style="margin-top:5px; color:#b0b3c5; font-family: monospace; font-size: 14px;">
                        ISIN: <span style="color:#fff; background:#333; padding:2px 6px; border-radius:4px;">{isin}</span> | 
                        Fisco: <span style="color:#ffcc00;">{tax}%</span> | 
                        Fonte: {d['fonte']}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                # METRICHE PRINCIPALI
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Prezzo", f"{d['pr']}€", delta=f"Taglio: {d['taglio']:,.0f}€")
                col2.metric("Rend. Netto", f"{rn*100:.2f}%", delta="Annuo", delta_color="normal")
                col3.metric("Cedola Lorda", f"{d['ced']}%")
                col4.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                
                # --- SCHEDA TECNICA (NUOVA) ---
                st.divider()
                st.subheader("📋 Scheda Tecnica e Rischio")
                c_tech1, c_tech2, c_tech3, c_tech4 = st.columns(4)
                c_tech1.info(f"**Duration (Sensibilità):**\n{d['duration']:.2f}")
                c_tech2.info(f"**Rating:**\n{d['rating']}")
                c_tech3.info(f"**Taglio Minimo:**\n{d['taglio']:,.0f}€")
                c_tech4.info(f"**Volume Scambi:**\n{d['volume']}")
                
                t1, t2 = st.tabs(["📊 Analisi Grafica", "💰 Tabella Flussi"])
                with t1:
                    c_chart1, c_chart2 = st.columns([1, 2])
                    with c_chart1:
                        fig = go.Figure(go.Bar(x=[rl*100, rn*100], y=['Lordo', 'Netto'], orientation='h', marker_color=['#EF553B', '#00CC96'], text=[f"{rl*100:.2f}%", f"{rn*100:.2f}%"], textposition='auto'))
                        fig.update_layout(height=250, margin=dict(l=0,r=0,t=30,b=0), template="plotly_dark", title="Rendimento %")
                        st.plotly_chart(fig, use_container_width=True)
                    with c_chart2:
                        fig_area = go.Figure(go.Scatter(x=df_flussi['Data'], y=df_flussi['Capitale'], fill='tozeroy', line=dict(color='#636EFA', width=3)))
                        fig_area.update_layout(height=250, margin=dict(l=0,r=0,t=30,b=0), template="plotly_dark", title=f"Evoluzione {importo}€")
                        st.plotly_chart(fig_area, use_container_width=True)
                with t2:
                    st.dataframe(df_flussi.style.format({"Netto": "{:.2f}€", "Capitale": "{:.2f}€"}), use_container_width=True)
                
                if st.button("📌 Salva per Confronto"):
                    st.session_state.confronto = d
                    st.success("Salvato!")
            else: st.error("Non trovato. Prova ad aggiornare il database.")

    # --- PAGINA 2: CONFRONTO ---
    elif page == "⚔️ Confronto":
        st.title("⚔️ Confronto Diretto")
        if st.session_state.confronto:
            saved = st.session_state.confronto
            st.info(f"📌 A: **{saved['desc']}**")
            
            c1, c2 = st.columns(2)
            cat_b = c1.selectbox("Categoria B", list(SOURCES_MAP.keys()))
            isin_b = c2.text_input("ISIN B").strip().upper()
            
            if st.button("CONFRONTA ⚡", use_container_width=True) and isin_b:
                rb, ib = cerca_nel_database_locale(isin_b, cat_b)
                db = processa_riga_bond(rb, ib) if rb is not None else None
                if db:
                    da = saved
                    rna, _ = calcola_rendimenti(da, determina_tasse(da['fonte'], da['desc']))
                    rnb, _ = calcola_rendimenti(db, determina_tasse(db['fonte'], db['desc']))
                    
                    st.divider()
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("TITOLO A", f"{rna*100:.2f}% Netto", f"Dur: {da['duration']}")
                    cc2.markdown("<h2 style='text-align: center;'>VS</h2>", unsafe_allow_html=True)
                    cc3.metric("TITOLO B", f"{rnb*100:.2f}% Netto", f"Dur: {db['duration']}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(name='A', x=['Netto'], y=[rna*100], marker_color='#EF553B', text=[f"{rna*100:.2f}%"]))
                    fig.add_trace(go.Bar(name='B', x=['Netto'], y=[rnb*100], marker_color='#00CC96', text=[f"{rnb*100:.2f}%"]))
                    fig.update_layout(title="Rendimento Annuo %", template="plotly_dark", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.error("B non trovato.")
            if st.button("Resetta"): st.session_state.confronto = None; st.rerun()
        else: st.warning("Salva un titolo dallo scanner prima.")

    # --- PAGINA 3: PORTAFOGLIO ---
    elif page == "💼 Portafoglio":
        st.title("💼 Il Tuo Portafoglio")
        with st.expander("➕ Aggiungi", expanded=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            p_cat = c1.selectbox("Cat", list(SOURCES_MAP.keys()))
            p_isin = c2.text_input("ISIN").strip().upper()
            p_nom = c3.number_input("Nominale", 1000, step=1000)
            if c4.button("Add") and p_isin:
                r, i = cerca_nel_database_locale(p_isin, p_cat)
                d = processa_riga_bond(r, i) if r is not None else None
                if d:
                    rn, _ = calcola_rendimenti(d, determina_tasse(d['fonte'], d['desc']))
                    st.session_state.portfolio.append({
                        "ISIN": p_isin, "Desc": d['desc'], "Nominale": p_nom, "Prezzo": d['pr'],
                        "Valore": (p_nom * d['pr'])/100, "Rend%": rn*100, "Cedola": d['ced'], "Duration": d['duration']
                    }); st.success("OK")
                else: st.error("No Data")

        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            tot = df["Valore"].sum()
            df["Peso"] = df["Valore"]/tot
            wn = (df["Rend%"]*df["Peso"]).sum(); wd = (df["Duration"]*df["Peso"]).sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Totale", f"{tot:,.0f}€")
            k2.metric("Rendimento Ponderato", f"{wn:.2f}%")
            k3.metric("Duration Ponderata", f"{wd:.2f}")
            st.dataframe(df[["ISIN", "Desc", "Nominale", "Rend%", "Duration"]], use_container_width=True)
            if st.button("Reset"): st.session_state.portfolio = []; st.rerun()

if st.session_state.logged_in: main_app()
else: login()
