import streamlit as st
import pandas as pd
import requests
import datetime
import matplotlib.pyplot as plt
from scipy import optimize

# Configurazione Pagina
st.set_page_config(page_title="Portfolio Bond Manager", layout="wide")

# Inizializzazione Memoria (Session State) per il Portafoglio
if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

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
# 2. MOTORE SCARICAMENTO DATI
# ==============================================================================
@st.cache_data(ttl=3600)
def scarica_database():
    db = pd.DataFrame()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Usiamo uno spinner discreto nella sidebar
    with st.sidebar:
        with st.spinner('Aggiornamento listini...'):
            for url in PAGINE_DA_ANALIZZARE:
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                    if tabelle:
                        df = max(tabelle, key=len)
                        df.columns = df.columns.str.strip()
                        if 'ISIN' in df.columns:
                            db = pd.concat([db, df], ignore_index=True)
                except: continue
    return db

# ==============================================================================
# 3. MOTORE ANALISI FINANZIARIA
# ==============================================================================
def calcola_flussi_bond(prezzo, cedola, scadenza, importo_investito, tasse=12.5):
    # Calcolo nominale acquistato (es. con 5000€ a prezzo 80 compro molto più nominale)
    # Formula: Importo Reale / (Prezzo/100)
    nominale = importo_investito / (prezzo/100)
    oggi = datetime.date.today()
    
    flussi = []
    date_f = []
    
    # Uscita Iniziale (Reale)
    flussi.append(-importo_investito)
    date_f.append(oggi)
    
    cedola_netta_totale = (cedola * nominale) * (1 - tasse/100)
    
    cursor = today_f = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Rimborso Nominale + Cedola + Gain Netto
            # Gain = (100 - Prezzo) * Nominale. Tasse sul Gain.
            plusvalenza_unitaria = max(0, 100 - prezzo)
            tassa_gain = plusvalenza_unitaria * (tasse/100) * (nominale/100)
            
            rimborso_netto = nominale - tassa_gain
            
            flussi.append(cedola_netta_totale + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_netta_totale)
            date_f.append(dt)
            
    return pd.DataFrame({"Data": date_f, "Importo": flussi, "ISIN": "Bond"})

def calcola_xirr(df_flussi):
    if df_flussi.empty: return 0
    df_grp = df_flussi.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
    
    dts = df_grp["Data"].tolist()
    cf = df_grp["Importo"].tolist()
    
    dts_days = [(d - dts[0]).days for d in dts]
    try: 
        res = optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        return res * 100
    except: return 0

# ==============================================================================
# 4. INTERFACCIA
# ==============================================================================
st.title("💰 Gestore Portafoglio Obbligazionario")

db = scarica_database()

# --- SIDEBAR: AGGIUNGI TITOLI ---
with st.sidebar:
    st.header("➕ Aggiungi al Portafoglio")
    input_isin = st.text_input("ISIN", placeholder="es. IT0005519787").strip()
    input_euro = st.number_input("Importo da Investire (€)", min_value=1000, step=1000, value=5000)
    input_tasse = st.selectbox("Tassazione", [12.5, 26.0], index=0)
    
    if st.button("Aggiungi Bond"):
        riga = db[db['ISIN'] == input_isin]
        if not riga.empty:
            # Estrazione Dati
            try:
                prezzo = float(str(riga.iloc[0]['Price' if 'Price' in riga.columns else 'Last']).replace(',', '.'))
                c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
                cedola = 0.0 if c_raw in ['ZC', 'zero', '-'] else float(c_raw.replace(',', '.')) / 100
                s_str = str(riga.iloc[0]['Maturity'])
                scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
                nome = riga.iloc[0]['Name'] if 'Name' in riga.columns else input_isin
                
                # Calcola flussi
                df_bond = calcola_flussi_bond(prezzo, cedola, scadenza, input_euro, input_tasse)
                rendimento = calcola_xirr(df_bond)
                
                # Salva in Session State
                bond_data = {
                    "ISIN": input_isin,
                    "Nome": nome,
                    "Investito": input_euro,
                    "Prezzo": prezzo,
                    "Scadenza": scadenza,
                    "Rendimento": rendimento,
                    "Flussi": df_bond
                }
                st.session_state.portafoglio.append(bond_data)
                st.success(f"✅ {nome} aggiunto!")
            except Exception as e:
                st.error(f"Errore lettura dati: {e}")
        else:
            st.error("❌ ISIN non trovato.")

    st.divider()
    if st.button("🗑️ Svuota Portafoglio"):
        st.session_state.portafoglio = []
        st.rerun()

# --- MAIN PAGE: ANALISI PORTAFOGLIO ---

if not st.session_state.portafoglio:
    st.info("👈 Il portafoglio è vuoto. Aggiungi dei titoli dalla barra laterale per iniziare la strategia Laddering.")
else:
    # 1. Tabella Riepilogativa
    st.subheader("📋 Il tuo Portafoglio")
    
    lista_display = []
    totale_investito = 0
    df_flussi_totali = pd.DataFrame()
    
    for bond in st.session_state.portafoglio:
        lista_display.append({
            "Nome": bond["Nome"],
            "ISIN": bond["ISIN"],
            "Scadenza": bond["Scadenza"],
            "Investito (€)": f"{bond['Investito']:,.0f}",
            "Rendimento Netto": f"{bond['Rendimento']:.2f}%"
        })
        totale_investito += bond["Investito"]
        df_flussi_totali = pd.concat([df_flussi_totali, bond["Flussi"]])
    
    st.table(pd.DataFrame(lista_display))
    
    # 2. Calcoli Aggregati
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    rendimento_portafoglio = calcola_xirr(df_flussi_totali)
    profitto_totale = df_flussi_totali["Importo"].sum()
    
    col1.metric("Capitale Totale", f"{totale_investito:,.0f} €")
    col2.metric("Rendimento Netto Annuo (TIR)", f"{rendimento_portafoglio:.2f}%", help="Rendimento composto di tutto il portafoglio")
    col3.metric("Guadagno Netto a Scadenza", f"{profitto_totale:,.2f} €", delta_color="normal")
    
    # 3. Grafico Flussi Aggregati
    st.subheader("📅 Flussi di Cassa Combinati (Cash Flow)")
    st.markdown("Ecco quanti soldi ti entrano **complessivamente** (sommando le cedole di tutti i titoli).")
    
    # Raggruppa per data
    df_chart = df_flussi_totali.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
    ax.bar(df_chart["Data"], df_chart["Importo"], color=colors, width=50)
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_ylabel("Euro (€)")
    ax.set_title("Entrate/Uscite Totali del Portafoglio")
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Formatta asse X per date
    plt.gcf().autofmt_xdate()
    
    st.pyplot(fig)
    
    # 4. Tabella Flussi Dettagliata
    with st.expander("Vedi Tabella Pagamenti Dettagliata"):
        st.dataframe(df_chart, use_container_width=True)
