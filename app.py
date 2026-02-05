import streamlit as st
import pandas as pd
import cloudscraper # <--- L'ARMA SEGRETA
import datetime
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# CONFIGURAZIONE
# ==============================================================================
st.set_page_config(page_title="Bond Scraper Pro", layout="wide")

if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# ==============================================================================
# MOTORE DI SCARICAMENTO "CLOUDSCRAPER"
# ==============================================================================
@st.cache_data(ttl=600) # Cache 10 minuti
def get_market_data_advanced():
    urls = [
        "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
        "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
        "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR"
    ]
    
    db = pd.DataFrame()
    
    # Creiamo uno scraper che risolve le sfide JavaScript
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    bar = st.progress(0)
    
    for i, url in enumerate(urls):
        try:
            # Usiamo scraper.get invece di requests.get
            r = scraper.get(url)
            
            if r.status_code == 200:
                tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                for df in tabelle:
                    df.columns = df.columns.str.strip()
                    if 'ISIN' in df.columns:
                        df['ISIN'] = df['ISIN'].astype(str)
                        db = pd.concat([db, df], ignore_index=True)
                        break
            else:
                print(f"Errore {r.status_code} su {url}")
                
        except Exception as e:
            print(f"Errore Scraper: {e}")
        
        bar.progress((i + 1) / len(urls))
            
    bar.empty()
    return db

# ==============================================================================
# MOTORE MATEMATICO
# ==============================================================================
def calcola_tutto(prezzo, cedola_pct, scadenza, importo_investito, tasse_pct):
    oggi = datetime.date.today()
    if prezzo <= 0: prezzo = 100.0
    nominale = importo_investito / (prezzo / 100)
    
    flussi = [-importo_investito]
    date_f = [oggi]
    cedola_netta = (cedola_pct/100 * nominale) * (1 - tasse_pct/100)
    
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
            flussi.append(cedola_netta + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_netta)
            date_f.append(dt)
            
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0.0

    return {
        "rendimento": xirr(flussi, date_f) * 100,
        "duration": 0,
        "flussi": pd.DataFrame({"Data": date_f, "Importo": [round(x, 2) for x in flussi]})
    }

# ==============================================================================
# INTERFACCIA
# ==============================================================================
st.title("🛡️ Bond Scraper (Bypass Mode)")

with st.spinner("Bypassing protezioni anti-bot..."):
    db = get_market_data_advanced()

if not db.empty:
    st.success(f"✅ Bypassed! Scaricati {len(db)} bond.")
else:
    st.error("❌ Il sito ha rilevato anche CloudScraper. Usa la modalità manuale qui sotto.")

# INPUT
col1, col2 = st.columns([1, 2])

with col1:
    isin_in = st.text_input("ISIN", "").strip()
    
    # Default
    dp, dc, ds, dn = 100.0, 3.0, datetime.date.today() + datetime.timedelta(days=1800), "Nuovo Bond"
    
    if isin_in and not db.empty:
        riga = db[db['ISIN'] == isin_in]
        if not riga.empty:
            st.toast("Trovato!", icon="🔥")
            try:
                cols = riga.columns
                if 'Price' in cols: dp = float(str(riga.iloc[0]['Price']).replace(',','.'))
                elif 'Last' in cols: dp = float(str(riga.iloc[0]['Last']).replace(',','.'))
                
                c_str = str(riga.iloc[0]['Coupon']).replace('%','').strip().split(' ')[0]
                dc = 0.0 if c_str in ['ZC','zero','-'] else float(c_str.replace(',','.'))
                
                ds = datetime.datetime.strptime(str(riga.iloc[0]['Maturity']), "%d/%m/%Y").date()
                dn = riga.iloc[0]['Name'] if 'Name' in cols else isin_in
            except: pass

    with st.form("calcola"):
        nome = st.text_input("Nome", value=dn)
        p = st.number_input("Prezzo", value=dp, format="%.2f")
        c = st.number_input("Cedola %", value=dc, format="%.2f")
        s = st.date_input("Scadenza", value=ds)
        inv = st.number_input("Investito", value=5000, step=1000)
        tax = st.selectbox("Tassazione", [12.5, 26.0])
        submit = st.form_submit_button("Calcola")

if submit:
    res = calcola_tutto(p, c, s, inv, tax)
    
    with col2:
        st.subheader(f"📊 {nome}")
        st.metric("Rendimento Netto", f"{res['rendimento']:.2f}%")
        
        df_chart = res['flussi']
        colors = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.bar(df_chart["Data"], df_chart["Importo"], color=colors)
        st.pyplot(fig)
