import streamlit as st
import pandas as pd
import datetime
import yfinance as yf
import matplotlib.pyplot as plt  # <--- QUESTA ERA LA RIGA MANCANTE
from scipy import optimize
from dateutil.relativedelta import relativedelta

# ==============================================================================
# CONFIGURAZIONE PAGINA
# ==============================================================================
st.set_page_config(page_title="Universal Bond Calculator", layout="wide", page_icon="🌍")

# Inizializza memoria (Session State) per ricordare i dati inseriti
if 'db_locale' not in st.session_state:
    st.session_state.db_locale = {}

# ==============================================================================
# 1. MOTORE DI RICERCA (YAHOO FINANCE)
# ==============================================================================
def cerca_titolo_universale(isin):
    isin = isin.strip().upper()
    
    # Suffissi per cercare nelle varie borse (Milano, EuroTLX, Francoforte, ecc.)
    suffissi = [".MI", ".RG", ".F", ".PA", ".DE", ""]
    
    info_trovate = {"successo": False, "msg": "Titolo non trovato."}

    # Barra di caricamento
    progress_text = "Ricerca sui mercati globali in corso..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, suff in enumerate(suffissi):
        ticker = isin + suff
        try:
            bond = yf.Ticker(ticker)
            # Chiediamo il prezzo di oggi
            hist = bond.history(period="1d")
            
            if not hist.empty:
                # TROVATO!
                prezzo = float(hist['Close'].iloc[-1])
                info = bond.info
                nome = info.get('longName', info.get('shortName', ticker))
                
                info_trovate = {
                    "successo": True,
                    "isin": isin,
                    "ticker": ticker,
                    "prezzo": prezzo,
                    "nome": nome,
                    "msg": f"Trovato su mercato: {suff if suff else 'USA/OTC'}"
                }
                my_bar.progress(100, text="Completato!")
                return info_trovate
        except:
            pass
        
        # Avanzamento barra
        perc = int((i+1)/len(suffissi)*100)
        my_bar.progress(perc, text=f"Cercando in {suff}...")

    my_bar.empty()
    return info_trovate

# ==============================================================================
# 2. MOTORE MATEMATICO (RENDIMENTO & FLUSSI)
# ==============================================================================
def calcola_rendimento(prezzo, cedola_pct, scadenza, investito, tasse_pct, freq_mesi):
    oggi = datetime.date.today()
    if prezzo <= 0: prezzo = 100.0
    
    nominale = investito / (prezzo / 100)
    flussi = [-investito]
    date_f = [oggi]
    
    # Calcolo cedola netta periodica
    cedola_annua_netta = (cedola_pct / 100) * nominale * (1 - tasse_pct/100)
    cedola_periodica = cedola_annua_netta / (12 / freq_mesi)
    
    cursor = today_f = oggi
    
    # Generazione date future
    while True:
        cursor = cursor + relativedelta(months=+freq_mesi)
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Rimborso capitale + Ultima cedola + Tasse su eventuale guadagno capitale
            gain_lordo = (100 - prezzo) * (nominale / 100)
            # Le tasse si pagano solo se c'è un guadagno (Capital Gain)
            tassa_gain = max(0, gain_lordo * (tasse_pct/100))
            rimborso_netto = nominale - tassa_gain
            
            flussi.append(cedola_periodica + rimborso_netto)
            date_f.append(dt)
            break
        else:
            flussi.append(cedola_periodica)
            date_f.append(dt)
            
    # Funzione XIRR (Tasso Interno di Rendimento)
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365.0) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0.0

    return {
        "rendimento": xirr(flussi, date_f) * 100,
        "flussi": pd.DataFrame({"Data": date_f, "Importo": [round(x, 2) for x in flussi]}),
        "guadagno": sum(flussi)
    }

# ==============================================================================
# 3. INTERFACCIA UTENTE
# ==============================================================================
st.title("🌍 Universal Bond Calculator")
st.caption("Inserisci ISIN -> Trova Prezzo Live -> Calcola Rendimento Netto")

# --- SEZIONE 1: RICERCA ---
col1, col2 = st.columns([1, 2])

