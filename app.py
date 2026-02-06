import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize
import time
import random
import plotly.graph_objects as go

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="⚖️", layout="wide")

# --- CREDENZIALI DI ACCESSO ---
# Modifica qui la password che vuoi usare
SEGRETO_UTENTE = "admin"
SEGRETO_PASSWORD = "password123"

# --- MAPPA FONTI (Organizzata per Categorie) ---
SOURCES_MAP = {
    "🇮🇹 Titoli di Stato Italiani (BTP, BOT)": [
        {"nome": "BTP ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT (Buoni Tesoro)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Obbligazioni Bancarie (Senior)": [
        {"nome": "BANCHE ITA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇪🇺 Banche Estere & Globali": [
        {"nome": "BANCHE EUROPEE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE GENERICO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=banche&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Corporate (Aziende, Auto, Energy)": [
        {"nome": "CORPORATE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Stati Esteri (USA, Bund, EU)": [
        {"nome": "USA TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Speciali (Sub, Zero Coupon, Callable)": [
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHISSIMI (25Y+)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI DI CALCOLO ---
def get_bond_data_protected(isin, category):
    # CACHING: Se abbiamo cercato questo URL meno di 5 min fa, usiamo la memoria
    @st.cache_data(ttl=300, show_spinner=False)
    def download_url(url):
        # Lista User-Agent per mascherare lo script
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36'
        ]
        headers = {'User-Agent': random.choice(user_agents)}
        # Ritardo casuale per sembrare umano
        time.sleep(random.uniform(0.5, 1.5))
        r = requests.get(url, headers=headers, timeout=15)
        return r

    target_list = SOURCES_MAP.get(category, [])
    
    for s in target_list:
        try:
            r = download_url(s['url'])
            if r.status_code != 200: continue
            
            df_list = pd.read_html(r.text, decimal=",", thousands=".")
            for df in df_list:
                col_isin = next((c for c in df.columns if any(k in str(c).lower() for k in ['isin', 'codice'])), None)
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin, na=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
                        c_sc = next((c for c in df.columns if any(k in str(c).lower() for k in ['scadenza', 'data'])), None)
                        c_de = next((c for c in df.columns if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
                        
                        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
                        sc_str = str(row[c_sc])
                        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
                        except: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
                        
                        desc = str(row[c_de])
                        ced = 0.0
                        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                        if m: ced = float(m.group(1).replace(',', '.'))
                        
                        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": s['freq'], "fonte": s['nome']}
        except: continue
    return None

# --- GESTIONE LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.title("🔒 Accesso Riservato")
    with st.form("login_form"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submit = st.form_submit_button("Entra")
        
        if submit:
            if user == SEGRETO_UTENTE and pwd == SEGRETO_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Credenziali non valide.")

def main_app():
    st.title("🎓 Bond Research Terminal")
    st.markdown("---")
    
    # DISCLAIMER LEGALE
    with st.expander("⚠️ DISCLAIMER LEGALE (Importante)", expanded=False):
        st.warning("""
        **TERMINI DI UTILIZZO E LIMITAZIONE DI RESPONSABILITÀ**
        
        1. **Finalità Esclusivamente Didattiche:** Questo software è sviluppato e fornito esclusivamente per scopi di ricerca accademica, studio e sperimentazione informatica. Non costituisce in alcun modo consulenza finanziaria, invito al risparmio pubblico o sollecitazione all'investimento.
        
        2. **Nessuna Garanzia sui Dati:** I dati mostrati sono ottenuti tramite tecniche di web scraping da fonti pubbliche terze. Non si garantisce l'accuratezza, la tempestività o la completezza delle informazioni. I prezzi e i rendimenti potrebbero essere differiti o errati.
        
        3. **Esonero Responsabilità:** L'autore del software e i gestori della piattaforma declinano ogni responsabilità per eventuali perdite finanziarie, danni diretti o indiretti derivanti dall'utilizzo di queste informazioni. Qualsiasi decisione di investimento è presa dall'utente a proprio esclusivo rischio.
        
        4. **Utilizzo Etico:** L'utente si impegna a utilizzare questo strumento in modo etico, evitando di sovraccaricare i server delle fonti dati (le protezioni anti-ban sono incluse ma non infallibili).
        
        *Continuando l'utilizzo, accetti integralmente queste condizioni.*
        """)

    # INTERFACCIA RICERCA
    col_cat, col_isin, col_tax, col_btn = st.columns([2, 1.5, 1, 1])

    with col_cat:
        cat_choice = st.selectbox("1. Categoria Mercato", options=list(SOURCES_MAP.keys()))
    
    with col_isin:
        isin_input = st.text_input("2. Codice ISIN", placeholder="Es: IT0005566408").strip().upper()
    
    with col_tax:
        is_gov = "Stato" in cat_choice or "Stati" in cat_choice
        tax_choice = st.radio("3. Tassa", [12.5, 26.0], index=0 if is_gov else 1, horizontal=True)

    with col_btn:
        st.write("")
        trigger = st.button("ANALIZZA 🚀", use_container_width=True)

    if trigger and isin_input:
        with st.spinner("Connessione sicura ai database in corso..."):
            res = get_bond_data_protected(isin_input, cat_choice)
            
            if res:
                # Calcoli Finanziari
                oggi = date.today()
                valuta = oggi + timedelta(days=2)
                giorni_res = (res['sc'] - valuta).days
                anni = giorni_res / 365.25
                t_val = tax_choice / 100
                
                # Rendimento Semplice (Yield to Maturity approx)
                rend_n = (((100 - res['pr'])*(1-t_val) + (res['ced'] * anni * (1-t_val))) / res['pr']) / anni
                rend_l = (((100 - res['pr']) + (res['ced'] * anni)) / res['pr']) / anni

                st.success(f"Analisi completata: **{res['desc']}**")
                
                # Dashboard Metriche
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Prezzo Attuale", f"{res['pr']}€")
                k2.metric("Rendimento Netto", f"{rend_n*100:.2f}%", delta_color="normal")
                k3.metric("Cedola Lorda", f"{res['ced']}%")
                k4.metric("Scadenza", res['sc'].strftime('%d/%m/%Y'))

                st.caption(f"Fonte dati: {res['fonte']} | Frequenza cedola: {'Annuale/Semestrale' if res['freq']>0 else 'Zero Coupon'}")

                # Grafico Plotly
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=['Prezzo Acquisto', 'Rendimento Netto %', 'Rendimento Lordo %'],
                    y=[res['pr'], rend_n*100, rend_l*100],
                    marker_color=['#1f77b4', '#2ca02c', '#d62728'],
                    text=[f"{res['pr']}€", f"{rend_n*100:.2f}%", f"{rend_l*100:.2f}%"],
                    textposition='auto',
                ))
                fig.update_layout(title="Analisi Redditività", template="plotly_dark", height=400)
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.error("Titolo non trovato.")
                st.info("Suggerimento: Verifica di aver selezionato la categoria corretta (es. 'Titoli di Stato' per i BTP).")
    
    # Tasto Logout
    st.divider()
    if st.button("Esci / Logout"):
        st.session_state.logged_in = False
        st.rerun()

# --- AVVIO APP ---
if st.session_state.logged_in:
    main_app()
else:
    login()
