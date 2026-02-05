import streamlit as st
import pandas as pd
import requests
import datetime
import time
import random
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# CONFIGURAZIONE E LISTA IDENTITÀ (Per aggirare i blocchi)
# ==============================================================================
st.set_page_config(page_title="Bond Sniper", layout="wide", page_icon="🎯")

# Lista di "Facce" da usare a rotazione per confondere il server
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

URLS = {
    "🇮🇹 Italia (BTP/CCT)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "🇮🇹 Italia (Inflation Linked)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "🇪🇺 Europa (Romania/Bulgaria/Est)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "🇩🇪 Germania (Bund)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "🏢 Corporate (Aziende)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "🇺🇸 USA (Treasury)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
}

# ==============================================================================
# 1. FUNZIONE SCARICAMENTO FURTIVO
# ==============================================================================
@st.cache_data(ttl=600, show_spinner=False) # Cache di 10 minuti
def scarica_listino_specifico(url_target):
    """
    Scarica SOLO un listino alla volta per non insospettire il server.
    """
    # Ritardo casuale (simula un umano che ci mette tempo a cliccare)
    time.sleep(random.uniform(1.0, 3.0))
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS), # Cambia identità ogni volta
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }

    try:
        r = requests.get(url_target, headers=headers, timeout=15)
        
        if r.status_code == 200:
            dfs = pd.read_html(r.text, thousands='.', decimal=',')
            # Cerca la tabella giusta
            for df in dfs:
                if 'ISIN' in df.columns:
                    # Pulizia colonne
                    df.columns = df.columns.str.strip()
                    df['ISIN'] = df['ISIN'].astype(str).str.strip().str.upper()
                    return df
    except Exception as e:
        return None
    
    return None

# ==============================================================================
# 2. MOTORE MATEMATICO
# ==============================================================================
def calcola_analytics(prezzo, cedola, scadenza, importo, tasse):
    nominale = importo / (prezzo/100)
    oggi = datetime.date.today()
    flussi = [-importo]
    date_f = [oggi]
    
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
            flussi.append(cedola_netta + (nominale - tassa_gain))
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_netta)
            date_f.append(dt)
            
    # XIRR
    def xirr(cf, dts):
        dts = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts)]), 0.05)
        except: return 0
        
    rend = xirr(flussi, date_f)
    
    # Duration
    num = sum([(date_f[i]-oggi).days/365.25 * flussi[i]/((1+rend)**((date_f[i]-oggi).days/365.25)) for i in range(1, len(flussi))])
    den = sum([flussi[i]/((1+rend)**((date_f[i]-oggi).days/365.25)) for i in range(1, len(flussi))])
    duration = num/den if den != 0 else 0
    
    return rend*100, duration, pd.DataFrame({"Data": date_f, "Importo": flussi})

# ==============================================================================
# 3. INTERFACCIA UTENTE
# ==============================================================================
st.title("🎯 Bond Sniper (Anti-Block)")
st.markdown("Questo sistema scarica **solo il mercato necessario** per evitare il ban dell'IP.")

# --- SELEZIONE MERCATO (Strategica) ---
col_m1, col_m2 = st.columns([2, 1])
with col_m1:
    mercato_scelto = st.selectbox("1. Seleziona Mercato (Scarica solo questo)", list(URLS.keys()))
with col_m2:
    if st.button("🔄 Forza Aggiornamento"):
        st.cache_data.clear()
        st.rerun()

# --- SCARICAMENTO MIRATO ---
with st.spinner(f"Scaricamento dati {mercato_scelto} in corso..."):
    db = scarica_listino_specifico(URLS[mercato_scelto])

if db is None or db.empty:
    st.error("⛔ Blocco IP Attivo o Errore Connessione.")
    st.warning("Il sito ha rifiutato la connessione. Attendi qualche minuto e riprova.")
    st.stop()
else:
    st.success(f"✅ Dati scaricati: {len(db)} titoli disponibili.")

st.divider()

# --- RICERCA TITOLO ---
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    isin_search = st.text_input("2. Cerca ISIN o Nome", placeholder="es. IT0005...").strip().upper()
with col2:
    importo = st.number_input("Investimento €", value=10000, step=1000)
with col3:
    tasse = st.selectbox("Tassazione", [12.5, 26.0])

if isin_search:
    # Filtro
    filtro = db[db['ISIN'].str.contains(isin_search, na=False) | db['Name'].astype(str).str.contains(isin_search, case=False, na=False)]
    
    if filtro.empty:
        st.warning("Nessun titolo trovato in questo mercato.")
    else:
        # Selettore se ci sono più risultati
        opzioni = filtro['ISIN'] + " | " + filtro['Name']
        scelta = st.selectbox("Trovati più titoli, seleziona:", opzioni)
        
        isin_reale = scelta.split(" | ")[0]
        riga = filtro[filtro['ISIN'] == isin_reale].iloc[0]
        
        # --- ANALISI ---
        try:
            # Parsing "sporco" ma efficace per vari formati
            cols = riga.index
            if 'Price' in cols: p_val = riga['Price']
            elif 'Last' in cols: p_val = riga['Last']
            else: p_val = 100
            
            p = float(str(p_val).replace(',', '.'))
            
            c_str = str(riga.get('Coupon', 0)).replace('%','').strip().split(' ')[0]
            c = 0.0 if c_str in ['ZC', 'zero', '-'] else float(c_str.replace(',', '.'))/100
            
            s_obj = riga['Maturity']
            # Gestione formati data misti
            if isinstance(s_obj, str):
                s = datetime.datetime.strptime(s_obj, "%d/%m/%Y").date()
            else:
                s = s_obj # Se pandas l'ha già convertito
            
            # Calcolo
            rend, dur, df_flussi = calcola_analytics(p, c, s, importo, tasse)
            
            # --- DASHBOARD ---
            st.markdown(f"### 📄 {riga.get('Name', 'Bond')}")
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Prezzo", f"{p} €")
            k2.metric("Rendimento Netto", f"{rend:.2f}%", delta="Reale Annuo")
            k3.metric("Duration", f"{dur:.2f} anni")
            k4.metric("Profitto Totale", f"{(df_flussi['Importo'].sum()):+.2f} €")
            
            # Grafico
            fig, ax = plt.subplots(figsize=(10, 3))
            colors = ['red' if x < 0 else 'green' for x in df_flussi["Importo"]]
            ax.bar(df_flussi["Data"], df_flussi["Importo"], color=colors)
            ax.axhline(0, color='black')
            st.pyplot(fig)
            
            with st.expander("Dettaglio Flussi"):
                st.dataframe(df_flussi)
                
        except Exception as e:
            st.error(f"Errore nella lettura dei dati del titolo: {e}")
