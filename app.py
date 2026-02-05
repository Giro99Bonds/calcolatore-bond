import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Bond Club Portfolio", page_icon="💼", layout="wide")

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'access_granted' not in st.session_state:
    st.session_state.access_granted = False
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = [] # Lista per salvare i bond del portafoglio

# --- FUNZIONI DI CALCOLO (Backend) ---
def xirr(cashflows, dates):
    if not cashflows or not dates: return None
    def xnpv(rate, cashflows, dates):
        if rate <= -1.0: return float('inf')
        t0 = dates[0]
        return sum([cf / ((1 + rate) ** ((d - t0).days / 365.0)) for cf, d in zip(cashflows, dates)])
    try:
        return optimize.newton(lambda r: xnpv(r, cashflows, dates), 0.05)
    except:
        return None

def rendimento_semplice_360(prezzo, rimborso, giorni):
    if giorni <= 0: return 0
    return ((rimborso - prezzo) / prezzo) * (360 / giorni)

def get_bond_data(isin_code):
    sources = [
        {"nome": "BOT (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BTP (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND (Germania)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT (Francia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GLOBALI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    for source in sources:
        try:
            r = requests.get(source["url"], headers=headers, timeout=5)
            if r.status_code != 200: continue
            df_list = pd.read_html(r.content, decimal=",", thousands=".")
            for df in df_list:
                if 'Codice ISIN' in df.columns:
                    match = df[df['Codice ISIN'] == isin_code]
                    if not match.empty:
                        row = match.iloc[0]
                        pr = float(str(row['Prezzo di riferimento']).replace(',', '.'))
                        scad = datetime.strptime(str(row['Data scadenza']), '%Y-%m-%d').date()
                        desc = row['Descrizione']
                        val = row['Divisa'] if 'Divisa' in df.columns else "EUR"
                        ced = 0.0
                        if source["freq"] > 0:
                            m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                            if m: ced = float(m.group(1).replace(',', '.'))
                        
                        return {"source": source["nome"], "freq": source["freq"], "valuta": val,
                                "prezzo": pr, "scadenza": scad, "cedola": ced, "desc": desc}
        except: pass
    return None

def calcola_metriche(dati, tax_rate):
    today = date.today()
    np_today = np.datetime64(today, 'D')
    data_valuta = np.busday_offset(np_today, 2, roll='forward').astype(date)
    giorni = (dati['scadenza'] - data_valuta).days
    
    cf_lordi = [-dati['prezzo']]
    cf_netti = [-dati['prezzo']]
    dates = [data_valuta]
    nominale = 100.0
    
    if dati['freq'] > 0 and dati['cedola'] > 0:
        c_lorda = dati['cedola']/dati['freq']
        c_netta = c_lorda * (1-tax_rate)
        curr = dati['scadenza']
        delta = 365 // dati['freq']
        c_future = []
        while curr > data_valuta:
            c_future.append(curr)
            curr -= timedelta(days=delta)
        c_future.sort()
        for d in c_future:
            cf_lordi.append(c_lorda)
            cf_netti.append(c_netta)
            dates.append(d)
        cf_lordi[-1] += nominale
        gain = max(0, nominale - dati['prezzo'])
        cf_netti[-1] += (nominale - (gain*tax_rate) - c_netta)
    else:
        cf_lordi.append(nominale)
        gain = max(0, nominale - dati['prezzo'])
        cf_netti.append(nominale - (gain*tax_rate))
        dates.append(dati['scadenza'])
        
    tir_lordo = xirr(cf_lordi, dates)
    tir_netto = xirr(cf_netti, dates)
    
    return {"tir_lordo": tir_lordo, "tir_netto": tir_netto, "giorni": giorni, "data_valuta": data_valuta}

# ==========================================
#              GATEKEEPER
# ==========================================
if not st.session_state.access_granted:
    st.markdown("<h1 style='text-align: center; color: red;'>⛔ AREA RISERVATA ⛔</h1>", unsafe_allow_html=True)
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align: center;'>SEI UN TOSSICO? 💊</h3>", unsafe_allow_html=True)
        st.caption("<p style='text-align: center;'>(Domanda di sicurezza obbligatoria)</p>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("SÌ, SONO DIPENDENTE", use_container_width=True):
            st.session_state.access_granted = True
            st.rerun()
        if b2.button("NO, STO BENE", use_container_width=True):
            st.markdown("<h1 style='text-align: center;'>SOLO FATTONI! 😤</h1>", unsafe_allow_html=True)
            st.stop()

# ==========================================
#           APP PRINCIPALE
# ==========================================
else:
    # --- SIDEBAR MENU ---
    with st.sidebar:
        st.title("Menu Bond Club")
        page = st.radio("Scegli Sezione:", ["🔎 Analisi Singola", "💼 Costruisci Portafoglio"])
        st.divider()
        if st.button("Esci dal Club"):
            st.session_state.access_granted = False
            st.rerun()

    # =========================================================
    # PAGINA 1: ANALISI SINGOLA (Quella che avevamo)
    # =========================================================
    if page == "🔎 Analisi Singola":
        st.title("🔎 Scanner Bond")
        st.caption("Analizza un singolo titolo o confrontane due.")

        tab1, tab2 = st.tabs(["Analisi", "Confronto"])

        with tab1:
            c1, c2, c3 = st.columns([2, 1, 1])
            isin_input = c1.text_input("Inserisci ISIN", placeholder="Es. IT000...", key="single_isin").strip().upper()
            tassazione = c2.selectbox("Tassazione", [12.5, 26.0], index=0, format_func=lambda x: f"{x}%", key="tax1")
            c3.write("") 
            c3.write("")
            if c3.button("Calcola", use_container_width=True, key="btn1") and isin_input:
                with st.spinner("Scraping in corso..."):
                    dati = get_bond_data(isin_input)
                    if dati:
                        res = calcola_metriche(dati, tassazione/100)
                        st.success(f"**{dati['desc']}**")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Prezzo", f"{dati['prezzo']} {dati['valuta']}")
                        m2.metric("Rendimento Netto", f"{res['tir_netto']*100:.3f}%")
                        m3.metric("Rendimento Lordo", f"{res['tir_lordo']*100:.3f}%")
                        st.info(f"Scadenza: {dati['scadenza']} ({res['giorni']} gg)")
                    else:
                        st.error("ISIN non trovato.")

        with tab2:
            st.write("Confronto diretto tra due ISIN")
            col_a, col_b = st.columns(2)
            isin_a = col_a.text_input("ISIN A", key="cmp_a").strip().upper()
            isin_b = col_b.text_input("ISIN B", key="cmp_b").strip().upper()
            tax_cmp = st.radio("Tasse confronto", [12.5, 26.0], horizontal=True, key="tax_cmp")

            if st.button("Confronta") and isin_a and isin_b:
                with st.spinner("Analisi differenziale..."):
                    da = get_bond_data(isin_a)
                    db = get_bond_data(isin_b)
                    if da and db:
                        ra = calcola_metriche(da, tax_cmp/100)
                        rb = calcola_metriche(db, tax_cmp/100)
                        
                        st.divider()
                        ca, cb = st.columns(2)
                        ca.metric(f"A: {da['desc'][:20]}...", f"{ra['tir_netto']*100:.3f}%")
                        cb.metric(f"B: {db['desc'][:20]}...", f"{rb['tir_netto']*100:.3f}%", delta=f"{(rb['tir_netto']-ra['tir_netto'])*100:.3f}%")
                    else:
                        st.error("Uno dei due ISIN non trovato.")

    # =========================================================
    # PAGINA 2: COSTRUISCI PORTAFOGLIO (Nuova)
    # =========================================================
    elif page == "💼 Costruisci Portafoglio":
        st.title("💼 Il Mio Portafoglio Bond")
        st.write("Aggiungi i titoli che possiedi (o vorresti) per calcolare il rendimento complessivo.")

        # --- SEZIONE AGGIUNTA ---
        with st.container(border=True):
            st.subheader("Aggiungi Titolo")
            c_in1, c_in2, c_in3, c_in4 = st.columns([2, 2, 1, 1])
            
            p_isin = c_in1.text_input("ISIN", placeholder="IT000...", key="p_isin").strip().upper()
            p_nominale = c_in2.number_input("Valore Nominale (€)", min_value=1000, step=1000, value=1000, help="Quanti soldi di valore facciale compri")
            p_tax = c_in3.selectbox("Tasse", [12.5, 26.0], key="p_tax", format_func=lambda x: f"{x}%")
            c_in4.write("")
            c_in4.write("")
            add_btn = c_in4.button("➕ Aggiungi", use_container_width=True)

            if add_btn and p_isin:
                with st.spinner("Cerco e calcolo..."):
                    dati = get_bond_data(p_isin)
                    if dati:
                        # Calcolo metriche per questo bond
                        metrics = calcola_metriche(dati, p_tax/100)
                        
                        # Calcolo valore di mercato (Quanto paghi davvero)
                        valore_mercato = (p_nominale * dati['prezzo']) / 100
                        
                        nuovo_bond = {
                            "ISIN": p_isin,
                            "Nome": dati['desc'],
                            "Nominale": p_nominale,
                            "Prezzo": dati['prezzo'],
                            "Valore Mercato": valore_mercato,
                            "Rend. Netto %": metrics['tir_netto'] * 100,
                            "Rend. Lordo %": metrics['tir_lordo'] * 100,
                            "Tasse": p_tax,
                            "Valuta": dati['valuta']
                        }
                        
                        st.session_state.portfolio.append(nuovo_bond)
                        st.success(f"Aggiunto: {dati['desc']}")
                    else:
                        st.error("ISIN non trovato.")

        # --- VISUALIZZAZIONE PORTAFOGLIO ---
        if len(st.session_state.portfolio) > 0:
            st.divider()
            st.subheader("📊 Composizione Attuale")
            
            # Creiamo un DataFrame per visualizzare meglio
            df_pf = pd.DataFrame(st.session_state.portfolio)
            
            # Tabella interattiva
            st.dataframe(df_pf[["ISIN", "Nome", "Nominale", "Prezzo", "Valore Mercato", "Rend. Netto %"]], use_container_width=True)

            # --- CALCOLO RENDIMENTO MEDIO PONDERATO ---
            totale_investito = df_pf["Valore Mercato"].sum()
            
            # Formula Ponderata: Somma(Rendimento * Peso)
            # Peso = Valore Mercato del singolo bond / Totale Investito
            
            df_pf["Peso"] = df_pf["Valore Mercato"] / totale_investito
            df_pf["Contributo Netto"] = df_pf["Rend. Netto %"] * df_pf["Peso"]
            df_pf["Contributo Lordo"] = df_pf["Rend. Lordo %"] * df_pf["Peso"]
            
            avg_yield_netto = df_pf["Contributo Netto"].sum()
            avg_yield_lordo = df_pf["Contributo Lordo"].sum()
            
            st.divider()
            col_res1, col_res2, col_res3 = st.columns(3)
            
            col_res1.metric("Totale Investito (Mercato)", f"€ {totale_investito:,.2f}")
            col_res2.metric("Rendimento Medio Netto", f"{avg_yield_netto:.3f}%", help="Media ponderata in base ai soldi investiti")
            col_res3.metric("Rendimento Medio Lordo", f"{avg_yield_lordo:.3f}%")
            
            # Grafico a torta
            st.write("Distribuzione Portafoglio:")
            st.bar_chart(df_pf.set_index("Nome")["Valore Mercato"])
            
            # Tasto Reset
            if st.button("🗑️ Svuota Portafoglio"):
                st.session_state.portfolio = []
                st.rerun()
        else:
            st.info("Il tuo portafoglio è vuoto. Aggiungi dei bond sopra.")
