import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from scipy import optimize
from dateutil.relativedelta import relativedelta

# Configurazione
st.set_page_config(page_title="Bond Calculator (Indistruttibile)", layout="wide", page_icon="🛡️")

# Inizializza portafoglio
if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# ==============================================================================
# 1. GENERATORE DI LINK (L'Assistente)
# ==============================================================================
def genera_link_ricerca(isin):
    isin = isin.strip().upper()
    return {
        "Google": f"https://www.google.com/search?q={isin}+prezzo",
        "BorsaItaliana": f"https://www.borsaitaliana.it/borsa/obbligazioni/mot/euro-obbligazioni/scheda/{isin}.html?lang=it",
        "Teleborsa": f"https://www.teleborsa.it/Ricerca?q={isin}",
        "EuroTLX": f"https://www.borsaitaliana.it/borsa/obbligazioni/eurotlx/scheda/{isin}.html?lang=it"
    }

# ==============================================================================
# 2. MOTORE MATEMATICO (Cuore del sistema)
# ==============================================================================
def calcola_rendimento(prezzo, cedola_pct, scadenza, investito, tasse_pct, freq_mesi):
    oggi = datetime.date.today()
    if prezzo <= 0.01: prezzo = 100.0
    
    nominale = investito / (prezzo / 100)
    flussi = [-investito]
    date_f = [oggi]
    
    # Cedola netta periodica
    cedola_annua_netta = (cedola_pct / 100) * nominale * (1 - tasse_pct/100)
    cedola_periodica = cedola_annua_netta / (12 / freq_mesi)
    
    cursor = today_f = oggi
    
    while True:
        cursor = cursor + relativedelta(months=+freq_mesi)
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            gain_lordo = (100 - prezzo) * (nominale / 100)
            tassa_gain = max(0, gain_lordo * (tasse_pct/100))
            rimborso_netto = nominale - tassa_gain
            flussi.append(cedola_periodica + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_periodica)
            date_f.append(dt)
            
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365.0) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0.0

    tir = xirr(flussi, date_f) * 100
    
    # Duration semplificata
    numeratore = 0
    denominatore = 0
    for i in range(1, len(flussi)):
        t_anni = (date_f[i] - oggi).days / 365.25
        val_att = flussi[i] / ((1+tir/100)**t_anni)
        numeratore += t_anni * val_att
        denominatore += val_att
    duration = numeratore / denominatore if denominatore != 0 else 0

    return {
        "tir": tir,
        "duration": duration,
        "flussi": pd.DataFrame({"Data": date_f, "Importo": [round(x, 2) for x in flussi]}),
        "guadagno": sum(flussi)
    }

# ==============================================================================
# 3. INTERFACCIA
# ==============================================================================
st.title("🛡️ Bond Calculator Pro (Manuale Assistito)")
st.markdown("Questo strumento **non scarica dati** (per evitare blocchi) ma ti aiuta a trovarli in 1 secondo e fa tutti i calcoli complessi.")

# --- SEZIONE CERCA E LINK ---
col_isin, col_link = st.columns([1, 2])
with col_isin:
    isin_input = st.text_input("1. Incolla ISIN qui:", placeholder="IT000...").strip().upper()

with col_link:
    st.write("2. Clicca per trovare i dati (si apre in nuova scheda):")
    if isin_input:
        links = genera_link_ricerca(isin_input)
        c1, c2, c3, c4 = st.columns(4)
        c1.link_button("🌐 Google", links["Google"])
        c2.link_button("🇮🇹 Borsa IT", links["BorsaItaliana"])
        c3.link_button("📊 Teleborsa", links["Teleborsa"])
        c4.link_button("🇪🇺 EuroTLX", links["EuroTLX"])
    else:
        st.info("👆 Inserisci un ISIN per generare i link rapidi.")

st.divider()

# --- SEZIONE DATI E CALCOLO ---
st.subheader("3. Inserisci i 3 dati fondamentali")

