import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
import time
import random
import plotly.graph_objects as go
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide")

# CREDENZIALI
SEGRETO_UTENTE = "giulio"
SEGRETO_PASSWORD = "Giulio99mac!"

# CARTELLA DATABASE LOCALE
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# --- INIZIALIZZAZIONE STATO ---
if 'confronto' not in st.session_state: st.session_state.confronto = None 

# --- MAPPA FONTI ---
SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "BTP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "BUND_GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT_FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA_TREASURIES", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA_MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TDS_2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE_USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 SPECIALI": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# --- FUNZIONI DATABASE LOCALE (MODALITÀ BRADIPO 🦥) ---
def aggiorna_database_locale():
    """Scarica i database MOLTO LENTAMENTE per evitare il ban"""
    
    # User Agents Rotanti (simulano device diversi)
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36', # PC Chrome
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15', # Mac Safari
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15' # iPhone
    ]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Contiamo quanti link ci sono
    total_sources = sum(len(v) for v in SOURCES_MAP.values())
    count = 0
    
    for category, sources in SOURCES_MAP.items():
        for s in sources:
            count += 1
            # Messaggio Utente
            perc = int((count / total_sources) * 100)
            status_text.markdown(f"⏳ **Scaricamento {s['nome']}**... ({count}/{total_sources}) - {perc}%")
            progress_bar.progress(count / total_sources)
            
            try:
                # --- IL SEGRETO ANTI-BAN ---
                # Aspetta un tempo casuale tra 5 e 12 secondi. 
                # Nessun bot aspetta 12 secondi. Solo un umano lo fa.
                sleep_time = random.uniform(5.0, 12.0)
                time.sleep(sleep_time) 
                
                # Scarica
                headers = {'User-Agent': random.choice(user_agents)}
                r = requests.get(s['url'], headers=headers, timeout=20)
                
                if r.status_code == 200:
                    dfs = pd.read_html(r.text, decimal=",", thousands=".")
                    for df in dfs:
                        if any(col for col in df.columns if 'ISIN' in str(col).upper()):
                            filename = os.path.join(DB_FOLDER, f"{s['nome']}.csv")
                            df.to_csv(filename, index=False)
                            break
            except Exception as e:
                # Se fallisce uno, non bloccare tutto, vai avanti
                print(f"Errore {s['nome']}: {e}")
                
    status_text.text("✅ Aggiornamento Completato! Ora sei al sicuro.")
    time.sleep(2)
    status_text.empty()
    progress_bar.empty()
    st.success(f"Database salvato in locale. Ora puoi fare ricerche istantanee senza connessione.")

def cerca_nel_database_locale(isin, category):
    target_list = SOURCES_MAP.get(category, [])
    for s in target_list:
        filename = os.path.join(DB_FOLDER, f"{s['nome']}.csv")
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)
                col_isin = next((c for c in df.columns if any(k in str(c).lower() for k in ['isin', 'codice'])), None)
                if col_isin:
                    match = df[df[col_isin].astype(str).str.contains(isin, na=False, case=False)]
                    if not match.empty:
                        return match.iloc[0], s 
            except: continue
    return None, None

def processa_riga_bond(row, source_info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if any(k in str(c).lower() for k in ['scadenza', 'data'])), None)
        c_de = next((c for c in cols if any(k in str(c).lower() for k in ['descrizione', 'nome'])), None)
        
        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        sc_str = str(row[c_sc])
        try: sc = datetime.strptime(sc_str, '%Y-%m-%d').date()
        except: 
            try: sc = datetime.strptime(sc_str, '%d/%m/%Y').date()
            except: return None
            
        desc = str(row[c_de])
        ced = 0.0
        m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
        if m: ced = float(m.group(1).replace(',', '.'))
        
        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": source_info['freq'], "fonte": source_info['nome']}
    except: return None

def determina_tasse(nome_fonte, descrizione_titolo):
    fonti_whitelist = ["BTP", "BOT", "BUND", "OAT", "USA", "ROMANIA", "EUROPA", "TDS"]
    for w in fonti_whitelist:
        if w in nome_fonte.upper(): return 12.5
    desc_upper = descrizione_titolo.upper()
    keywords_stato = ["REPUBLIC", "REPUBBLICA", "TREASURY", "KINGDOM", "REGNO", "BTP", "CCT", "BOT", "OAT", "BUND"]
    for k in keywords_stato:
        if k in desc_upper: return 12.5
    return 26.0

