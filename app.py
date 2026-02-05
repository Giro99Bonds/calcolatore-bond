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
st.set_page_config(page_title="Bond Manager (Anti-Ban)", layout="wide", page_icon="🛡️")

if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# Lista di "Facce" (User-Agents) diverse per confondere il server
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 1. MOTORE DI SCARICAMENTO "BYPASS"
# ==============================================================================
# Rimosso @st.cache_data per forzare tentativi freschi se cambi proxy
def scarica_database(proxy_url=None):
    database_totale = pd.DataFrame()
    
    # Seleziona un'identità a caso
    current_agent = random.choice(USER_AGENTS)
    
    headers = {
        "User-Agent": current_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/", # Finge di arrivare da Google
        "Connection": "keep-alive"
    }

    # Configurazione Proxy (se inserito dall'utente)
    proxies = {}
    if proxy_url:
        if not proxy_url.startswith("http"):
            proxy_url = f"http://{proxy_url}"
        proxies = {"http": proxy_url, "https": proxy_url}
        st.toast(f"🕵️‍♂️ Uso Proxy: {proxy_url}", icon="🛡️")

    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    with requests.Session() as s:
        s.headers.update(headers)
        
        for i, url in enumerate(PAGINE_DA_ANALIZZARE):
            try:
                nome_monitor = url.split("monitor=")[1].split("&")[0].upper()
                status_text.text(f"Scarico {nome_monitor}...")
                
                # Aggiungi parametro casuale per evitare la cache del server
                url_bypass = f"{url}&nocache={random.randint(1, 100000)}"
                
                # Ritardo casuale per sembrare umano
                time.sleep(random.uniform(1.0, 3.0))
                
                r = s.get(url_bypass, timeout=20, proxies=proxies)
                
                if r.status_code == 200:
                    try:
                        tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                        for df in tabelle:
                            df.columns = df.columns.str.strip()
                            if 'ISIN' in df.columns:
                                df['ISIN'] = df['ISIN'].astype(str).str.strip().str.upper()
                                database_totale = pd.concat([database_totale, df], ignore_index=True)
                                break
                    except ValueError: pass
                elif r.status_code == 403:
                    st.toast(f"⛔ Blocco IP su {nome_monitor}. Prova col Proxy!", icon="⚠️")
                    
            except Exception as e:
                continue
            
            progress_bar.progress((i + 1) / len(PAGINE_DA_ANALIZZARE))
            
    status_text.empty()
    progress_bar.empty()
    
    # Se vuoto, restituisci struttura vuota per non crashare
    if database_totale.empty:
        return pd.DataFrame(columns=['ISIN', 'Name', 'Price', 'Coupon', 'Maturity'])
        
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
            
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0

    rend_netto = xirr(flussi, date_f)
    
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

st.sidebar.title("Configurazione")

# --- BOX PROXY (LA SOLUZIONE ANTI-BAN) ---
st.sidebar.markdown("### 🛡️ Bypass Blocco IP")
proxy_input = st.sidebar.text_input("Inserisci Proxy HTTP (Opzionale)", placeholder="es. 192.168.1.1:8080", help="Se il sito ti ha bloccato, cerca 'Free HTTP Proxy List' su Google e incollane uno qui.")

if st.sidebar.button("🔄 Ricarica Dati"):
    st.cache_data.clear()
    st.rerun()

# Caricamento DB
if 'db' not in st.session_state or st.sidebar.button("Forza Aggiornamento"):
    with st.spinner('Connessione Stealth in corso...'):
        st.session_state.db = scarica_database(proxy_input if proxy_input else None)

db = st.session_state.db

# --- CONTROLLO D'EMERGENZA ---
if db.empty or 'ISIN' not in db.columns:
    st.error("⛔ Blocco IP rilevato.")
    st.warning("Il sito ha bloccato la tua connessione. Vai su 'spys.one/en/http-proxy-list/', copia un IP e incollalo nel box 'Bypass Blocco IP' a sinistra.")
    st.stop()

# --- NAVIGAZIONE ---
pagina = st.sidebar.radio("Vai a:", ["🔎 Cerca Bond", "💼 Gestione Portafoglio"])

