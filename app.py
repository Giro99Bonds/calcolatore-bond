import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Scanner", page_icon="📈")

# --- FUNZIONI ---
def xirr(cashflows, dates):
    if not cashflows or not dates: return None
    def xnpv(rate, cashflows, dates):
        if rate <= -1.0: return float('inf')
        t0 = dates[0]
        return sum([cf / ((1 + rate) ** ((d - t0).days / 365.0)) for cf, d in zip(cashflows, dates)])
    try:
        return optimize.newton(lambda r: xnpv(r, cashflows, dates), 0.05)
    except:
        return None

def rendimento_semplice_360(prezzo, rimborso, giorni):
    if giorni <= 0: return 0
    return ((rimborso - prezzo) / prezzo) * (360 / giorni)

# --- APP ---
st.title("🔎 Calcolatore Bond Universale")
st.write("Inserisci un ISIN (BTP, BOT, Estero) e calcola il rendimento netto reale.")

isin_input = st.text_input("Inserisci ISIN", "IT0005692485").strip().upper()
if st.button("Analizza Titolo"):
    
    with st.spinner("Cerco nei database internazionali..."):
        sources = [
            {"nome": "BOT (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
            {"nome": "BTP (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
            {"nome": "BUND (Germania)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
            {"nome": "OAT (Francia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
            {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
            {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
            {"nome": "EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
            {"nome": "ALTRI EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
            {"nome": "GLOBALI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
        ]
        
        dati = None
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for source in sources:
            try:
                r = requests.get(source["url"], headers=headers, timeout=5)
                if r.status_code != 200: continue
                df_list = pd.read_html(r.content, decimal=",", thousands=".")
                for df in df_list:
                    if 'Codice ISIN' in df.columns:
                        match = df[df['Codice ISIN'] == isin_input]
                        if not match.empty:
                            row = match.iloc[0]
                            pr = float(str(row['Prezzo di riferimento']).replace(',', '.'))
                            scad = datetime.strptime(str(row['Data scadenza']), '%Y-%m-%d').date()
                            desc = row['Descrizione']
                            val = row['Divisa'] if 'Divisa' in df.columns else "EUR"
                            ced = 0.0
                            if source["freq"] > 0:
                                m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                                if m: ced = float(m.group(1).replace(',', '.'))
                            
                            dati = {"source": source["nome"], "freq": source["freq"], "valuta": val,
                                    "prezzo": pr, "scadenza": scad, "cedola": ced, "desc": desc}
                            break
                if dati: break
            except: pass
            
        if not dati:
            st.error("ISIN non trovato!")
            st.stop()
            
        # CALCOLI
        today = date.today()
        # Fix data numpy
        np_today = np.datetime64(today, 'D')
        data_valuta = np.busday_offset(np_today, 2, roll='forward').astype(date)
        giorni = (dati['scadenza'] - data_valuta).days
        
        cf_lordi = [-dati['prezzo']]
        cf_netti = [-dati['prezzo']]
        dates = [data_valuta]
        tass = 0.125
        nominale = 100.0
        
        if dati['freq'] > 0 and dati['cedola'] > 0:
            c_lorda = dati['cedola']/dati['freq']
            c_netta = c_lorda * (1-tass)
            curr = dati['scadenza']
            delta = 365 // dati['freq']
            c_future = []
            while curr > data_valuta:
                c_future.append(curr)
                curr -= timedelta(days=delta)
            c_future.sort()
            for d in c_future:
                cf_lordi.append(c_lorda)
                cf_netti.append(c_netta)
                dates.append(d)
            cf_lordi[-1] += nominale
            gain = max(0, nominale - dati['prezzo'])
            cf_netti[-1] += (nominale - (gain*tass) - c_netta)
        else:
            cf_lordi.append(nominale)
            gain = max(0, nominale - dati['prezzo'])
            cf_netti.append(nominale - (gain*tass))
            dates.append(dati['scadenza'])
            
        tir_lordo = xirr(cf_lordi, dates)
        tir_netto = xirr(cf_netti, dates)
        semplice = rendimento_semplice_360(dati['prezzo'], nominale, giorni)
        
        st.success(f"Trovato: {dati['desc']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Prezzo", f"{dati['prezzo']}")
        c2.metric("Cedola", f"{dati['cedola']}%")
        c3.metric("Scadenza", f"{dati['scadenza']}")
        
        st.divider()
        k1, k2 = st.columns(2)
        if tir_netto: k1.info(f"**TIR NETTO: {tir_netto*100:.3f}%**")
        if tir_lordo: k2.write(f"TIR LORDO: {tir_lordo*100:.3f}%")
        if giorni < 366: st.caption(f"Semplice (360gg): {semplice*100:.3f}%")
