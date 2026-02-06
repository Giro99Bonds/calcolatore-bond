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
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide")

# CREDENZIALI
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# --- NUOVA MAPPA FONTI (Logica "SimpleTools") ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI (Stati: Italia, Germania, USA...)": [
        {"nome": "BTP ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI (Banche & Subordinate)": [
        {"nome": "BANCHE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE (Aziende Industriali)": [
        {"nome": "CORPORATE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE (Auto)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY (Petrolio)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM (Tlc)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI (Zero Coupon, Green, ecc.)": [
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHISSIMI (25Y+)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI BACKEND (Caching & Anti-Ban) ---
def get_bond_data_protected(isin, category):
    @st.cache_data(ttl=300, show_spinner=False)
    def download_url(url):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/119.0.0.0 Safari/537.36'
        ]
        time.sleep(random.uniform(0.4, 1.2)) # Ritardo per sembrare umani
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
            else: st.error("Errore")

def main_app():
    st.title("🏛️ Bond Research Terminal")
    st.caption("Strumento di analisi obbligazionaria accademica.")
    st.markdown("---")

    # --- LEGENDA CHIARA ---
    st.subheader("📍 Dove devo cercare?")
    st.info("Il sistema divide i 28 database in 4 Macro-Aree per velocità e sicurezza:")
    
    col_leg1, col_leg2, col_leg3, col_leg4 = st.columns(4)
    with col_leg1:
        st.markdown("""
        ### 🏛️ GOVERNATIVI
        **Tutti gli Stati Sovrani**
        * BTP, BOT (Italia)
        * Bund (Germania)
        * OAT (Francia)
        * Treasury (USA)
        * Romania, Europa...
        """)
    with col_leg2:
        st.markdown("""
        ### 🏦 FINANZIARI
        **Banche e Assicurazioni**
        * Intesa, UniCredit
        * Goldman, Deutsche Bank
        * Banche USA/UE
        * *Include Subordinate*
        """)
    with col_leg3:
        st.markdown("""
        ### 🏭 CORPORATE
        **Aziende Industriali**
        * Eni, Enel, Stellantis
        * Telecom, Ferrari
        * Volkswagen, Renault
        * Settore Energia
        """)
    with col_leg4:
        st.markdown("""
        ### 💎 SPECIALI
        **Strutture Particolari**
        * Zero Coupon (No cedola)
        * Green Bonds
        * Callable
        * Scadenze lunghissime
        """)

    st.markdown("---")

    # --- INTERFACCIA RICERCA ---
    col_input, col_res = st.columns([1, 2])

    with col_input:
        st.markdown("### 🔎 Impostazioni")
        # Menu con le nuove categorie pulite
        cat = st.selectbox("1. Categoria (Vedi sopra)", list(SOURCES_MAP.keys()))
        isin = st.text_input("2. Codice ISIN", placeholder="Es. DE000...").strip().upper()
        
        # Logica Tasse Smart
        is_gov = "GOVERNATIVI" in cat
        tax = st.radio("3. Tassazione", [12.5, 26.0], index=0 if is_gov else 1, horizontal=True)
        
        btn = st.button("ANALIZZA TITOLO 🚀", use_container_width=True)
        st.caption("⚠️ **Disclaimer:** Dati a scopo didattico. Non è consulenza finanziaria.")

    with col_res:
        if btn and isin:
            with st.spinner("Connessione ai database selezionati..."):
                d = get_bond_data_protected(isin, cat)
                
                if d:
                    # Calcoli
                    oggi = date.today()
                    valuta = oggi + timedelta(days=2)
                    anni = (d['sc'] - valuta).days / 365.25
                    t_val = tax / 100
                    
                    rend_n = (((100 - d['pr'])*(1-t_val) + (d['ced'] * anni * (1-t_val))) / d['pr']) / anni
                    rend_l = (((100 - d['pr']) + (d['ced'] * anni)) / d['pr']) / anni
                    
                    st.success(f"✅ Trovato: **{d['desc']}**")
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Prezzo", f"{d['pr']}€")
                    k2.metric("Rendimento Netto", f"{rend_n*100:.2f}%", delta_color="normal")
                    k3.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                    
                    # Grafico
                    fig = go.Figure(go.Bar(
                        x=[rend_n*100, rend_l*100, d['ced']],
                        y=['Rend. Netto', 'Rend. Lordo', 'Cedola'],
                        orientation='h',
                        marker_color=['#00CC96', '#EF553B', '#636EFA'],
                        text=[f"{rend_n*100:.2f}%", f"{rend_l*100:.2f}%", f"{d['ced']}%"],
                        textposition='auto'
                    ))
                    fig.update_layout(title="Analisi Redditività", height=300, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig, use_container_width=True)

                    st.info(f"🔎 Fonte: {d['fonte']} | Tipo: {cat.split(' ')[1]}")

                else:
                    st.error("❌ Titolo non trovato.")
                    st.warning(f"Hai cercato in **{cat}**. Sei sicuro che l'ISIN appartenga a questa categoria? Controlla la legenda sopra.")
        else:
            st.info("👈 Inserisci ISIN e Categoria per iniziare.")

    # Logout
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

if st.session_state.logged_in: main_app()
else: login()
