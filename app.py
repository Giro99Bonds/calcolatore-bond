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
st.set_page_config(page_title="Bond Research Pro", page_icon="🎓", layout="wide")

# --- MAPPA FONTI COMPLETA ---
SOURCES_MAP = {
    "🇮🇹 Titoli di Stato Italiani (BTP, BOT, Valore)": [
        {"nome": "BTP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Banche Italiane (Intesa, UniCredit, Mediobanca)": [
        {"nome": "BANCHE ITA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇪🇺 Banche Estere (USA, Europa, Corporate)": [
        {"nome": "BANCHE EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE GEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=banche&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Aziende (Eni, Stellantis, Telecom, Auto)": [
        {"nome": "CORP ITA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP GEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Stati Esteri (USA, Bund, Romania)": [
        {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EU MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Speciali (Sub, Callable, Zero Coupon)": [
        {"nome": "ZERO COUP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "SUB", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI DI SUPPORTO ---
def get_bond_data_safe(isin, category):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    target_list = SOURCES_MAP.get(category, [])
    for s in target_list:
        try:
            time.sleep(random.uniform(0.3, 0.6))
            r = requests.get(s['url'], headers=headers, timeout=12)
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
                        pr = float(str(row[c_pr]).replace(',', '.'))
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

# --- UI PRINCIPALE ---
st.title("🎓 Bond Research Console")
st.markdown("---")

if 'access' not in st.session_state: st.session_state.access = False
if not st.session_state.access:
    if st.button("ACCEDI AL SISTEMA"): st.session_state.access = True; st.rerun()
else:
    # 📖 LEGENDA UX
    with st.expander("📖 LEGENDA: Guida alla scelta della categoria", expanded=False):
        st.write("""
        | Prefisso ISIN | Tipo Titolo | Categoria da Selezionare |
        | :--- | :--- | :--- |
        | **IT...** | BTP, BOT, Valore | `🇮🇹 Titoli di Stato Italiani` |
        | **IT... / XS...** | Intesa, UniCredit | `🏦 Banche Italiane` |
        | **US... / XS...** | Goldman, Eni, Stellantis | `🇪🇺 Banche Estere` o `🏭 Aziende` |
        | **RO... / DE...** | Romania, Germania | `🌍 Stati Esteri` |
        """)

    # 🔍 INPUT DI RICERCA
    col_cat, col_isin, col_tax, col_btn = st.columns([2, 1.5, 1, 1])

    with col_cat:
        cat_choice = st.selectbox("1. Seleziona Mercato", options=list(SOURCES_MAP.keys()))
    
    with col_isin:
        isin_input = st.text_input("2. Codice ISIN", placeholder="Es: IT0005566408").strip().upper()
    
    with col_tax:
        # Auto-tassazione intelligente
        is_gov = "Stato" in cat_choice or "Stati" in cat_choice
        tax_choice = st.radio("3. Tassa", [12.5, 26.0], index=0 if is_gov else 1, horizontal=True)

    with col_btn:
        st.write("")
        trigger = st.button("ANALIZZA 🚀", use_container_width=True)

    if trigger and isin_input:
        with st.spinner("Scansione database in corso..."):
            res = get_bond_data_safe(isin_input, cat_choice)
            if res:
                # Calcoli rapidi per la ricerca
                oggi = date.today()
                valuta = oggi + timedelta(days=2)
                anni = (res['sc'] - valuta).days / 365.25
                t_val = tax_choice / 100
                rend_n = (((100 - res['pr'])*(1-t_val) + (res['ced'] * anni * (1-t_val))) / res['pr']) / anni
                
                st.success(f"Analisi completata per: {res['desc']}")
                
                # DASHBOARD RISULTATI
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Prezzo", f"{res['pr']}€")
                m2.metric("Rend. Netto", f"{rend_n*100:.2f}%")
                m3.metric("Cedola Lorda", f"{res['ced']}%")
                m4.metric("Scadenza", res['sc'].strftime('%d/%m/%Y'))
                
                # GRAFICO TRAIETTORIA
                fig = go.Figure(go.Scatter(
                    x=[0, anni], y=[res['pr'], 100],
                    mode='lines+markers+text',
                    text=['Prezzo Oggi', 'Rimborso (100)'],
                    textposition="bottom right",
                    line=dict(color='#00CC96', width=3)
                ))
                fig.update_layout(title="Traiettoria del Capitale", template="plotly_dark", xaxis_title="Anni alla scadenza", yaxis_title="Valore")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Titolo non trovato. Controlla ISIN o cambia categoria.")
