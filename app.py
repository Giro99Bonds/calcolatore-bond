import streamlit as st
import pandas as pd
import datetime
import yfinance as yf
import requests
import matplotlib.pyplot as plt
from scipy import optimize
from dateutil.relativedelta import relativedelta # Importante per calcolo date preciso

# Configurazione Pagina
st.set_page_config(page_title="Bond Manager Pro", layout="wide", page_icon="📈")

if 'portafoglio' not in st.session_state:
    st.session_state.portafoglio = []

# ==============================================================================
# 1. SCARICAMENTO DATI (QualeBTP + Yahoo)
# ==============================================================================
@st.cache_data(ttl=600)
def scarica_qualebtp():
    url = "https://www.qualebtp.it/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            tabelle = pd.read_html(r.content, decimal=',', thousands='.')
            for df in tabelle:
                if 'ISIN' in df.columns:
                    return df
    except: pass
    return pd.DataFrame()

def cerca_su_yahoo(isin):
    suffissi = [".MI", ".F", ".RG", ""] 
    for suff in suffissi:
        ticker = isin + suff
        try:
            bond = yf.Ticker(ticker)
            hist = bond.history(period="1d")
            if not hist.empty:
                prezzo = float(hist['Close'].iloc[-1])
                info = bond.info
                return {
                    "Prezzo": prezzo,
                    "Nome": info.get('longName', ticker),
                    "Trovato": True,
                    "Fonte": f"Yahoo ({ticker})"
                }
        except: continue
    return {"Trovato": False}