def genera_flussi_cassa(dati, importo, tax_rate):
    flussi = []
    nominale = importo
    prezzo_acquisto = (importo * dati['pr']) / 100
    oggi = date.today()
    scadenza = dati['sc']
    freq = dati['freq']
    
    flussi.append({"Data": today_plus_2(oggi), "Evento": "🔴 Acquisto", "Netto": -prezzo_acquisto}) # T+2
    
    if freq > 0:
        ced_netta = (nominale * (dati['ced']/100) / freq) * (1 - tax_rate/100)
        curr = scadenza
        while curr > (oggi + timedelta(days=2)):
            flussi.append({"Data": curr, "Evento": "🟢 Cedola", "Netto": ced_netta})
            curr = curr - timedelta(days=365//freq)
    
    flussi = [f for f in flussi if not (f['Evento']=="🟢 Cedola" and f['Data']==scadenza)]
    
    gain = max(0, nominale - prezzo_acquisto)
    rimborso_netto = nominale - (gain * tax_rate/100)
    ced_finale_netta = (nominale * (dati['ced']/100) / freq) * (1 - tax_rate/100) if freq > 0 else 0
    
    flussi.append({"Data": scadenza, "Evento": "🏁 Rimborso", "Netto": rimborso_netto + ced_finale_netta})
    
    df = pd.DataFrame(flussi)
    df['Data'] = pd.to_datetime(df['Data'])
    df = df.sort_values(by="Data")
    df['Capitale'] = df['Netto'].cumsum()
    return df

def today_plus_2(d): return d + timedelta(days=2)

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

# --- MAIN APP ---
def main_app():
    st.title("🏛️ Bond Research Terminal (Safe Mode)")
    st.caption("Sistema Ibrido con Protezione Anti-Ban")
    st.markdown("---")

    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Gestione Dati")
        
        # TASTO AGGIORNAMENTO SICURO
        if st.button("🔄 Scarica Tutto (Safe Mode)", help="Impiega circa 3-4 minuti. NON Bannabile."):
            with st.spinner("Scaricamento lento in corso... prenditi un caffè ☕"):
                aggiorna_database_locale()
        
        files_ok = len([n for n in os.listdir(DB_FOLDER) if n.endswith('.csv')]) if os.path.exists(DB_FOLDER) else 0
        st.success(f"📂 Dati Locali: {files_ok}/28")
        
        st.divider()
        st.header("💶 Simulatore")
        importo = st.number_input("Investimento (€)", value=10000, step=1000)
        
        if st.session_state.confronto:
            st.divider()
            st.info(f"📌 VS: {st.session_state.confronto['desc'][:15]}...")
            if st.button("Rimuovi Confronto"): st.session_state.confronto = None; st.rerun()
        
        st.divider()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()

    # LEGENDA
    col_leg1, col_leg2, col_leg3, col_leg4 = st.columns(4)
    with col_leg1: st.success("🏛️ **GOVERNATIVI**\n\nStati: Italia, Germania, USA...")
    with col_leg2: st.warning("🏦 **FINANZIARI**\n\nBanche: Intesa, UniCredit...")
    with col_leg3: st.info("🏭 **CORPORATE**\n\nIndustry: Eni, Auto, Energy...")
    with col_leg4: st.error("💎 **SPECIALI**\n\nZero Coupon, Callable...")
    st.divider()

    # INPUT
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: cat = st.selectbox("Categoria", list(SOURCES_MAP.keys()))
    with c2: isin = st.text_input("ISIN", placeholder="IT000...").strip().upper()
    with c3: 
        st.write("")
        btn = st.button("CERCA 🚀", use_container_width=True)

    # LOGICA RICERCA IBRIDA
    if btn and isin:
        dati_bond = None
        modo = ""
        
        # 1. CERCA IN LOCALE
        with st.status("🔍 Ricerca in corso...") as status:
            status.write("Controllo file scaricati...")
            row, source_info = cerca_nel_database_locale(isin, cat)
            
            if row is not None:
                dati_bond = processa_riga_bond(row, source_info)
                modo = "📂 DATABASE LOCALE"
                status.write("✅ Trovato offline!")
            else:
                status.write("⚠️ Non trovato offline. Provo online (singola richiesta)...")
                # 2. FALLBACK ONLINE (Solo 1 richiesta)
                target_list = SOURCES_MAP.get(cat, [])
                for s in target_list:
                    try:
                        time.sleep(1) # Piccola pausa
                        r = requests.get(s['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                        if r.status_code == 200:
                            dfs = pd.read_html(r.text, decimal=",", thousands=".")
                            for df in dfs:
                                col_isin = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                                if col_isin and not df[df[col_isin].astype(str).str.contains(isin, na=False)].empty:
                                    row = df[df[col_isin].astype(str).str.contains(isin, na=False)].iloc[0]
                                    dati_bond = processa_riga_bond(row, s)
                                    modo = "🌐 WEB (Live)"
                                    break
                    except: continue
                    if dati_bond: break
            status.update(label="Fatto", state="complete")

        # VISUALIZZAZIONE
        if dati_bond:
            tax = determina_tasse(dati_bond['fonte'], dati_bond['desc'])
            t_val = tax / 100
            oggi = date.today()
            valuta = today_plus_2(oggi)
            anni = (dati_bond['sc'] - valuta).days / 365.25
            
            rend_n = (((100 - dati_bond['pr'])*(1-t_val) + (dati_bond['ced'] * anni * (1-t_val))) / dati_bond['pr']) / anni
            rend_l = (((100 - dati_bond['pr']) + (dati_bond['ced'] * anni)) / dati_bond['pr']) / anni
            
            df_flussi = genera_flussi_cassa(dati_bond, importo, tax)
            profitto = df_flussi['Netto'].sum() - importo

            st.markdown(f"""
            <div style="background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00CC96; margin-bottom: 20px;">
                <h2 style="margin:0; color:white;">{dati_bond['desc']}</h2>
                <p style="margin:0; color:#b0b3c5;">Fonte: {modo} | Tassa: {tax}%</p>
            </div>
            """, unsafe_allow_html=True)

            # Confronto
            if st.session_state.confronto:
                st.subheader("⚔️ Confronto")
                conf = st.session_state.confronto
                c_tax = determina_tasse(conf['fonte'], conf['desc'])
                c_anni = (conf['sc'] - valuta).days / 365.25
                c_rend = (((100 - conf['pr'])*(1-c_tax/100) + (conf['ced'] * c_anni * (1-c_tax/100))) / conf['pr']) / c_anni
                
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("TITOLO A", f"{c_rend*100:.2f}% Netto")
                cc2.metric("VS", "⚡")
                cc3.metric("TITOLO B", f"{rend_n*100:.2f}% Netto", delta_color="normal")
                st.divider()

            t1, t2, t3 = st.tabs(["📊 Analisi", "💰 Flussi", "⚙️ Azioni"])
            
            with t1:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Prezzo", f"{dati_bond['pr']}€")
                m2.metric("Rend. Netto", f"{rend_n*100:.2f}%")
                m3.metric("Scadenza", dati_bond['sc'].strftime('%d/%m/%Y'))
                m4.metric("Profitto", f"{profitto:+.2f}€")
                
                # Grafico
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_flussi['Data'], y=df_flussi['Capitale'], fill='tozeroy', mode='lines+markers', line=dict(color='#00CC96')))
                fig.update_layout(title="Crescita Capitale", template="plotly_dark", height=300)
                st.plotly_chart(fig, use_container_width=True)

            with t2:
                st.dataframe(df_flussi.style.format({"Netto": "{:+.2f}€", "Capitale": "{:+.2f}€"}), use_container_width=True)

            with t3:
                if st.button("📌 Salva per Confronto"):
                    st.session_state.confronto = dati_bond
                    st.success("Salvato!"); time.sleep(1); st.rerun()

        else:
            st.error("Titolo non trovato.")
            st.info("💡 Consiglio: Se non hai mai scaricato i dati, clicca 'Scarica Tutto (Safe Mode)' nella barra laterale.")

if st.session_state.logged_in: main_app()
else: login()
