import streamlit as st
import pandas as pd
import requests
import datetime
import time
import random
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# 0. CONFIGURAZIONE PAGINA
# ==============================================================================
st.set_page_config(page_title="Bond Manager Pro", layout="wide", page_icon="📊")

# Inizializza il portafoglio nella memoria del browser
if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# ==============================================================================
# 1. MOTORE DI SCARICAMENTO "ANTI-BLOCCO"
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
]

@st.cache_data(ttl=3600, show_spinner=False)
def scarica_database():
    """
    Scarica i dati e li salva in cache per 1 ora.
    Usa headers realistici per non farsi bloccare.
    """
    database_totale = pd.DataFrame()
    
    # Headers completi per sembrare un vero Browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    }

    # Barra di progresso nella sidebar per non disturbare
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    with requests.Session() as s:
        s.headers.update(headers)
        
        for i, url in enumerate(PAGINE_DA_ANALIZZARE):
            nome_monitor = url.split("monitor=")[1].split("&")[0].upper()
            status_text.text(f"Scaricamento: {nome_monitor}...")
            
            try:
                # Ritardo casuale minimo per sicurezza
                if i > 0: time.sleep(random.uniform(0.5, 1.5))
                
                r = s.get(url, timeout=15)
                
                if r.status_code == 200:
                    try:
                        tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                        for df in tabelle:
                            df.columns = df.columns.str.strip()
                            if 'ISIN' in df.columns:
                                df['ISIN'] = df['ISIN'].astype(str).str.strip().str.upper()
                                database_totale = pd.concat([database_totale, df], ignore_index=True)
                                break
                    except ValueError:
                        pass # Nessuna tabella trovata
            except Exception:
                continue # Passa al prossimo link se uno fallisce
            
            progress_bar.progress((i + 1) / len(PAGINE_DA_ANALIZZARE))
            
    status_text.empty()
    progress_bar.empty()
    return database_totale

# ==============================================================================
# 2. MOTORE MATEMATICO
# ==============================================================================
def analizza_flussi_bond(prezzo, cedola, scadenza, importo_investito, tasse_pct):
    nominale = importo_investito / (prezzo/100)
    oggi = datetime.date.today()
    
    flussi = [-importo_investito]
    date_f = [oggi]
    
    cedola_netta_totale = (cedola * nominale) * (1 - tasse_pct/100)
    
    cursor = today_f = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse_pct/100) * (nominale/100)
            rimborso_netto = nominale - tassa_gain
            
            flussi.append(cedola_netta_totale + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_netta_totale)
            date_f.append(dt)
            
    # Calcolo XIRR
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
        val_att = flussi[i] / ((1+rend_netto)**t_anni)
        numeratore += t_anni * val_att
        denominatore += val_att
    duration = numeratore / denominatore if denominatore != 0 else 0

    df_flussi = pd.DataFrame({"Data": date_f, "Importo": [round(f, 2) for f in flussi]})
    
    return {
        "rendimento": rend_netto * 100,
        "duration": duration,
        "profitto_netto": sum(flussi),
        "df_flussi": df_flussi,
        "scadenza": scadenza
    }

# ==============================================================================
# 3. INTERFACCIA UTENTE
# ==============================================================================

# Caricamento Dati (con spinner visibile solo la prima volta)
with st.spinner('Aggiornamento database bond in corso...'):
    db = scarica_database()

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title("Menu")
pagina = st.sidebar.radio("Seleziona:", ["🔎 Cerca Bond", "💼 Gestione Portafoglio"])

# --- PAGINA 1: RICERCA E ANALISI ---
if pagina == "🔎 Cerca Bond":
    st.title("🔎 Analisi Bond Singolo")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        isin_input = st.text_input("Inserisci ISIN (o parte del nome):").strip().upper()
    with col2:
        # Niente più domande Si/No, solo un menu pulito
        tasse_input = st.selectbox("Tassazione", [12.5, 26.0], index=0, help="12.5% per Titoli di Stato, 26% per Corporate")

    if isin_input:
        # Ricerca "Fuzzy" (trova anche se scrivi parziale)
        risultati = db[db['ISIN'].str.contains(isin_input, na=False)]
        
        if risultati.empty:
            st.error("❌ Nessun titolo trovato.")
        else:
            # Se ci sono più risultati, fanne scegliere uno
            if len(risultati) > 1:
                st.warning(f"Trovati {len(risultati)} titoli. Mostro il primo.")
            
            riga = risultati.iloc[0]
            
            try:
                # Parsing Dati
                cols = riga.index
                if 'Price' in cols: p = riga['Price']
                elif 'Last' in cols: p = riga['Last']
                else: p = riga.get('Bid', 0)
                prezzo = float(str(p).replace(',', '.'))
                
                c_str = str(riga['Coupon']).replace('%', '').strip().split(' ')[0]
                cedola = 0.0 if c_str in ['ZC', 'zero', '-'] else float(c_str.replace(',', '.')) / 100
                
                s_str = str(riga['Maturity'])
                scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
                nome = riga['Name'] if 'Name' in cols else isin_input
                
                # Calcoli (simuliamo 1000 euro per l'analisi singola)
                dati = analizza_flussi_bond(prezzo, cedola, scadenza, 1000, tasse_input)
                
                # --- VISUALIZZAZIONE ---
                st.divider()
                st.subheader(f"📄 {nome}")
                st.caption(f"ISIN: {riga['ISIN']}")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Prezzo", f"{prezzo} €")
                k2.metric("Rendimento Netto", f"{dati['rendimento']:.2f}%")
                k3.metric("Guadagno su 1k", f"{dati['profitto_netto']:+.2f} €")
                k4.metric("Duration", f"{dati['duration']:.2f} anni")
                
                # Grafico
                st.subheader("Flussi di Cassa")
                df_plot = dati['df_flussi']
                colors = ['red' if x < 0 else 'green' for x in df_plot["Importo"]]
                
                fig, ax = plt.subplots(figsize=(10, 3))
                ax.bar(df_plot["Data"], df_plot["Importo"], color=colors)
                ax.axhline(0, color='black', linewidth=0.8)
                ax.grid(axis='y', linestyle='--', alpha=0.5)
                st.pyplot(fig)

                with st.expander("Tabella Pagamenti"):
                    st.dataframe(dati['df_flussi'], use_container_width=True)

            except Exception as e:
                st.error(f"Errore analisi dati: {e}")

