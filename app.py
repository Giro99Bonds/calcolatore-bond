import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize
import time
import random

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Club Stealth", page_icon="🕵️", layout="wide")

if 'access_granted' not in st.session_state: st.session_state.access_granted = False
if 'portfolio' not in st.session_state: st.session_state.portfolio = [] 

# --- FUNZIONI MATEMATICHE ---
def xirr(cashflows, dates):
    if not cashflows or not dates: return None
    def xnpv(rate, cashflows, dates):
        if rate <= -1.0: return float('inf')
        t0 = dates[0]
        return sum([cf / ((1 + rate) ** ((d - t0).days / 365.0)) for cf, d in zip(cashflows, dates)])
    try:
        return optimize.newton(lambda r: xnpv(r, cashflows, dates), 0.05)
    except: return None

# --- MOTORE DI SCRAPING AVANZATO (Anti-Block) ---
def get_bond_data_stealth(isin_code, category_key):
    from app_config import SOURCES_MAP # Se preferisci tenere i link separati, o usa la mappa sotto
    
    # Mappa fonti integrata per semplicità
    target_sources = SOURCES_MAP.get(category_key, [])
    if category_key == "🌍 CERCA OVUNQUE (Lento!)":
        target_sources = [s for sublist in SOURCES_MAP.values() for s in sublist]

    # Lista di User-Agent per ruotare l'identità
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]

    session = requests.Session()
    
    for source in target_sources:
        try:
            # Simula un comportamento umano: aspetta un istante casuale
            time.sleep(random.uniform(0.5, 1.5))
            
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3',
                'Referer': 'https://www.google.com/',
                'DNT': '1'
            }

            response = session.get(source["url"], headers=headers, timeout=12)
            
            if response.status_code == 403:
                st.error(f"🚫 Il sito ha bloccato Streamlit (Errore 403) su {source['nome']}. Riprova tra poco.")
                continue
            
            if response.status_code != 200: continue
            
            # Parsing tabelle
            df_list = pd.read_html(response.text, decimal=",", thousands=".")
            
            for df in df_list:
                # Ricerca colonne flessibile
                col_isin = next((c for c in df.columns if 'isin' in str(c).lower() or 'codice' in str(c).lower()), None)
                
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin_code, na=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        
                        # Estrazione intelligente
                        col_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'price', 'last'])), None)
                        col_scad = next((c for c in df.columns if any(k in str(c).lower() for k in ['scadenza', 'maturity', 'date'])), None)
                        col_desc = next((c for c in df.columns if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
                        
                        pr = float(str(row[col_pr]).replace(',', '.'))
                        scad_str = str(row[col_scad])
                        try: scad = datetime.strptime(scad_str, '%Y-%m-%d').date()
                        except: scad = datetime.strptime(scad_str, '%d/%m/%Y').date()
                        
                        desc = str(row[col_desc])
                        ced = 0.0
                        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                        if m: ced = float(m.group(1).replace(',', '.'))
                        
                        return {"source": source["nome"], "freq": source["freq"], "prezzo": pr, "scadenza": scad, "cedola": ced, "desc": desc}
        except Exception as e:
            continue
    return None

# --- RE-INSERISCO LA MAPPA FONTI (Spostala qui se l'hai tolta) ---
SOURCES_MAP = {
    "🇮🇹 BTP & Italia": [
        {"nome": "BTP (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0}
    ],
    # ... Aggiungi qui le altre 26 fonti che abbiamo visto prima ...
}

# ==========================================
#              INTERFACCIA
# ==========================================
# (Mantieni la logica del Gatekeeper e delle Pagine viste nel messaggio precedente)