with st.form("calcolo"):
    c_dati, c_soldi = st.columns(2)
    
    with c_dati:
        nome = st.text_input("Nome (Opzionale)", value=isin_input if isin_input else "Mio Bond")
        p = st.number_input("Prezzo di Mercato (€)", min_value=0.0, value=100.0, step=0.1, format="%.2f")
        c = st.number_input("Cedola Annuale (%)", min_value=0.0, value=3.0, step=0.1, format="%.2f")
        s = st.date_input("Data Scadenza", value=datetime.date.today() + datetime.timedelta(days=365*4))
        
    with c_soldi:
        inv = st.number_input("Quanto vuoi investire? (€)", value=10000, step=1000)
        
        f1, f2 = st.columns(2)
        tax = f1.selectbox("Tassazione", [12.5, 26.0], help="12.5% Stato (White list), 26% Corporate/Altri")
        
        freq_map = {"Annuale": 12, "Semestrale (BTP Standard)": 6, "Trimestrale": 3, "Mensile": 1}
        freq = f2.selectbox("Frequenza Cedola", list(freq_map.keys()), index=1)
    
    submit = st.form_submit_button("🚀 CALCOLA RENDIMENTO", type="primary")

# --- SEZIONE RISULTATI ---
if submit:
    res = calcola_rendimento(p, c, s, inv, tax, freq_map[freq])
    
    st.divider()
    st.subheader(f"📊 Risultati per: {nome}")
    
    # KPI
    k1, k2, k3 = st.columns(3)
    k1.metric("Rendimento Netto Annuo", f"{res['tir']:.2f}%", delta_color="normal")
    k2.metric("Guadagno Netto Totale", f"{res['guadagno']:,.2f} €")
    k3.metric("Duration (Rischio)", f"{res['duration']:.2f} anni")
    
    # Grafico
    df = res['flussi']
    col_graph, col_tab = st.columns([2, 1])
    
    with col_graph:
        st.write("#### Flussi di Cassa")
        colors = ['red' if x < 0 else 'green' for x in df['Importo']]
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(df['Data'], df['Importo'], color=colors)
        ax.axhline(0, color='black', linewidth=1)
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        st.pyplot(fig)
        
    with col_tab:
        st.write("#### Piano Cedolare")
        st.dataframe(df, height=300)
    
    # Aggiungi al portafoglio (CON STATUS)
    if st.button("➕ Aggiungi questo bond al Portafoglio"):
        st.session_state.portafoglio.append({
            "Nome": nome, 
            "Investito": inv, 
            "Rendimento": res['tir'], 
            "Flussi": res['flussi'],
            "Status": "In attesa" # <--- NUOVA COLONNA RICHIESTA
        })
        st.success("Aggiunto con status 'In attesa'!")
        st.rerun()

# --- PORTAFOGLIO ---
if st.session_state.portafoglio:
    st.divider()
    st.header(f"💼 Il tuo Portafoglio ({len(st.session_state.portafoglio)} titoli)")
    
    # Mostra la tabella includendo la colonna Status
    df_p = pd.DataFrame(st.session_state.portafoglio)[["Nome", "Investito", "Rendimento", "Status"]]
    st.table(df_p)
    
    # Grafico Aggregato
    flussi_tot = pd.concat([b['Flussi'] for b in st.session_state.portafoglio])
    df_aggr = flussi_tot.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
    
    st.write("### 💰 Flussi Totali Combinati")
    fig2, ax2 = plt.subplots(figsize=(12, 4))
    cols2 = ['red' if x < 0 else 'green' for x in df_aggr["Importo"]]
    ax2.bar(df_aggr["Data"], df_aggr["Importo"], color=cols2)
    ax2.axhline(0, color='black')
    st.pyplot(fig2)
    
    if st.button("🗑️ Svuota tutto"):
        st.session_state.portafoglio = []
        st.rerun()
