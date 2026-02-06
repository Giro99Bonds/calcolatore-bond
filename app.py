import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
import time
import random
import plotly.graph_objects as go

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide")

# CREDENZIALI
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# --- INIZIALIZZAZIONE STATO ---
if 'confronto' not in st.session_state: st.session_state.confronto = None # Per salvare il bond da confrontare

# --- MAPPA FONTI ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI (Stati: Italia, Germania, USA...)": [
        {"nome": "BTP ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TDS 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI (Banche & Subordinate)": [
        {"nome": "BANCHE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE (Aziende Industriali)": [
        {"nome": "CORPORATE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE (Auto)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY (Petrolio)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM (Tlc)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI (Zero Coupon, Green, ecc.)": [
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHISSIMI (25Y+)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI BACKEND ---
def determina_tasse(nome_fonte, descrizione_titolo):
    fonti_whitelist = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "TDS", "SOVRANAZIONALI"]
    for w in fonti_whitelist:
        if w in nome_fonte.upper(): return 12.5
    desc_upper = descrizione_titolo.upper()
    keywords_stato = ["REPUBLIC", "REPUBBLICA", "TREASURY", "KINGDOM", "REGNO", "BTP", "CCT", "BOT", "OAT", "BUND"]
    for k in keywords_stato:
        if k in desc_upper: return 12.5
    return 26.0

def genera_flussi_cassa(dati, importo_investito, tax_rate):
    """Genera la tabella dei flussi futuri"""
    flussi = []
    nominale = importo_investito
    prezzo_acquisto = (importo_investito * dati['pr']) / 100
    
    # Date
    oggi = date.today()
    scadenza = dati['sc']
    freq = dati['freq'] # 1=Annuale, 2=Semestrale, 0=Zero Coupon
    
    # 1. Flusso di Acquisto (Oggi)
    flussi.append({
        "Data": oggi.strftime("%d/%m/%Y"),
        "Tipo": "🔴 Acquisto",
        "Importo Lordo": -prezzo_acquisto,
        "Tasse": 0,
        "Importo Netto": -prezzo_acquisto,
        "Capitale Cumulato": -prezzo_acquisto
    })
    
    # 2. Cedole Intermedie
    cedola_totale_netta = 0
    if freq > 0:
        cedola_pct_annua = dati['ced']
        mesi_step = 12 // freq
        cedola_valore_lordo = (nominale * (cedola_pct_annua / 100)) / freq
        cedola_valore_netto = cedola_valore_lordo * (1 - (tax_rate/100))
        
        # Generiamo date a ritroso dalla scadenza fino ad oggi
        cursore_data = scadenza
        date_cedole = []
        while cursore_data > today_plus_2(oggi):
            date_cedole.append(cursore_data)
            # Sottrai mesi
            anno = cursore_data.year
            mese = cursore_data.month - mesi_step
            if mese <= 0:
                mese += 12
                anno -= 1
            try:
                cursore_data = cursore_data.replace(year=anno, month=mese)
            except ValueError: # Gestione fine mese (es. 31 non esiste a febbraio)
                cursore_data = cursore_data.replace(year=anno, month=mese, day=28)
        
        date_cedole.sort() # Ordine cronologico
        
        # Aggiungiamo flussi cedole (tranne l'ultima che va col rimborso)
        for d in date_cedole[:-1]:
            flussi.append({
                "Data": d.strftime("%d/%m/%Y"),
                "Tipo": "🟢 Cedola",
                "Importo Lordo": cedola_valore_lordo,
                "Tasse": -(cedola_valore_lordo - cedola_valore_netto),
                "Importo Netto": cedola_valore_netto,
                "Capitale Cumulato": 0 # Calcolato dopo
            })
            cedola_totale_netta += cedola_valore_netto

    # 3. Rimborso Finale + Ultima Cedola
    ultima_cedola_lorda = (nominale * (dati['ced'] / 100) / freq) if freq > 0 else 0
    ultima_cedola_netta = ultima_cedola_lorda * (1 - (tax_rate/100))
    
    # Calcolo capital gain/loss
    plusvalenza = max(0, nominale - prezzo_acquisto)
    tassa_capital_gain = plusvalenza * (tax_rate/100)
    rimborso_netto = nominale - tassa_capital_gain
    
    totale_finale_netto = rimborso_netto + ultima_cedola_netta
    
    flussi.append({
        "Data": scadenza.strftime("%d/%m/%Y"),
        "Tipo": "🏁 Rimborso + Cedola",
        "Importo Lordo": nominale + ultima_cedola_lorda,
        "Tasse": -(tassa_capital_gain + (ultima_cedola_lorda - ultima_cedola_netta)),
        "Importo Netto": totale_finale_netto,
        "Capitale Cumulato": 0
    })
    
    # Calcolo Cumulato
    df = pd.DataFrame(flussi)
    df['Capitale Cumulato'] = df['Importo Netto'].cumsum()
    return df

def today_plus_2(d):
    return d + timedelta(days=2)

def get_bond_data_protected(isin, category):
    @st.cache_data(ttl=300, show_spinner=False)
    def download_url(url):
        user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36']
        time.sleep(random.uniform(0.4, 0.8))
        return requests.get(url, headers={'User-Agent': random.choice(user_agents)}, timeout=15)

    target_list = SOURCES_MAP.get(category, [])
    for s in target_list:
        try:
            r = download_url(s['url'])
            if r.status_code != 200: continue
            df_list = pd.read_html(r.text, decimal=",", thousands=".")
            for df in df_list:
                col_isin = next((c for c in df.columns if any(k in str(c).lower() for k in ['isin', 'codice'])), None)
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin, na=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        c_pr = next((c for c in df.columns if any(k in str(c).lower() for k in ['prezzo', 'last'])), None)
                        c_sc = next((c for c in df.columns if any(k in str(c).lower() for k in ['scadenza', 'data'])), None)
                        c_de = next((c for c in df.columns if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
                        
                        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
                        sc_str = str(row[c_sc])
                        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
                        except: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
                        desc = str(row[c_de])
                        ced = 0.0
                        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                        if m: ced = float(m.group(1).replace(',', '.'))
                        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": s['freq'], "fonte": s['nome']}
        except: continue
    return None

# --- LOGIN SYSTEM ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

def login():
    st.title("🔐 Accesso Ricerca")
    with st.form("login"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Entra"):
            if u == SEGRETO_UTENTE and p == SEGRETO_PASSWORD:
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("Credenziali non valide")

def main_app():
    st.title("🏛️ Bond Research Terminal")
    st.caption("Advanced Academic Tool for Bond Analysis & Comparison")
    st.markdown("---")

    # --- SIDEBAR (Input Investimento) ---
    with st.sidebar:
        st.header("💶 Simulatore")
        importo = st.number_input("Capitale da investire (€)", value=10000, step=1000)
        st.divider()
        if st.session_state.confronto:
            st.info(f"📌 **In confronto:**\n{st.session_state.confronto['desc'][:15]}...")
            if st.button("❌ Rimuovi Confronto"):
                st.session_state.confronto = None
                st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # --- INPUT RICERCA ---
    st.subheader("🔍 Cerca Titolo")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: cat = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
    with c2: isin = st.text_input("ISIN", placeholder="IT000...").strip().upper()
    with c3: 
        st.write("")
        btn = st.button("ANALIZZA 🚀", use_container_width=True)

    if btn and isin:
        with st.spinner("Elaborazione Dati e Simulazione Fiscale..."):
            d = get_bond_data_protected(isin, cat)
            
            if d:
                # Calcoli Base
                tax = determina_tasse(d['fonte'], d['desc'])
                oggi = date.today()
                valuta = oggi + timedelta(days=2)
                anni = (d['sc'] - valuta).days / 365.25
                t_val = tax / 100
                rend_n = (((100 - d['pr'])*(1-t_val) + (d['ced'] * anni * (1-t_val))) / d['pr']) / anni
                
                # Generazione Flussi
                df_flussi = genera_flussi_cassa(d, importo, tax)
                profitto_netto = df_flussi['Importo Netto'].sum()
                
                # --- LAYOUT RISULTATI ---
                st.success(f"Trovato: **{d['desc']}**")
                
                # Se c'è un confronto attivo, mostriamo la comparazione
                if st.session_state.confronto:
                    st.divider()
                    st.subheader("⚔️ Confronto Diretto")
                    conf = st.session_state.confronto
                    
                    # Ricalcolo dati confronto per sicurezza
                    c_tax = determina_tasse(conf['fonte'], conf['desc'])
                    c_anni = (conf['sc'] - valuta).days / 365.25
                    c_rend_n = (((100 - conf['pr'])*(1-c_tax/100) + (conf['ced'] * c_anni * (1-c_tax/100))) / conf['pr']) / c_anni
                    
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Titolo A (Salvato)", f"{conf['ced']}% Cedola", f"{c_rend_n*100:.2f}% Netto")
                    col_b.metric("VS", "⚡", "")
                    col_c.metric("Titolo B (Attuale)", f"{d['ced']}% Cedola", f"{rend_n*100:.2f}% Netto", delta_color="normal")
                    
                    # Grafico Confronto
                    fig_cmp = go.Figure()
                    fig_cmp.add_trace(go.Bar(name='A (Salvato)', x=['Rendimento Netto'], y=[c_rend_n*100], marker_color='#EF553B'))
                    fig_cmp.add_trace(go.Bar(name='B (Attuale)', x=['Rendimento Netto'], y=[rend_n*100], marker_color='#00CC96'))
                    st.plotly_chart(fig_cmp, use_container_width=True)
                    st.divider()

                # TABS PER DETTAGLI
                tab1, tab2, tab3 = st.tabs(["📊 Analisi & Grafico", "💰 Tabella Flussi Cassa", "⚙️ Azioni"])
                
                with tab1:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Prezzo", f"{d['pr']}€")
                    m2.metric("Rendimento Netto", f"{rend_n*100:.2f}%")
                    m3.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                    m4.metric("Profitto Netto Stimato", f"{profitto_netto:.2f}€", help=f"Su {importo}€ investiti")
                    
                    # Grafico Andamento Capitale
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df_flussi['Data'], 
                        y=df_flussi['Capitale Cumulato'],
                        fill='tozeroy',
                        mode='lines+markers',
                        name='Capitale Netto',
                        line=dict(color='#00CC96')
                    ))
                    fig.update_layout(title=f"Evoluzione dell'Investimento ({importo}€)", template="plotly_dark", height=350)
                    st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    st.subheader(f"Piano Cedolare su {importo}€")
                    st.dataframe(
                        df_flussi[["Data", "Tipo", "Importo Lordo", "Tasse", "Importo Netto"]].style.format({
                            "Importo Lordo": "{:.2f}€", 
                            "Tasse": "{:.2f}€", 
                            "Importo Netto": "{:.2f}€"
                        }), 
                        use_container_width=True
                    )
                    st.caption("Nota: Il calcolo è una stima che assume il mantenimento fino a scadenza.")

                with tab3:
                    st.write("Cosa vuoi fare con questo titolo?")
                    if st.button("📌 Salva per Confronto"):
                        st.session_state.confronto = d
                        st.success("Titolo salvato! Ora cerca un altro titolo per confrontarli.")
                        time.sleep(1)
                        st.rerun()

            else:
                st.error("Titolo non trovato.")
    else:
        st.info("Inserisci un ISIN per iniziare. Esempio BTP: IT0005566408")

if st.session_state.logged_in: main_app()
else: login()