# --- PAGINA 2: PORTAFOGLIO ---
elif pagina == "💼 Gestione Portafoglio":
    st.title("💼 Il Tuo Portafoglio (Laddering)")
    
    # Sezione Aggiunta (in alto per comodità)
    with st.expander("➕ Aggiungi Titolo al Portafoglio", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        p_isin = c1.text_input("ISIN").strip().upper()
        p_importo = c2.number_input("Investimento (€)", min_value=1000, step=1000, value=5000)
        p_tasse = c3.selectbox("Tasse", [12.5, 26.0])
        
        if c4.button("Aggiungi"):
            res_db = db[db['ISIN'] == p_isin]
            if not res_db.empty:
                r = res_db.iloc[0]
                try:
                    # Estrazione rapida
                    cols = r.index
                    if 'Price' in cols: pr = float(str(r['Price']).replace(',', '.'))
                    elif 'Last' in cols: pr = float(str(r['Last']).replace(',', '.'))
                    else: pr = 100.0
                    
                    cp_str = str(r['Coupon']).replace('%', '').strip().split(' ')[0]
                    cp = 0.0 if cp_str in ['ZC', 'zero', '-'] else float(cp_str.replace(',', '.')) / 100
                    
                    sc = datetime.datetime.strptime(str(r['Maturity']), "%d/%m/%Y").date()
                    nm = r['Name'] if 'Name' in cols else p_isin
                    
                    # Calcolo
                    calcoli = analizza_flussi_bond(pr, cp, sc, p_importo, p_tasse)
                    
                    # Salvataggio in Sessione
                    st.session_state.portafoglio.append({
                        "ISIN": p_isin,
                        "Nome": nm,
                        "Scadenza": sc,
                        "Investito": p_importo,
                        "Rendimento": calcoli['rendimento'],
                        "Flussi": calcoli['df_flussi']
                    })
                    st.success(f"Aggiunto: {nm}")
                except: st.error("Errore nei dati del bond.")
            else:
                st.error("ISIN non trovato nel database.")

    # Visualizzazione Portafoglio
    if st.session_state.portafoglio:
        st.divider()
        
        # 1. Tabella Riepilogo
        df_view = pd.DataFrame([{
            "Nome": b["Nome"],
            "Scadenza": b["Scadenza"],
            "Investito": f"{b['Investito']} €",
            "Rendimento": f"{b['Rendimento']:.2f}%"
        } for b in st.session_state.portafoglio])
        
        st.subheader("I tuoi titoli")
        st.table(df_view)
        
        # 2. Aggregazione Totale
        tot_inv = sum(b['Investito'] for b in st.session_state.portafoglio)
        df_tot = pd.concat([b['Flussi'] for b in st.session_state.portafoglio])
        # Raggruppa per data sommando gli importi
        df_chart = df_tot.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
        guadagno_tot = df_chart["Importo"].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("Totale Investito", f"{tot_inv:,.0f} €")
        m2.metric("Profitto Netto a Scadenza", f"{guadagno_tot:,.2f} €", delta_color="normal")
        
        # 3. Grafico Aggregato
        st.subheader("📅 Flussi di Cassa Totali (Entrate previste)")
        
        fig2, ax2 = plt.subplots(figsize=(12, 5))
        colors2 = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        ax2.bar(df_chart["Data"], df_chart["Importo"], color=colors2)
        ax2.axhline(0, color='black', linewidth=0.8)
        ax2.grid(axis='y', linestyle='--', alpha=0.5)
        st.pyplot(fig2)
        
        if st.button("🗑️ Svuota Tutto"):
            st.session_state.portafoglio = []
            st.rerun()
    else:
        st.info("Il portafoglio è vuoto. Usa il pannello sopra per aggiungere titoli.")