if pagina == "🔎 Cerca Bond":
    st.title("🔎 Analisi Bond (Anti-Ban)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        isin_input = st.text_input("ISIN o Nome:").strip().upper()
    with col2:
        tasse_input = st.selectbox("Tassazione", [12.5, 26.0])

    if isin_input:
        risultati = db[db['ISIN'].str.contains(isin_input, na=False)]
        
        if risultati.empty:
            st.error("❌ Nessun titolo trovato.")
        else:
            riga = risultati.iloc[0]
            try:
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
                
                dati = analizza_flussi_bond(prezzo, cedola, scadenza, 1000, tasse_input)
                
                st.divider()
                st.subheader(f"📄 {nome}")
                st.caption(f"ISIN: {riga['ISIN']}")
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Prezzo", f"{prezzo} €")
                k2.metric("Rendimento Netto", f"{dati['rendimento']:.2f}%")
                k3.metric("Guadagno su 1k", f"{dati['profitto_netto']:+.2f} €")
                k4.metric("Duration", f"{dati['duration']:.2f} anni")
                
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
                st.error(f"Errore calcolo: {e}")

elif pagina == "💼 Gestione Portafoglio":
    st.title("💼 Portafoglio Laddering")
    
    with st.expander("➕ Aggiungi Titolo", expanded=True):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        p_isin = c1.text_input("ISIN").strip().upper()
        p_importo = c2.number_input("Euro", min_value=1000, step=1000, value=5000)
        p_tasse = c3.selectbox("Tax", [12.5, 26.0])
        
        if c4.button("Aggiungi"):
            res_db = db[db['ISIN'] == p_isin]
            if not res_db.empty:
                r = res_db.iloc[0]
                try:
                    cols = r.index
                    if 'Price' in cols: pr = float(str(r['Price']).replace(',', '.'))
                    else: pr = float(str(r.get('Last', 100)).replace(',', '.'))
                    
                    cp_str = str(r.get('Coupon', '0')).replace('%', '').strip().split(' ')[0]
                    cp = 0.0 if cp_str in ['ZC', 'zero', '-'] else float(cp_str.replace(',', '.')) / 100
                    
                    sc = datetime.datetime.strptime(str(r['Maturity']), "%d/%m/%Y").date()
                    nm = r.get('Name', p_isin)
                    
                    calcoli = analizza_flussi_bond(pr, cp, sc, p_importo, p_tasse)
                    
                    st.session_state.portafoglio.append({
                        "ISIN": p_isin, "Nome": nm, "Scadenza": sc,
                        "Investito": p_importo, "Rendimento": calcoli['rendimento'],
                        "Flussi": calcoli['df_flussi']
                    })
                    st.success(f"Aggiunto: {nm}")
                except: st.error("Dati non validi.")
            else:
                st.error("ISIN non trovato.")

    if st.session_state.portafoglio:
        st.divider()
        
        # Tabella
        df_view = pd.DataFrame([{
            "Nome": b["Nome"], "Scadenza": b["Scadenza"],
            "Investito": f"{b['Investito']} €", "Rendimento": f"{b['Rendimento']:.2f}%"
        } for b in st.session_state.portafoglio])
        st.table(df_view)
        
        # Totali
        tot_inv = sum(b['Investito'] for b in st.session_state.portafoglio)
        df_tot = pd.concat([b['Flussi'] for b in st.session_state.portafoglio])
        df_chart = df_tot.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
        guadagno_tot = df_chart["Importo"].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("Totale Investito", f"{tot_inv:,.0f} €")
        m2.metric("Profitto Netto Totale", f"{guadagno_tot:,.2f} €")
        
        # Grafico
        fig2, ax2 = plt.subplots(figsize=(12, 5))
        colors2 = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        ax2.bar(df_chart["Data"], df_chart["Importo"], color=colors2)
        ax2.axhline(0, color='black', linewidth=0.8)
        ax2.grid(axis='y', linestyle='--', alpha=0.5)
        st.pyplot(fig2)
        
        if st.button("🗑️ Reset"):
            st.session_state.portafoglio = []
            st.rerun()
