import streamlit as st
import pandas as pd
import requests
import datetime
import time
import random
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================
st.set_page_config(page_title="Bond Sniper (Proxy Mode)", layout="wide", page_icon="🛡️")

if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# Lista URL Monitor
URLS = {
    "🇮🇹 Italia (BTP/CCT)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "🇮🇹 Italia (Inflation)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "🇪🇺 Europa (Romania/Est)": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "🇩🇪 Germania": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "🏢 Corporate": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
}

# ==============================================================================
# 1. MOTORE PROXY AUTOMATICO
# ==============================================================================
def get_free_proxies():
    """Scarica una lista di proxy pubblici gratuiti"""
    try:
        # Usiamo una lista pubblica affidabile di proxy HTTP/HTTPS
        url_list = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        r = requests.get(url_list, timeout=5)
        if r.status_code == 200:
            proxies = r.text.splitlines()
            return [p for p in proxies if p]
    except:
        return []
    return []

def scarica_con_proxy_rotativo(url_target):
    """
    Prova diversi proxy finché non ne trova uno che funziona.
    """
    status_box = st.empty()
    status_box.info("🕵️‍♂️ Cerco un tunnel (Proxy) funzionante...")
    
    proxies_list = get_free_proxies()
    # Ne prendiamo 20 a caso per non provare sempre gli stessi
    random.shuffle(proxies_list)
    short_list = proxies_list[:15]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://google.com"
    }

    # Tentativo DIRETTO (senza proxy) prima di tutto
    try:
        r = requests.get(url_target, headers=headers, timeout=5)
        if r.status_code == 200 and len(r.text) > 1000:
            status_box.success("✅ Connessione Diretta Riuscita!")
            time.sleep(1)
            status_box.empty()
            return r.text
    except:
        pass

    # Se diretto fallisce, inizia la rotazione proxy
    progress_bar = st.progress(0)
    
    for i, proxy in enumerate(short_list):
        protocollo = "http"
        proxy_dict = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        
        status_box.warning(f"🔄 Tentativo {i+1}/{len(short_list)} tramite {proxy}...")
        progress_bar.progress((i + 1) / len(short_list))
        
        try:
            r = requests.get(url_target, headers=headers, proxies=proxy_dict, timeout=4)
            
            # Controllo se ha scaricato davvero la pagina giusta
            if r.status_code == 200 and "ISIN" in r.text:
                status_box.success(f"✅ Trovato tunnel funzionante: {proxy}")
                time.sleep(1)
                status_box.empty()
                progress_bar.empty()
                return r.text
        except:
            continue # Se fallisce, passa al prossimo

    status_box.error("❌ Nessun proxy funzionante trovato al momento. Riprova.")
    progress_bar.empty()
    return None

# ==============================================================================
# 2. PARSING E CALCOLO
# ==============================================================================
def parse_html_table(html_content):
    if not html_content: return pd.DataFrame()
    try:
        dfs = pd.read_html(html_content, thousands='.', decimal=',')
        for df in dfs:
            if 'ISIN' in df.columns:
                df.columns = df.columns.str.strip()
                df['ISIN'] = df['ISIN'].astype(str).str.strip().str.upper()
                return df
    except: pass
    return pd.DataFrame()

def calcola_analytics(prezzo, cedola, scadenza, importo, tasse):
    nominale = importo / (prezzo/100)
    oggi = datetime.date.today()
    flussi = [-importo]
    date_f = [oggi]
    
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    cursor = today_f = oggi
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
            
    def xirr(cf, dts):
        dts = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts)]), 0.05)
        except: return 0
        
    rend = xirr(flussi, date_f)
    
    # Duration Semplificata
    duration = 0
    if rend > 0:
        num = sum([(date_f[i]-oggi).days/365.25 * flussi[i]/((1+rend)**((date_f[i]-oggi).days/365.25)) for i in range(1, len(flussi))])
        den = sum([flussi[i]/((1+rend)**((date_f[i]-oggi).days/365.25)) for i in range(1, len(flussi))])
        duration = num/den if den != 0 else 0
    
    return rend*100, duration, pd.DataFrame({"Data": date_f, "Importo": flussi})

# ==============================================================================
# 3. INTERFACCIA
# ==============================================================================
st.title("🛡️ Bond Sniper (Auto-Proxy)")
st.markdown("Se il server è bloccato, questo sistema cercherà automaticamente una via alternativa.")

# Selettore
mercato = st.selectbox("Seleziona Mercato:", list(URLS.keys()))

if st.button("🚀 Scarica Dati (con Bypass)", type="primary"):
    with st.spinner("Avvio procedura di sblocco..."):
        html_data = scarica_con_proxy_rotativo(URLS[mercato])
        
        if html_data:
            df = parse_html_table(html_data)
            if not df.empty:
                st.session_state['db_current'] = df
                st.rerun() # Ricarica per mostrare i dati
            else:
                st.error("HTML scaricato ma nessuna tabella valida trovata.")
        else:
            st.error("Tutti i tentativi di connessione sono falliti.")

# --- SEZIONE DATI ---
if 'db_current' in st.session_state:
    db = st.session_state['db_current']
    st.success(f"Dati caricati: {len(db)} obbligazioni disponibili.")
    
    st.divider()
    
    c1, c2, c3 = st.columns([2,1,1])
    isin_input = c1.text_input("Cerca ISIN:", "").strip().upper()
    investimento = c2.number_input("Euro:", value=10000, step=1000)
    tax = c3.selectbox("Tax:", [12.5, 26.0])
    
    if isin_input:
        res = db[db['ISIN'].str.contains(isin_input, na=False)]
        if not res.empty:
            row = res.iloc[0]
            
            # Estrazione sicura
            try:
                # Prezzo
                cols = row.index
                p_raw = row['Price'] if 'Price' in cols else row.get('Last', 100)
                prezzo = float(str(p_raw).replace(',', '.'))
                
                # Cedola
                c_raw = str(row.get('Coupon', 0)).replace('%','').strip().split(' ')[0]
                cedola = 0.0 if c_raw in ['ZC', 'zero', '-'] else float(c_raw.replace(',', '.'))/100
                
                # Scadenza
                s_obj = row['Maturity']
                scadenza = datetime.datetime.strptime(str(s_obj), "%d/%m/%Y").date() if isinstance(str(s_obj), str) else s_obj
                
                # Calcoli
                rend, dur, flussi = calcola_analytics(prezzo, cedola, scadenza, investimento, tax)
                
                st.markdown(f"### {row.get('Name', 'Bond')}")
                k1, k2, k3 = st.columns(3)
                k1.metric("Prezzo", f"{prezzo}")
                k2.metric("Rendimento Netto", f"{rend:.2f}%")
                k3.metric("Duration", f"{dur:.2f}")
                
                fig, ax = plt.subplots(figsize=(10, 2))
                colors = ['red' if x < 0 else 'green' for x in flussi["Importo"]]
                ax.bar(flussi["Data"], flussi["Importo"], color=colors)
                st.pyplot(fig)
                
                with st.expander("Dettagli Pagamenti"):
                    st.dataframe(flussi)
                    
            except Exception as e:
                st.error(f"Errore lettura dati: {e}")
        else:
            st.warning("ISIN non trovato nel listino scaricato.")
