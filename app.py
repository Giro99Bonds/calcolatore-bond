import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Bond Club", page_icon="⛔", layout="centered")

# --- GESTIONE STATO (SESSION STATE) ---
# Serve per ricordare se l'utente ha risposto "Sì" o "No"
if 'access_granted' not in st.session_state:
    st.session_state.access_granted = False

# --- FUNZIONI DI CALCOLO (Backend) ---
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
    guadagno_pct = (rimborso - prezzo) / prezzo
    return guadagno_pct * (360 / giorni)

# ==========================================
#              GATEKEEPER (IL BLOCCO)
# ==========================================
if not st.session_state.access_granted:
    st.markdown("<h1 style='text-align: center; color: red;'>⛔ ALTOLÀ ⛔</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Domanda di sicurezza per accedere:</h3>", unsafe_allow_html=True)
    st.write("")
    st.write("")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>SEI UN TOSSICO? 💊</h2>", unsafe_allow_html=True)
        st.caption("(Di obbligazioni finanziarie, ovviamente...)")
        
        # Pulsanti SÌ / NO
        b1, b2 = st.columns(2)
        if b1.button("SÌ, SONO DIPENDENTE", use_container_width=True):
            st.session_state.access_granted = True
            st.rerun() # Ricarica la pagina per far entrare l'utente
            
        if b2.button("NO, SONO SANO", use_container_width=True):
            st.markdown("<h1 style='text-align: center; font-size: 80px;'>SOLO FATTONI! 😤</h1>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>Torna a investire in conti deposito!</h3>", unsafe_allow_html=True)
            st.stop() # Ferma tutto qui

