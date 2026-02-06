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

st.set_page_config(page_title="Academic Bond Research", page_icon="🎓", layout="wide")

# Mappa completa 28 Database (Suddivisi per non sovraccaricare)
SOURCES_MAP = {
    "🇮🇹 Italia & TDS": [
        {"nome": "BTP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Banche Italia": [
        {"nome": "BANCHE ITA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇪🇺 Banche EU & USA": [
        {"nome": "BANCHE EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE GEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=banche&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Corporate & Settoriali": [
        {"nome": "CORP ITA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP GEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Stati Estero": [
        {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EU MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GLOBAL", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Speciali": [
        {"nome": "ZERO COUP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CEDOLA 0", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cedolazero&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "SUB", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

def get_bond_data_academic(isin, category):
    # Stealth Headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9'
    }
    target_list = SOURCES_MAP[category]
    
    for s in target_list:
        try:
            # Random delay per simulare comportamento umano
            time.sleep(random.uniform(0.4, 0.8))
            r = requests.get(s['url'], headers=headers, timeout=12)
            if r.status_code != 200: continue
            
            df_list = pd.read_html(r.text, decimal=",", thousands=".")
            for df in df_list:
                col_isin = next((c for c in df.columns if any(k in str(c).lower() for k in ['isin', 'codice'])), None)
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin, na=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
                        c_sc = next((c for c in df.columns if any(k in str(c).lower() for k in ['scadenza', 'maturity', 'data'])), None)
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

# UI
st.title("🎓 Bond Research Console")
st.caption("Strumento per studi accademici e analisi di mercato obbligazionario.")

if 'access' not in st.session_state: st.session_state.access = False
if not st.session_state.access:
    if st.button("ACCEDI ALLA RICERCA"): st.session_state.access = True; st.rerun()
else:
    with st.sidebar:
        cat = st.selectbox("Categoria Database", options=list(SOURCES_MAP.keys()))
        isin = st.text_input("Inserisci ISIN").strip().upper()
        tax = st.radio("Tassazione (%)", [12.5, 26.0])
        btn = st.button("ANALIZZA 🚀")

    if btn and isin:
        with st.spinner("Scansione database in corso (Modalità Stealth)..."):
            d = get_bond_data_academic(isin, cat)
            if d:
                # Calcoli rapidi
                oggi = date.today()
                valuta = oggi + timedelta(days=2)
                giorni = (d['sc'] - valuta).days
                anni = giorni / 365.25
                tax_val = tax / 100
                
                rend_l = (((100 - d['pr']) + (d['ced'] * anni)) / d['pr']) / anni
                rend_n = (((100 - d['pr'])*(1-tax_val) + (d['ced'] * anni * (1-tax_val))) / d['pr']) / anni

                st.subheader(f"📄 {d['desc']}")
                
                cols = st.columns(4)
                cols[0].metric("Prezzo", f"{d['pr']}€")
                cols[1].metric("Rend. Netto", f"{rend_n*100:.2f}%")
                cols[2].metric("Cedola", f"{d['ced']}%")
                cols[3].metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                
                # Plotly grafico accademico
                fig = go.Figure(go.Scatter(
                    x=[0, anni], y=[d['pr'], 100],
                    mode='lines+markers+text',
                    text=['Acquisto', 'Rimborso'],
                    textposition="top center",
                    line=dict(color='#00CC96', width=4)
                ))
                fig.update_layout(title="Traiettoria del Capitale verso la Scadenza", template="plotly_dark", xaxis_title="Anni Residui", yaxis_title="Valore")
                st.plotly_chart(fig)
            else:
                st.error("Titolo non trovato. Prova un'altra categoria.")