# ==============================================================================
# 2. MOTORE MATEMATICO (CORRETTO PER FREQUENZA)
# ==============================================================================
def calcola_rendimento_preciso(prezzo, cedola_pct, scadenza, importo_investito, tasse_pct, frequenza_mesi):
    oggi = datetime.date.today()
    if prezzo <= 0: prezzo = 100.0
    
    # Calcolo Nominale (Quanti pezzi compro)
    # Esempio: Investo 1000€ a prezzo 90 -> Compro 1111€ nominali
    nominale = importo_investito / (prezzo / 100)
    
    flussi = []
    date_f = []
    
    # 1. USCITA: Oggi pago l'investimento
    flussi.append(-importo_investito)
    date_f.append(oggi)
    
    # 2. CEDOLE FUTURE
    # Cedola annuale netta in %
    cedola_annuale_netta_pct = cedola_pct * (1 - tasse_pct/100)
    # Importo cedola singola (es. se semestrale è metà)
    numero_cedole_anno = 12 / frequenza_mesi
    importo_cedola_netta = (cedola_annuale_netta_pct / 100 * nominale) / numero_cedole_anno
    
    # Generiamo le date future
    cursor = today_f = oggi
    
    # Troviamo la prossima data cedola (stimata)
    # Andiamo avanti di "frequenza_mesi" finché non superiamo oggi
    # (Semplificazione: per precisione assoluta servirebbe data godimento, ma questo approssima bene)
    while True:
        cursor = cursor + relativedelta(months=+frequenza_mesi)
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Rimborso Finale + Ultima Cedola + Minus/Plusvalenza
            gain_lordo = (100 - prezzo) * (nominale / 100)
            if gain_lordo > 0:
                tassa_gain = gain_lordo * (tasse_pct / 100)
                rimborso_netto = nominale - tassa_gain
            else:
                rimborso_netto = nominale # Minusvalenza (non gestita fiscalmente qui per semplicità)
            
            flussi.append(importo_cedola_netta + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(importo_cedola_netta)
            date_f.append(dt)
            
    # 3. CALCOLO XIRR
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: 
            return optimize.newton(lambda r: sum([v/(1+r)**(d/365.0) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0.0

    rendimento = xirr(flussi, date_f) * 100
    
    return {
        "rendimento": rendimento,
        "flussi": pd.DataFrame({"Data": date_f, "Importo": [round(x, 2) for x in flussi]}),
        "guadagno": sum(flussi)
    }

# ==============================================================================
# 3. INTERFACCIA
# ==============================================================================
st.title("📈 Calcolatore Rendimenti Reali")

# Caricamento Sfondo
with st.spinner("Caricamento listini..."):
    db_btp = scarica_qualebtp()

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Inserimento Dati")
    isin_in = st.text_input("ISIN", "").strip().upper()
    
    # Default
    dp, dc, ds, dn = 100.0, 3.0, datetime.date.today() + datetime.timedelta(days=1800), "Nuovo Bond"
    frequenza_default = 6 # Default BTP (Semestrale)
    
    if isin_in:
        trovato = False
        # Cerca su QualeBTP
        if not db_btp.empty:
            riga = db_btp[db_btp['ISIN'] == isin_in]
            if not riga.empty:
                st.success("Trovato (BTP Italia)!")
                try:
                    r = riga.iloc[0]
                    # Parsing Robusto
                    dp = float(str(r['Prezzo']).replace(',', '.'))
                    dc = float(str(r['Cedola']).replace('%','').replace(',','.'))
                    ds = datetime.datetime.strptime(str(r['Scadenza']), "%d/%m/%Y").date()
                    dn = r['Titolo']
                    trovato = True
                except: pass
        
        # Cerca su Yahoo
        if not trovato:
            dy = cerca_su_yahoo(isin_in)
            if dy["Trovato"]:
                st.info(f"Prezzo trovato su Yahoo Finance")
                dp = dy["Prezzo"]
                dn = dy["Nome"]
                st.caption("⚠️ Controlla Cedola e Scadenza manualmente.")

    with st.form("calcola"):
        nome = st.text_input("Nome", value=dn)
        
        c1, c2 = st.columns(2)
        p = c1.number_input("Prezzo (€)", value=dp, format="%.2f", help="Prezzo di mercato (Corso Secco)")
        c = c2.number_input("Cedola Annuale (%)", value=dc, format="%.2f")
        
        s = st.date_input("Scadenza", value=ds)
        
        st.divider()
        c3, c4 = st.columns(2)
        # SELETTORE FREQUENZA (FONDAMENTALE PER IL CALCOLO)
        freq_dict = {"Annuale": 12, "Semestrale (BTP Standard)": 6, "Trimestrale": 3}
        freq_label = c3.selectbox("Frequenza Cedola", list(freq_dict.keys()), index=1) # Default Semestrale
        freq_val = freq_dict[freq_label]
        
        tax = c4.selectbox("Tasse", [12.5, 26.0], help="12.5% Titoli Stato, 26% Aziende")
        inv = st.number_input("Investito (€)", value=10000, step=1000)
        
        submit = st.form_submit_button("Calcola Rendimento Netto")

if submit:
    res = calcola_rendimento_preciso(p, c, s, inv, tax, freq_val)
    
    with col2:
        st.subheader(f"📊 Risultati: {nome}")
        
        m1, m2 = st.columns(2)
        m1.metric("Rendimento Netto Annuo (XIRR)", f"{res['rendimento']:.2f}%", delta_color="normal")
        m2.metric("Guadagno Netto a Scadenza", f"{res['guadagno']:,.2f} €")
        
        st.info(f"Cedola netta per periodo: **{res['flussi']['Importo'].iloc[1]:.2f} €**")
        
        df_chart = res['flussi']
        colors = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        
        # Grafico
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(df_chart["Data"], df_chart["Importo"], color=colors, width=20) # Width fisso per estetica
        ax.axhline(0, color='black', linewidth=1)
        ax.set_title("Flussi di Cassa")
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        st.pyplot(fig)
        
        with st.expander("Vedi Tabella Pagamenti"):
            st.dataframe(res['flussi'])
        
        if st.button("➕ Aggiungi al Portafoglio"):
            st.session_state.portafoglio.append({
                "Nome": nome, "Investito": inv, 
                "Rendimento": res['rendimento'], "Flussi": res['flussi']
            })
            st.success("Aggiunto!")
            st.rerun()

# PORTAFOGLIO
if st.session_state.portafoglio:
    st.divider()
    st.subheader("💼 Portafoglio")
    df_p = pd.DataFrame(st.session_state.portafoglio)[["Nome", "Investito", "Rendimento"]]
    st.table(df_p)
    
    if st.button("Reset"):
        st.session_state.portafoglio = []
        st.rerun()
