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

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="🧭", layout="wide")

# CREDENZIALI PERSONALIZZATE
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# --- MAPPA FONTI ---
SOURCES_MAP = {
    "🇮🇹 Titoli di Stato (BTP, BOT)": [
        {"nome": "BTP ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Banche Italiane (Intesa, UniCredit)": [
        {"nome": "BANCHE ITA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Aziende (Eni, Auto, Telecom)": [
        {"nome": "CORPORATE ITA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE GEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Estero (USA, Goldman, Bund)": [
        {"nome": "USA TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BUND", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Speciali (Sub, Zero, Green)": [
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI BACKEND ---
def get_bond_data_protected(isin, category):
    @st.cache_data(ttl=300, show_spinner=False)
    def download_url(url):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/119.0.0.0 Safari/537.36'
        ]
        time.sleep(random.uniform(0.4, 1.2)) # Ritardo umano
        return requests.get(url, headers={'User-Agent': random.choice(user_agents)}, timeout=15)

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
                        c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
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

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

def login():
    st.title("🔐 Accesso Ricerca")
    with st.form("login"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entra"):
            if u == SEGRETO_UTENTE and p == SEGRETO_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("Credenziali non valide")

def main_app():
    st.title("🧭 Bond Research Compass")
    st.caption("Strumento di analisi comparativa per investitori privati.")
    st.markdown("---")

    # --- LEGENDA VISIVA ---
    st.subheader("💡 Come scegliere la categoria giusta?")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.info("**🇮🇹 Titoli di Stato**\n\nScegli se cerchi:\n* BTP / BTP Valore\n* BOT / CCT\n* *ISIN inizia con IT*")
    with c2:
        st.info("**🏦 Banche Italiane**\n\nScegli se cerchi:\n* Intesa Sanpaolo\n* UniCredit\n* Mediobanca")
    with c3:
        st.info("**🏭 Aziende**\n\nScegli se cerchi:\n* Eni, Enel, Ferrari\n* Telecom, Stellantis\n* *Corporate Bond*")
    with c4:
        st.info("**🌍 Estero / Mix**\n\nScegli se cerchi:\n* USA / Germania\n* Goldman / Deutsche\n* *ISIN stranieri*")

    st.markdown("---")

    # --- INTERFACCIA DI RICERCA ---
    col_input, col_res = st.columns([1, 2])

    with col_input:
        st.markdown("### 🔎 Parametri Ricerca")
        cat = st.selectbox("1. Categoria (Vedi legenda sopra)", list(SOURCES_MAP.keys()))
        isin = st.text_input("2. Codice ISIN", placeholder="Es. IT0005566408").strip().upper()
        
        # Auto-Set Tasse
        idx_tax = 0 if "Stato" in cat else 1
        tax = st.radio("3. Tassazione", [12.5, 26.0], index=idx_tax, horizontal=True)
        
        btn = st.button("ANALIZZA TITOLO 🚀", use_container_width=True)
        
        # Disclaimer compatto
        st.caption("⚠️ **Disclaimer:** Dati a scopo didattico. Non è consulenza finanziaria. L'autore non è responsabile per inesattezze.")

    with col_res:
        if btn and isin:
            with st.spinner("Connessione ai mercati in corso..."):
                d = get_bond_data_protected(isin, cat)
                
                if d:
                    # Calcoli
                    oggi = date.today()
                    valuta = oggi + timedelta(days=2)
                    anni = (d['sc'] - valuta).days / 365.25
                    t_val = tax / 100
                    
                    rend_n = (((100 - d['pr'])*(1-t_val) + (d['ced'] * anni * (1-t_val))) / d['pr']) / anni
                    rend_l = (((100 - d['pr']) + (d['ced'] * anni)) / d['pr']) / anni
                    
                    # VISUALIZZAZIONE RISULTATO
                    st.success(f"✅ Trovato: **{d['desc']}**")
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Prezzo", f"{d['pr']}€")
                    k2.metric("Rendimento Netto", f"{rend_n*100:.2f}%", delta_color="normal")
                    k3.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                    
                    # Grafico a barre orizzontali
                    fig = go.Figure(go.Bar(
                        x=[rend_n*100, rend_l*100, d['ced']],
                        y=['Rend. Netto', 'Rend. Lordo', 'Cedola'],
                        orientation='h',
                        marker_color=['#00CC96', '#EF553B', '#636EFA'],
                        text=[f"{rend_n*100:.2f}%", f"{rend_l*100:.2f}%", f"{d['ced']}%"],
                        textposition='auto'
                    ))
                    fig.update_layout(title="Analisi Rendimento", height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)

                    st.info(f"🔎 Fonte: {d['fonte']} | Frequenza: {'Annuale/Semestrale' if d['freq']>0 else 'Zero Coupon'}")

                else:
                    st.error("❌ Titolo non trovato.")
                    st.markdown("""
                    **Possibili cause:**
                    1. Hai scelto la **categoria sbagliata**? (Controlla la legenda in alto)
                    2. L'ISIN è corretto?
                    3. Il titolo è appena stato emesso? (Riprova domani)
                    """)
        else:
            st.info("👈 Inserisci i dati a sinistra per vedere l'analisi qui.")

    # Logout
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

if st.session_state.logged_in: main_app()
else: login()