with col1:
    isin_input = st.text_input("Inserisci ISIN", "").strip().upper()
    btn_cerca = st.button("🔍 Cerca Titolo")
    
    # Variabili di default
    dati_form = {
        "nome": "Nuovo Titolo",
        "prezzo": 100.0,
        "cedola": 3.0,
        "scadenza": datetime.date.today() + datetime.timedelta(days=365*5)
    }
    
    # LOGICA DI RICERCA
    if btn_cerca and isin_input:
        # 1. Controlla se lo conosciamo già (Memoria Sessione)
        if isin_input in st.session_state.db_locale:
            st.success("Dati recuperati dalla memoria!")
            saved = st.session_state.db_locale[isin_input]
            dati_form.update(saved)
            # Proviamo comunque ad aggiornare il prezzo live
            res_live = cerca_titolo_universale(isin_input)
            if res_live["successo"]:
                dati_form["prezzo"] = res_live["prezzo"]
                st.toast(f"Prezzo aggiornato live: {res_live['prezzo']}€")
                
        # 2. Se è nuovo, cerca online
        else:
            res = cerca_titolo_universale(isin_input)
            if res["successo"]:
                st.success(f"{res['msg']}")
                dati_form["prezzo"] = res["prezzo"]
                dati_form["nome"] = res["nome"]
                st.info("⚠️ Yahoo ha trovato il PREZZO. Verifica Cedola e Scadenza.")
            else:
                st.error("ISIN non trovato sui mercati online. Inserisci tutto manualmente.")

    st.divider()
    
    # --- SEZIONE 2: FORM DI CALCOLO ---
    with st.form("calcolo_bond"):
        st.markdown("### Dati Titolo")
        nome = st.text_input("Nome", value=dati_form["nome"])
        
        c_p, c_c = st.columns(2)
        p = c_p.number_input("Prezzo (€)", value=float(dati_form["prezzo"]), format="%.2f", step=0.01)
        c = c_c.number_input("Cedola Annuale (%)", value=float(dati_form["cedola"]), format="%.2f", step=0.1)
        
        s = st.date_input("Scadenza", value=dati_form["scadenza"])
        
        st.markdown("### Parametri Investimento")
        c_inv, c_tax = st.columns(2)
        inv = c_inv.number_input("Investito (€)", value=10000, step=1000)
        tax = c_tax.selectbox("Tasse", [12.5, 26.0], help="12.5% Stato, 26% Corporate")
        
        c_freq, c_b = st.columns(2)
        freq_dict = {"Annuale": 12, "Semestrale (BTP/BOT)": 6, "Trimestrale": 3}
        freq = c_freq.selectbox("Frequenza Cedola", list(freq_dict.keys()), index=1)
        
        submit = st.form_submit_button("🚀 Calcola Rendimento")

# --- SEZIONE 3: RISULTATI ---
if submit:
    # 1. Salva i dati fissi (cedola/scadenza) in memoria per il futuro
    if isin_input:
        st.session_state.db_locale[isin_input] = {
            "nome": nome, "cedola": c, "scadenza": s
        }
    
    # 2. Calcola
    res = calcola_rendimento(p, c, s, inv, tax, freq_dict[freq])
    
    with col2:
        st.subheader(f"📊 Risultati: {nome}")
        
        # KPI Principali
        k1, k2 = st.columns(2)
        k1.metric("Rendimento Netto Annuo", f"{res['rendimento']:.2f}%", delta_color="normal")
        k2.metric("Guadagno Netto Totale", f"{res['guadagno']:,.2f} €")
        
        # Grafico Flussi
        st.write("#### 📅 Flussi di Cassa")
        df_chart = res['flussi']
        colors = ['red' if x < 0 else 'green' for x in df_chart["Importo"]]
        
        # Creazione Grafico
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.bar(df_chart["Data"], df_chart["Importo"], color=colors, width=20)
        ax.axhline(0, color='black', linewidth=0.8)
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        
        # Mostra il grafico con Streamlit
        st.pyplot(fig)
        
        with st.expander("Vedi Tabella Pagamenti"):
            st.dataframe(df_chart)
