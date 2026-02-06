import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Club", page_icon="🏦")

# Mappa Fonti Integrata
SOURCES_MAP = {
    "🇮🇹 Italia": [
        {"nome": "BTP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0}
    ],
    "🏦 Banche & Corp": [
        {"nome": "BANCHE ITA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE ITA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Estero": [
        {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI ---
def xirr(cashflows, dates):
    if not cashflows or not dates: return None
    def xnpv(rate, cashflows, dates):
        if rate <= -1.0: return float('inf')
        t0 = dates[0]
        return sum([cf / ((1 + rate) ** ((d - t0).days / 365.0)) for cf, d in zip(cashflows, dates)])
    try:
        return optimize.newton(lambda r: xnpv(r, cashflows, dates), 0.05)
    except: return None

def get_bond_data(isin_code, category):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    target_sources = SOURCES_MAP.get(category, [])
    
    for source in target_sources:
        try:
            r = requests.get(source["url"], headers=headers, timeout=10)
            if r.status_code != 200: continue
            df_list = pd.read_html(r.text, decimal=",", thousands=".")
            for df in df_list:
                col_isin = next((c for c in df.columns if 'isin' in str(c).lower() or 'codice' in str(c).lower()), None)
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin_code, na=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        col_pr = next((c for c in df.columns if 'prezzo' in str(c).lower()), None)
                        col_scad = next((c for c in df.columns if 'scadenza' in str(c).lower()), None)
                        col_desc = next((c for c in df.columns if 'descrizione' in str(c).lower()), None)
                        
                        pr = float(str(row[col_pr]).replace(',', '.'))
                        scad_str = str(row[col_scad])
                        try: scad = datetime.strptime(scad_str, '%Y-%m-%d').date()
                        except: scad = datetime.strptime(scad_str, '%d/%m/%Y').date()
                        
                        desc = str(row[col_desc])
                        ced = 0.0
                        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                        if m: ced = float(m.group(1).replace(',', '.'))
                        
                        return {"source": source["nome"], "freq": source["freq"], "prezzo": pr, "scadenza": scad, "cedola": ced, "desc": desc}
        except: continue
    return None

# --- UI ---
st.title("🏛️ Bond Club Console")

if 'access' not in st.session_state: st.session_state.access = False

if not st.session_state.access:
    if st.button("ENTRA NEL CLUB"):
        st.session_state.access = True
        st.rerun()
else:
    cat = st.selectbox("Seleziona Mercato", options=list(SOURCES_MAP.keys()))
    isin = st.text_input("Inserisci ISIN").strip().upper()
    
    if st.button("ANALIZZA") and isin:
        with st.spinner("Ricerca in corso..."):
            d = get_bond_data(isin, cat)
            if d:
                st.success(f"Trovato: {d['desc']}")
                st.write(f"Prezzo: {d['prezzo']} | Cedola: {d['cedola']}% | Scadenza: {d[ 'scadenza']}")
            else:
                st.error("Titolo non trovato in questa categoria.")
