import streamlit as st
import pandas as pd
import datetime
import yfinance as yf
import requests
import matplotlib.pyplot as plt
from scipy import optimize

# Configurazione
st.set_page_config(page_title="Bond Manager Multi-Source", layout="wide", page_icon="🌐")

if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# ==============================================================================
# 1. FONTE A: QUALEBTP.IT (Solo Italia - Molto leggero)
# ==============================================================================
@st.cache_data(ttl=600)
def scarica_qualebtp():
    """Scarica la tabella da QualeBTP.it (Ottimo per BTP Italia/Fissi)"""
    url = "https://www.qualebtp.it/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            # Pandas legge le tabelle HTML
            tabelle = pd.read_html(r.content, decimal=',', thousands='.')
            for df in tabelle:
                # QualeBTP ha una colonna ISIN esplicita
                if 'ISIN' in df.columns:
                    return df
    except:
        pass
    return pd.DataFrame()

# ==============================================================================
# 2. FONTE B: YAHOO FINANCE (Mondiale - API Ufficiale)
# ==============================================================================
def cerca_su_yahoo(isin):
    """Usa l'API ufficiale di Yahoo Finance (Non viene bloccata)"""
    # Yahoo usa i suffissi: .MI (Milano), .F (Francoforte), .PA (Parigi)
    suffissi = [".MI", ".F", ".RG", ""] # .RG è EuroTLX
    
    for suff in suffissi:
        ticker = isin + suff
        try:
            bond = yf.Ticker(ticker)
            # Cerchiamo dati storici veloci (prezzo attuale)
            hist = bond.history(period="1d")
            
            if not hist.empty:
                prezzo = float(hist['Close'].iloc[-1])
                info = bond.info
                
                # Yahoo spesso nasconde cedola e scadenza nei bond
                # Recuperiamo almeno il prezzo che è la cosa fondamentale
                return {
                    "Prezzo": prezzo,
                    "Nome": info.get('longName', ticker),
                    "Trovato": True,
                    "Fonte": f"Yahoo ({ticker})"
                }
        except:
            continue
            
    return {"Trovato": False}

# ==============================================================================
# 3. MOTORE MATEMATICO
# ==============================================================================
def calcola_tutto(prezzo, cedola_pct, scadenza, importo_investito, tasse_pct):
    oggi = datetime.date.today()
    if prezzo <= 0: prezzo = 100.0
    nominale = importo_investito / (prezzo / 100)
    
    flussi = [-importo_investito]
    date_f = [oggi]
    
    cedola_netta = (cedola_pct/100 * nominale) * (1 - tasse_pct/100)
    
    cursor = oggi
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
        "flussi": pd.DataFrame({"Data": date_f, "Importo": [round(x, 2) for x in flussi]}),
        "guadagno": sum(flussi)
    }

# ==============================================================================
# 4. INTERFACCIA UTENTE
# ==============================================================================
st.title("🌐 Bond Manager (Multi-Source)")

# Caricamento Sfondo (Database Italiano)
with st.spinner("Caricamento listino BTP..."):
    db_btp = scarica_qualebtp()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Cerca Titolo")
    isin_in = st.text_input("ISIN", "").strip().upper()
    
    # Valori Default
    dp, dc, ds, dn = 100.0, 3.0, datetime.date.today() + datetime.timedelta(days=1800), "Nuovo Bond"
    msg_stato = ""
    
    if isin_in:
        trovato = False
        
        # TENTATIVO 1: Database BTP Italia (QualeBTP)
        if not db_btp.empty:
            riga = db_btp[db_btp['ISIN'] == isin_in]
            if not riga.empty:
                st.success("Trovato su QualeBTP!")
                try:
                    r = riga.iloc[0]
                    dp = float(str(r['Prezzo']).replace(',', '.'))
                    dc = float(str(r['Cedola']).replace('%','').replace(',','.'))
                    ds = datetime.datetime.strptime(str(r['Scadenza']), "%d/%m/%Y").date()
                    dn = r['Titolo']
                    trovato = True
                except: pass
        
        # TENTATIVO 2: Yahoo Finance (Se non è un BTP o non trovato prima)
        if not trovato:
            dati_yahoo = cerca_su_yahoo(isin_in)
            if dati_yahoo["Trovato"]:
                st.info(f"Prezzo trovato su {dati_yahoo['Fonte']}")
                dp = dati_yahoo["Prezzo"]
                dn = dati_yahoo["Nome"]
                # Yahoo spesso non dà cedola/scadenza, quindi lasciamo all'utente di riempirli
                st.caption("⚠️ Yahoo fornisce il prezzo live. Verifica Cedola e Scadenza.")
                trovato = True
            else:
                st.warning("Non trovato online. Inserisci i dati a mano.")

    with st.form("calcola"):
        st.write(f"**Dati per: {dn}**")
        nome = st.text_input("Nome", value=dn)
        p = st.number_input("Prezzo (€)", value=dp, format="%.2f")
        c = st.number_input("Cedola (%)", value=dc, format="%.2f")
        s = st.date_input("Scadenza", value=ds)
        
        c1, c2 = st.columns(2)
        inv = c1.number_input("Investito (€)", value=5000, step=1000)
        tax = c2.selectbox("Tasse", [12.5, 26.0])
        
        submit = st.form_submit_button("Calcola Rendimento")

if submit:
    res = calcola_tutto(p, c, s, inv, tax)
    
    with col2:
        st.subheader(f"📊 Analisi: {nome}")
        
        

        m1, m2, m3 = st.columns(3)
        m1.metric("Rendimento Netto", f"{res['rendimento']:.2f}%", delta_color="normal")
        m2.metric("Guadagno Netto", f"{res['guadagno']:,.2f} €")
        m3.metric("Duration", "N/A") # Semplificato
        
        df_chart = res['flussi']
        colors = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.bar(df_chart["Data"], df_chart["Importo"], color=colors)
        ax.axhline(0, color='black')
        st.pyplot(fig)
        
        if st.button("➕ Aggiungi al Portafoglio"):
            st.session_state.portafoglio.append({
                "Nome": nome, "Investito": inv, 
                "Rendimento": res['rendimento'], "Flussi": res['flussi']
            })
            st.success("Titolo aggiunto!")
            st.rerun()

# SEZIONE PORTAFOGLIO
if st.session_state.portafoglio:
    st.divider()
    st.subheader("💼 Il tuo Portafoglio")
    
    # Tabella
    df_p = pd.DataFrame(st.session_state.portafoglio)[["Nome", "Investito", "Rendimento"]]
    st.table(df_p)
    
    # Grafico Totale
    flussi_tot = pd.concat([b['Flussi'] for b in st.session_state.portafoglio])
    df_aggr = flussi_tot.groupby("Data")["Importo"].sum().reset_index().sort_values("Data")
    
    fig2, ax2 = plt.subplots(figsize=(12, 4))
    cols2 = ['red' if x < 0 else 'green' for x in df_aggr["Importo"]]
    ax2.bar(df_aggr["Data"], df_aggr["Importo"], color=cols2)
    ax2.axhline(0, color='black')
    ax2.set_title("Flussi di Cassa Totali (Tutte le entrate)")
    st.pyplot(fig2)
    
    if st.button("🗑️ Reset"):
        st.session_state.portafoglio = []
        st.rerun()
