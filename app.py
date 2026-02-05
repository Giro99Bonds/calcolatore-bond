import streamlit as st
import pandas as pd
import requests
import datetime
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# 0. CONFIGURAZIONE E SETUP
# ==============================================================================
st.set_page_config(page_title="Bond Master Tool", layout="wide", page_icon="📈")

# Inizializza Session State per il Portafoglio (Memoria)
if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# Link ai database
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 1. FUNZIONI DI CALCOLO E SCARICAMENTO (IL MOTORE)
# ==============================================================================
@st.cache_data(ttl=3600)
def scarica_database():
    db = pd.DataFrame()
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in PAGINE_DA_ANALIZZARE:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            tabelle = pd.read_html(r.text, thousands='.', decimal=',')
            if tabelle:
                df = max(tabelle, key=len)
                df.columns = df.columns.str.strip()
                if 'ISIN' in df.columns:
                    db = pd.concat([db, df], ignore_index=True)
        except: continue
    return db

def analizza_flussi_completi(prezzo, cedola, scadenza, importo_nominale=1000, tasse=12.5):
    oggi = datetime.date.today()
    flussi = []
    date_f = []
    
    # 1. Acquisto (Uscita)
    # Calcolo costo reale: Prezzo% * Nominale
    costo_acquisto = -importo_nominale * (prezzo/100)
    flussi.append(costo_acquisto)
    date_f.append(oggi)
    
    cedola_netta_importo = (cedola * importo_nominale) * (1 - tasse/100)
    
    cursor = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Rimborso + Cedola + Gain Netto
            gain_unitario = max(0, 100 - prezzo)
            tassa_gain = (gain_unitario * (tasse/100)) / 100 * importo_nominale
            rimborso_netto = importo_nominale - tassa_gain
            
            flussi.append(cedola_netta_importo + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_netta_importo)
            date_f.append(dt)
            
    # Calcolo XIRR
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0

    rend_netto = xirr(flussi, date_f)
    
    # Calcolo Duration
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
        "df_flussi": df_flussi
    }

# ==============================================================================
# 2. INTERFACCIA UTENTE (NAVIGAZIONE)
# ==============================================================================

# Scaricamento dati all'avvio (nascosto)
with st.spinner('Connessione ai mercati in corso...'):
    db = scarica_database()

# --- MENU LATERALE ---
st.sidebar.title("📌 Menu Navigazione")
pagina_selezionata = st.sidebar.radio(
    "Vai a:", 
    ["🔎 Analisi Singolo Titolo", "💼 Portafoglio Laddering"]
)

# ------------------------------------------------------------------------------
# PAGINA 1: ANALISI SINGOLO TITOLO (DETTAGLIATA + GRAFICI)
# ------------------------------------------------------------------------------
if pagina_selezionata == "🔎 Analisi Singolo Titolo":
    st.title("🔎 Analisi Approfondita Bond")
    st.markdown("Inserisci un ISIN per vedere rendimento reale, duration e grafico dei pagamenti.")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        isin_input = st.text_input("Inserisci ISIN:", placeholder="Es. IT0005519787").strip()
    with col2:
        tasse_input = st.selectbox("Tassazione", [12.5, 26.0], index=0)
        
    if isin_input:
        riga = db[db['ISIN'] == isin_input]
        if riga.empty:
            st.error("❌ ISIN non trovato nei listini.")
        else:
            try:
                # Dati base
                prezzo = float(str(riga.iloc[0]['Price' if 'Price' in riga.columns else 'Last']).replace(',', '.'))
                c_str = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
                cedola = 0.0 if c_str in ['ZC', 'zero', '-'] else float(c_str.replace(',', '.')) / 100
                s_str = str(riga.iloc[0]['Maturity'])
                scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
                nome = riga.iloc[0]['Name'] if 'Name' in riga.columns else isin_input
                
                # Calcolo Avanzato
                dati = analizza_flussi_completi(prezzo, cedola, scadenza, 1000, tasse_input)
                
                # --- VISUALIZZAZIONE ---
                st.divider()
                st.subheader(f"📄 {nome}")
                
                # 4 KPI
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Prezzo", f"{prezzo} €")
                k2.metric("Rendimento Netto", f"{dati['rendimento']:.2f}%")
                k3.metric("Guadagno su 1k", f"{dati['profitto_netto']:+.2f} €")
                k4.metric("Duration (Rischio)", f"{dati['duration']:.2f} anni", help="Sensibilità ai tassi d'interesse")
                
                # Grafico Flussi
                st.subheader("📉 Grafico Flussi di Cassa")
                df_plot = dati['df_flussi']
                colors = ['red' if x < 0 else 'green' for x in df_plot["Importo"]]
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.bar(df_plot["Data"], df_plot["Importo"], color=colors)
                ax.axhline(0, color='black', linewidth=0.8)
                ax.set_title("Uscita Iniziale (Rosso) vs Cedole Future (Verde)")
                ax.grid(axis='y', linestyle='--', alpha=0.5)
                st.pyplot(fig)
                
                # Tabella
                with st.expander("Vedi Tabella Pagamenti"):
                    st.dataframe(dati['df_flussi'], use_container_width=True)
                    
            except Exception as e:
                st.error(f"Errore nei calcoli: {e}")


