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
if 'confronto' not in st.session_state: st.session_state.confronto = None 

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
    flussi = []
    nominale = importo_investito
    prezzo_acquisto = (importo_investito * dati['pr']) / 100
    oggi = date.today()
    scadenza = dati['sc']
    freq = dati['freq']
    
    # 1. Acquisto
    flussi.append({
        "Data": oggi.strftime("%d/%m/%Y"),
        "Tipo": "🔴 Acquisto",
        "Importo Netto": -prezzo_acquisto,
        "Cumulato": -prezzo_acquisto
    })
    
    # 2. Cedole
    if freq > 0:
        cedola_pct_annua = dati['ced']
        mesi_step = 12 // freq
        cedola_valore_lordo = (nominale * (cedola_pct_annua / 100)) / freq
        cedola_valore_netto = cedola_valore_lordo * (1 - (tax_rate/100))
        
        cursore_data = scadenza
        date_cedole = []
        while cursore_data > today_plus_2(oggi):
            date_cedole.append(cursore_data)
            anno = cursore_data.year
            mese = cursore_data.month - mesi_step
            if mese <= 0:
                mese += 12
                anno -= 1
            try: cursore_data = cursore_data.replace(year=anno, month=mese)
            except: cursore_data = cursore_data.replace(year=anno, month=mese, day=28)
        
        date_cedole.sort()
        for d in date_cedole[:-1]:
            flussi.append({
                "Data": d.strftime("%d/%m/%Y"),
                "Tipo": "🟢 Cedola",
                "Importo Netto": cedola_valore_netto,
                "Cumulato": 0
            })

    # 3. Rimborso
    ultima_cedola_lorda = (nominale * (dati['ced'] / 100) / freq) if freq > 0 else 0
    ultima_cedola_netta = ultima_cedola_lorda * (1 - (tax_rate/100))
    plusvalenza = max(0, nominale - prezzo_acquisto)
    tassa_capital_gain = plusvalenza * (tax_rate/100)
    rimborso_netto = nominale - tassa_capital_gain
    
    flussi.append({
        "Data": scadenza.strftime("%d/%m/%Y"),
        "Tipo": "🏁 Rimborso",
        "Importo Netto": rimborso_netto + ultima_cedola_netta,
        "Cumulato": 0
    })
    
    df = pd.DataFrame(flussi)
    df['Cumulato'] = df['Importo Netto'].cumsum()
    return df

def today_plus_2(d): return d + timedelta(days=2)

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

# --- LOGIN ---
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
            else: st.error("Credenziali Errate")

# --- APP PRINCIPALE ---
def main_app():
    st.title("🏛️ Bond Research Terminal")
    st.caption("Advanced Academic Tool for Bond Analysis & Comparison")
    st.markdown("---")

    # 1. LEGENDA (Rimesse le 4 colonne come piaceva a te!)
    st.subheader("📍 Guida alla Ricerca")
    
    col_leg1, col_leg2, col_leg3, col_leg4 = st.columns(4)
    with col_leg1:
        st.success("**🏛️ GOVERNATIVI**\n\n*Stati Sovrani*\nBTP, BOT, Bund, Treasury, OAT, Romania...")
    with col_leg2:
        st.warning("**🏦 FINANZIARI**\n\n*Banche & Assicurazioni*\nIntesa, UniCredit, Goldman, Subordinate...")
    with col_leg3:
        st.info("**🏭 CORPORATE**\n\n*Aziende Industriali*\nEni, Stellantis, Telecom, Energy, Auto...")
    with col_leg4:
        st.error("**💎 SPECIALI**\n\n*Strutture Miste*\nZero Coupon, Callable, Green Bonds, 25Y+...")

    st.divider()

    # SIDEBAR
    with st.sidebar:
        st.header("💶 Simulatore")
        importo = st.number_input("Capitale Investito (€)", value=10000, step=1000)
        st.divider()
        if st.session_state.confronto:
            st.info(f"📌 **VS:** {st.session_state.confronto['desc'][:15]}...")
            if st.button("❌ Rimuovi Confronto"):
                st.session_state.confronto = None
                st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

    # INPUT
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: cat = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
    with c2: isin = st.text_input("ISIN", placeholder="IT000...").strip().upper()
    with c3: 
        st.write("")
        btn = st.button("ANALIZZA 🚀", use_container_width=True)

    # RISULTATI
    if btn and isin:
        with st.spinner("Analisi in corso..."):
            d = get_bond_data_protected(isin, cat)
            if d:
                # Calcoli
                tax = determina_tasse(d['fonte'], d['desc'])
                t_val = tax / 100
                oggi = date.today()
                valuta = oggi + timedelta(days=2)
                anni = (d['sc'] - valuta).days / 365.25
                rend_n = (((100 - d['pr'])*(1-t_val) + (d['ced'] * anni * (1-t_val))) / d['pr']) / anni
                df_flussi = genera_flussi_cassa(d, importo, tax)
                profitto = df_flussi['Importo Netto'].sum() - importo

                # Confronto
                if st.session_state.confronto:
                    st.divider()
                    st.subheader("⚔️ Confronto")
                    conf = st.session_state.confronto
                    c_tax = determina_tasse(conf['fonte'], conf['desc'])
                    c_anni = (conf['sc'] - valuta).days / 365.25
                    c_rend = (((100 - conf['pr'])*(1-c_tax/100) + (conf['ced'] * c_anni * (1-c_tax/100))) / conf['pr']) / c_anni
                    
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("TITOLO A (Salvato)", f"{c_rend*100:.2f}% Netto")
                    cc2.metric("VS", "⚡")
                    cc3.metric("TITOLO B (Attuale)", f"{rend_n*100:.2f}% Netto", delta_color="normal")
                    st.divider()

                st.success(f"Trovato: **{d['desc']}**")

                # Tabs Dettagli
                t1, t2, t3 = st.tabs(["📊 Analisi", "💰 Flussi Cassa", "⚙️ Azioni"])
                
                with t1:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Prezzo", f"{d['pr']}€")
                    m2.metric("Rend. Netto", f"{rend_n*100:.2f}%")
                    m3.metric("Scadenza", d['sc'].strftime('%d/%m/%Y'))
                    m4.metric("Profitto Stimato", f"{profitto:.2f}€")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_flussi['Data'], y=df_flussi['Cumulato'], fill='tozeroy', mode='lines+markers', line=dict(color='#00CC96')))
                    fig.update_layout(title=f"Crescita Capitale su {importo}€", template="plotly_dark", height=300)
                    st.plotly_chart(fig, use_container_width=True)

                with t2:
                    st.dataframe(df_flussi.style.format({"Importo Netto": "{:.2f}€", "Cumulato": "{:.2f}€"}), use_container_width=True)

                with t3:
                    if st.button("📌 Salva per Confronto"):
                        st.session_state.confronto = d
                        st.success("Salvato! Cerca un altro titolo.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("Non trovato. Controlla Categoria e ISIN.")

if st.session_state.logged_in: main_app()
else: login()