# ==========================================
#           APP VERA E PROPRIA
# ==========================================
# Se siamo qui, significa che access_granted è True
else:
    # --- INTERFACCIA CALCOLATORE ---
    st.title("💉 Bond Scanner & Yield Calculator")
    st.success("Benvenuto nel club. Ecco la tua dose di rendimenti.")

    # Input ISIN
    col1, col2 = st.columns([3, 1])
    with col1:
        isin_input = st.text_input("Inserisci Codice ISIN", placeholder="Es. IT0005692485").strip().upper()
    with col2:
        st.write("") # Spacer
        st.write("") # Spacer
        cerca_btn = st.button("Dammi il rendimento 🚀", use_container_width=True)

    # --- LOGICA DI RICERCA ---
    if cerca_btn and isin_input:
        
        with st.spinner(f"Sto cercando la roba buona per {isin_input}..."):
            
            # 1. DATABASE FONTI
            sources = [
                {"nome": "BOT (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
                {"nome": "BTP (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
                {"nome": "BUND (Germania)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
                {"nome": "OAT (Francia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
                {"nome": "USA (T-Notes)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
                {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
                {"nome": "EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
                {"nome": "ALTRI EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
                {"nome": "GLOBALI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
            ]

            dati = None
            
            # 2. SCRAPING
            headers = {'User-Agent': 'Mozilla/5.0'}
            for source in sources:
                try:
                    response = requests.get(source["url"], headers=headers, timeout=8)
                    if response.status_code != 200: continue
                    
                    df_list = pd.read_html(response.content, decimal=",", thousands=".")
                    df = None
                    for t in df_list:
                        if 'Codice ISIN' in t.columns:
                            df = t
                            break
                    
                    if df is not None:
                        match = df[df['Codice ISIN'] == isin_input]
                        if not match.empty:
                            riga = match.iloc[0]
                            prezzo = float(str(riga['Prezzo di riferimento']).replace(',', '.'))
                            scadenza_obj = datetime.strptime(str(riga['Data scadenza']), '%Y-%m-%d').date()
                            desc = riga['Descrizione']
                            valuta = "EUR"
                            if 'Divisa' in df.columns: valuta = riga['Divisa']
                            
                            cedola_pct = 0.0
                            freq = source["freq"]
                            if freq > 0:
                                m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                                if m: cedola_pct = float(m.group(1).replace(',', '.'))
                            
                            dati = {"source": source["nome"], "freq": freq, "valuta": valuta,
                                    "prezzo": prezzo, "scadenza": scadenza_obj, 
                                    "cedola": cedola_pct, "desc": desc}
                            break
                except: pass

            if not dati:
                st.error("❌ ISIN non trovato. Forse è roba tagliata male.")
                st.stop()

            # 3. CALCOLI FINANZIARI
            today = date.today()
            np_today = np.datetime64(today, 'D')
            np_valuta = np.busday_offset(np_today, 2, roll='forward')
            data_valuta = np_valuta.astype(date)
            giorni_residui = (dati['scadenza'] - data_valuta).days

            # Flussi
            valore_nominale = 100.0
            tassazione = 0.125
            cf_lordi = [-dati['prezzo']]
            cf_netti = [-dati['prezzo']]
            date_cf = [data_valuta]
            
            # Generazione flussi
            if dati['freq'] > 0 and dati['cedola'] > 0:
                cedola_lorda = dati['cedola'] / dati['freq']
                cedola_netta = cedola_lorda * (1 - tassazione)
                delta = 365 // dati['freq']
                temp_date = dati['scadenza']
                cedole_future = []
                while temp_date > data_valuta:
                    cedole_future.append(temp_date)
                    temp_date = temp_date - timedelta(days=delta)
                cedole_future.sort()
                
                for d in cedole_future:
                    cf_lordi.append(cedola_lorda)
                    cf_netti.append(cedola_netta)
                    date_cf.append(d)
                
                cf_lordi[-1] += valore_nominale
                gain = max(0, valore_nominale - dati['prezzo'])
                rimborso_netto = valore_nominale - (gain * tassazione)
                cf_netti[-1] += (rimborso_netto - cedola_netta)
            else:
                cf_lordi.append(valore_nominale)
                gain = max(0, valore_nominale - dati['prezzo'])
                rimborso_netto = valore_nominale - (gain * tassazione)
                cf_netti.append(rimborso_netto)
                date_cf.append(dati['scadenza'])

            # Risultati Rendimento
            tir_lordo = xirr(cf_lordi, date_cf)
            tir_netto = xirr(cf_netti, date_cf)
            semplice_lordo = rendimento_semplice_360(dati['prezzo'], valore_nominale, giorni_residui)

            # --- OUTPUT GRAFICO ---
            st.success(f"Trovato: {dati['desc']}")
            
            # Metriche in alto
            m1, m2, m3 = st.columns(3)
            m1.metric("Prezzo", f"{dati['prezzo']} {dati['valuta']}")
            m2.metric("Cedola", f"{dati['cedola']}%")
            m3.metric("Scadenza", dati['scadenza'].strftime('%d/%m/%Y'))

            st.divider()

            # Sezione Rendimenti
            st.subheader("📊 Risultati Rendimento")
            
            c1, c2 = st.columns(2)
            if tir_netto:
                c1.info(f"**TIR NETTO (XIRR)**\n# {tir_netto*100:.3f}%")
            else:
                c1.warning("TIR non calcolabile")
                
            if tir_lordo:
                c2.write(f"**TIR LORDO (XIRR):** {tir_lordo*100:.3f}%")
            
            if giorni_residui < 366:
                st.caption(f"Rendimento Semplice (Bancario 360gg): {semplice_lordo*100:.3f}% Lordo")

            # Tabella Dettagli Tecnici
            with st.expander("Vedi dettagli tecnici"):
                st.write(f"**Mercato:** {dati['source']}")
                st.write(f"**Data Valuta (T+2):** {data_valuta}")
                st.write(f"**Giorni residui:** {giorni_residui}")
                if dati['valuta'] != 'EUR':
                    st.warning(f"⚠️ Titolo in {dati['valuta']}. Il rendimento è nella valuta locale.")

                # Tabella Flussi
                df_flussi = pd.DataFrame({
                    "Data": date_cf,
                    "Flusso Netto": cf_netti
                })
                st.dataframe(df_flussi)
                
                # Grafico Flussi
                st.bar_chart(df_flussi.set_index("Data")["Flusso Netto"])
    
    # Pulsante per uscire (opzionale)
    if st.button("Esci dal Club"):
        st.session_state.access_granted = False
        st.rerun()