# ------------------------------------------------------------------------------
# PAGINA 2: PORTAFOGLIO LADDERING (GESTIONE + GRAFICO AGGREGATO)
# ------------------------------------------------------------------------------
elif pagina_selezionata == "💼 Portafoglio Laddering":
    st.title("💼 Il Tuo Portafoglio Obbligazionario")
    
    # Form per aggiungere titoli (nella pagina principale per comodità)
    with st.expander("➕ Aggiungi un nuovo Bond al portafoglio", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        p_isin = c1.text_input("ISIN Bond").strip()
        p_importo = c2.number_input("Importo Investito (€)", min_value=1000, step=1000, value=5000)
        p_tasse = c3.selectbox("Tasse %", [12.5, 26.0])
        
        if c4.button("Aggiungi"):
            riga = db[db['ISIN'] == p_isin]
            if not riga.empty:
                try:
                    # Estrazione e Calcolo
                    prezzo = float(str(riga.iloc[0]['Price' if 'Price' in riga.columns else 'Last']).replace(',', '.'))
                    c_str = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
                    cedola = 0.0 if c_str in ['ZC', 'zero', '-'] else float(c_str.replace(',', '.')) / 100
                    s_str = str(riga.iloc[0]['Maturity'])
                    scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
                    nome = riga.iloc[0]['Name'] if 'Name' in riga.columns else p_isin
                    
                    res = analizza_flussi_completi(prezzo, cedola, scadenza, p_importo, p_tasse)
                    
                    st.session_state.portafoglio.append({
                        "ISIN": p_isin, "Nome": nome, "Investito": p_importo,
                        "Scadenza": scadenza, "Rendimento": res['rendimento'],
                        "Flussi": res['df_flussi']
                    })
                    st.success(f"{nome} aggiunto!")
                except: st.error("Errore dati bond.")
            else:
                st.error("ISIN non trovato.")

    # Visualizzazione Portafoglio
    if st.session_state.portafoglio:
        st.divider()
        st.subheader("Riepilogo Titoli")
        
        # Tabella semplice
        df_view = pd.DataFrame([{
            "Nome": b["Nome"], "Scadenza": b["Scadenza"], 
            "Investito": f"{b['Investito']} €", "Rendimento": f"{b['Rendimento']:.2f}%"
        } for b in st.session_state.portafoglio])
        st.table(df_view)
        
        # Aggregazione Flussi
        df_total = pd.concat([b["Flussi"] for b in st.session_state.portafoglio])
        df_chart = df_total.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
        
        # Metriche Totali
        tot_invest = sum([b["Investito"] for b in st.session_state.portafoglio])
        tot_guadagno = df_chart["Importo"].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("Capitale Totale Investito", f"{tot_invest:,.0f} €")
        m2.metric("Guadagno Netto Totale a Scadenza", f"{tot_guadagno:,.2f} €")
        
        # Grafico Aggregato
        st.subheader("📅 Flussi di Cassa Combinati (Cash Flow Totale)")
        fig2, ax2 = plt.subplots(figsize=(12, 5))
        colors2 = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        ax2.bar(df_chart["Data"], df_chart["Importo"], color=colors2)
        ax2.axhline(0, color='black', linewidth=0.8)
        ax2.set_title("Quando riceverai i soldi (somma di tutte le cedole)")
        ax2.grid(axis='y', linestyle='--', alpha=0.5)
        st.pyplot(fig2)
        
        if st.button("🗑️ Reset Portafoglio"):
            st.session_state.portafoglio = []
            st.rerun()
    else:
        st.info("Il portafoglio è vuoto. Aggiungi titoli sopra.")
