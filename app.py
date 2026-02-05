import streamlit as st
import pandas as pd
import requests
import datetime
import matplotlib.pyplot as plt
from scipy import optimize

# Configurazione Pagina
st.set_page_config(page_title="Bond Analyzer", layout="wide")

# ==============================================================================
# 1. LINK AI MONITOR
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 2. MOTORE SCARICAMENTO DATI (CACHED)
# ==============================================================================
@st.cache_data(ttl=3600) # La cache dura 1 ora per non scaricare sempre
def scarica_database():
    db = pd.DataFrame()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Barra di progresso
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_links = len(PAGINE_DA_ANALIZZARE)
    
    for i, url in enumerate(PAGINE_DA_ANALIZZARE):
        status_text.text(f"Scaricamento dati da: {url.split('=')[1]}...")
        try:
            r = requests.get(url, headers=headers, timeout=10)
            tabelle = pd.read_html(r.text, thousands='.', decimal=',')
            if tabelle:
                df = max(tabelle, key=len)
                df.columns = df.columns.str.strip()
                if 'ISIN' in df.columns:
                    db = pd.concat([db, df], ignore_index=True)
        except Exception as e:
            continue
        progress_bar.progress((i + 1) / total_links)
            
    status_text.empty()
    progress_bar.empty()
    return db

# ==============================================================================
# 3. ANALISI FINANZIARIA
# ==============================================================================
def analizza_bond(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000
    oggi = datetime.date.today()
    
    flussi = []
    date_f = []
    tipi = []
    
    # Uscita Iniziale
    investimento = -nominale * (prezzo/100)
    flussi.append(investimento)
    date_f.append(oggi)
    tipi.append("Acquisto")
    
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    cursor = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            rimborso_netto = nominale - tassa_gain
            flussi.append(cedola_netta + rimborso_netto)
            date_f.append(dt)
            tipi.append("Rimborso + Cedola")
            break
        else:
            flussi.append(cedola_netta)
            date_f.append(dt)
            tipi.append("Cedola")

    # XIRR
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0
    
    rend_netto = xirr(flussi, date_f)
    
    # Duration
    numeratore = 0
    denominatore = 0
    for i in range(1, len(flussi)):
        t_anni = (date_f[i] - oggi).days / 365.25
        valore_att = flussi[i] / ((1 + rend_netto)**t_anni)
        numeratore += t_anni * valore_att
        denominatore += valore_att
        
    duration = numeratore / denominatore if denominatore != 0 else 0

    df_flussi = pd.DataFrame({
        "Data": date_f,
        "Tipo": tipi,
        "Importo": [round(f, 2) for f in flussi]
    })
    
    return {
        "rendimento": rend_netto * 100,
        "duration": duration,
        "profitto": sum(flussi),
        "df_flussi": df_flussi
    }

# ==============================================================================
# 4. INTERFACCIA STREAMLIT
# ==============================================================================
st.title("🕵️‍♂️ Bond Analyzer Pro")
st.markdown("Inserisci l'ISIN e ottieni analisi, flussi di cassa e grafici.")

# Scarica DB
with st.spinner('Aggiornamento database obbligazioni in corso...'):
    db = scarica_database()

st.success(f"Database caricato: {len(db)} titoli disponibili.")

# Input Utente
col1, col2 = st.columns([3, 1])
with col1:
    isin_input = st.text_input("Inserisci Codice ISIN (es. IT0005519787)", "").strip()
with col2:
    tassazione = st.selectbox("Tassazione", [12.5, 26.0], index=0, help="12.5% per Stati (White List), 26% per Aziende")

if isin_input:
    # Cerca nel DB
    riga = db[db['ISIN'] == isin_input]
    
    if riga.empty:
        st.error(f"❌ ISIN {isin_input} non trovato nei listini automatici.")
        st.warning("Prova a cercare un BTP classico o un bond Europeo.")
    else:
        try:
            # Estrazione Dati
            prezzo = float(str(riga.iloc[0]['Price' if 'Price' in riga.columns else 'Last']).replace(',', '.'))
            c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
            cedola = 0.0 if c_raw in ['ZC', 'zero', '-'] else float(c_raw.replace(',', '.')) / 100
            s_str = str(riga.iloc[0]['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            nome = riga.iloc[0]['Name'] if 'Name' in riga.columns else "Titolo Sconosciuto"
            
            # Calcoli
            res = analizza_bond(prezzo, cedola, scadenza, tassazione)
            
            # --- VISUALIZZAZIONE RISULTATI ---
            st.divider()
            st.subheader(f"📄 {nome}")
            
            # Metriche in alto
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Prezzo Attuale", f"{prezzo} €")
            kpi2.metric("Rendimento Netto", f"{res['rendimento']:.2f}%")
            kpi3.metric("Guadagno Totale", f"{res['profitto']:+.2f} €", help="Su 1000€ investiti")
            kpi4.metric("Duration (Rischio)", f"{res['duration']:.2f} anni")
            
            # Grafico
            st.subheader("📉 Flussi di Cassa (Cash Flow)")
            
            df_plot = res['df_flussi']
            colors = ['red' if x < 0 else 'green' for x in df_plot["Importo"]]
            
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(df_plot["Data"], df_plot["Importo"], color=colors)
            ax.axhline(0, color='black', linewidth=0.8)
            ax.set_title("Uscite (Rosso) vs Entrate (Verde)")
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            
            # IMPORTANTE: Streamlit usa st.pyplot, non plt.show()
            st.pyplot(fig)
            
            # Tabella Dati
            with st.expander("Vedi Tabella Pagamenti Dettagliata"):
                st.dataframe(res['df_flussi'], use_container_width=True)
                
        except Exception as e:
            st.error(f"Errore nella lettura dei dati del titolo: {e}")
