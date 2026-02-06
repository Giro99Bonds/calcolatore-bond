import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
from scipy import optimize

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Bond Club Pro", page_icon="🎯", layout="wide")

if 'access_granted' not in st.session_state: st.session_state.access_granted = False
if 'portfolio' not in st.session_state: st.session_state.portfolio = [] 

# --- FUNZIONI ---
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

# --- MAPPA DELLE FONTI ---
# Qui associamo le etichette del menu ai link reali
SOURCES_MAP = {
    "🇮🇹 BTP & Italia": [
        {"nome": "BTP (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT (Italia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0}
    ],
    "🇪🇺 Stati Europa (Bund/OAT/Ecc)": [
        {"nome": "BUND (Germania)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT (Francia)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇺🇸 USA & Globali": [
        {"nome": "USA (Treasuries)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "GLOBALI (Emergenti)", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_globali&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Banche (Senior & Sub)": [
        {"nome": "BANCHE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE EUROPEE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Corporate (Aziende)": [
        {"nome": "CORPORATE ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORPORATE GENERALE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🦁 Emittenti Specifici": [
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Speciali (Zero Coupon/Green/Lunghi)": [
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "GREEN BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ULTRA LUNGHI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

def get_bond_data(isin_code, category_key):
    # Seleziona solo le fonti della categoria scelta
    if category_key == "🌍 CERCA OVUNQUE (Lento!)":
        target_sources = [s for sublist in SOURCES_MAP.values() for s in sublist] # Appiattisce tutto
    else:
        target_sources = SOURCES_MAP[category_key]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def trova_colonna(df, keywords):
        for col in df.columns:
            for key in keywords:
                if key.lower() in col.lower(): return col
        return None

    for source in target_sources:
        try:
            r = requests.get(source["url"], headers=headers, timeout=10)
            if r.status_code != 200: continue
            
            try:
                df_list = pd.read_html(r.content, decimal=",", thousands=".")
            except:
                continue

            for df in df_list:
                col_isin = trova_colonna(df, ['isin', 'codice'])
                if col_isin:
                    match = df[df[col_isin] == isin_code]
                    if not match.empty:
                        row = match.iloc[0]
                        
                        col_prezzo = trova_colonna(df, ['prezzo', 'price', 'last', 'quotazione'])
                        col_scadenza = trova_colonna(df, ['scadenza', 'maturity', 'date'])
                        col_desc = trova_colonna(df, ['descrizione', 'nome'])
                        col_divisa = trova_colonna(df, ['divisa', 'curr', 'valuta'])
                        
                        if not col_prezzo or not col_scadenza: continue

                        try:
                            pr_str = str(row[col_prezzo]).replace(',', '.').replace('€', '').strip()
                            pr = float(pr_str)
                            
                            scad_str = str(row[col_scadenza])
                            try: scad = datetime.strptime(scad_str, '%Y-%m-%d').date()
                            except: scad = datetime.strptime(scad_str, '%d/%m/%Y').date()
                            
                            desc = row[col_desc] if col_desc else "N/A"
                            val = row[col_divisa] if col_divisa else "EUR"
                            
                            ced = 0.0
                            if source["freq"] > 0:
                                m = re.search(r'(\d+(?:[.,]\d+)?)%', desc)
                                if m: ced = float(m.group(1).replace(',', '.'))
                            
                            return {"source": source["nome"], "freq": source["freq"], "valuta": val,
                                    "prezzo": pr, "scadenza": scad, "cedola": ced, "desc": desc}
                        except: continue
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

# --- GATEKEEPER ---
if not st.session_state.access_granted:
    st.markdown("<h1 style='text-align: center; color: red;'>⛔ AREA RISERVATA ⛔</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h3 style='text-align: center;'>SEI UN TOSSICO? 💊</h3>", unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        if b1.button("SÌ, SONO DIPENDENTE", use_container_width=True):
            st.session_state.access_granted = True
            st.rerun()
        if b2.button("NO, STO BENE", use_container_width=True):
            st.stop()

else:
    with st.sidebar:
        st.title("Menu Bond Club")
        page = st.radio("Sezione:", ["🔎 Analisi & Scelta", "💼 Portafoglio"])
        st.divider()
        if st.button("Esci"):
            st.session_state.access_granted = False
            st.rerun()

    if page == "🔎 Analisi & Scelta":
        st.title("🔎 Scanner Intelligente")
        st.write("Scegli dove cercare per evitare blocchi e lunghe attese.")

        # --- SELETTORE CATEGORIA ---
        categorie = list(SOURCES_MAP.keys()) + ["🌍 CERCA OVUNQUE (Lento!)"]
        scelta_cat = st.selectbox("1. Dove devo cercare?", options=categorie, index=0)

        c1, c2, c3 = st.columns([2, 1, 1])
        isin_input = c1.text_input("2. Inserisci ISIN", placeholder="Es. IT000...", key="s_isin").strip().upper()
        tax = c2.selectbox("3. Tasse", [12.5, 26.0], format_func=lambda x: f"{x}%", key="s_tax")
        
        c3.write("")
        c3.write("")
        
        if c3.button("TROVA ORA 🚀", use_container_width=True) and isin_input:
            
            with st.spinner(f"Sto cercando in: {scelta_cat}..."):
                dati = get_bond_data(isin_input, scelta_cat)
                
                if dati:
                    res = calcola_metriche(dati, tax/100)
                    
                    st.success(f"Trovato: {dati['desc']}")
                    st.caption(f"Fonte: {dati['source']}")
                    
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Prezzo", f"{dati['prezzo']} {dati['valuta']}")
                    k2.metric("Rendimento Netto", f"{res['tir_netto']*100:.2f}%")
                    k3.metric("Scadenza", f"{dati['scadenza'].strftime('%d/%m/%Y')}")
                    
                    # Avvisi
                    if "SUBORDINATE" in dati['source']: st.error("⚠️ SUBORDINATO")
                    if "CALLABLE" in dati['source']: st.warning("📞 CALLABLE")
                    if dati['valuta'] != "EUR": st.warning(f"💱 Valuta {dati['valuta']}")
                    
                else:
                    st.error("❌ Non trovato in questa categoria.")
                    st.info("Prova a cambiare categoria nel menu in alto o controlla l'ISIN.")

    elif page == "💼 Portafoglio":
        st.title("💼 Gestione Portafoglio")
        with st.expander("Aggiungi Titolo Manualmente o da Ricerca", expanded=True):
            pc1, pc2, pc3 = st.columns(3)
            p_isin = pc1.text_input("ISIN", key="p_isin").strip().upper()
            p_nom = pc2.number_input("Nominale", 1000, step=1000)
            p_cat = pc3.selectbox("Categoria Ricerca", options=list(SOURCES_MAP.keys()), key="p_cat")
            
            if st.button("Aggiungi al Portafoglio"):
                d = get_bond_data(p_isin, p_cat)
                if d:
                    m = calcola_metriche(d, 0.125) # Default 12.5, modificabile
                    val_mercato = (p_nom * d['prezzo']) / 100
                    st.session_state.portfolio.append({
                        "ISIN": p_isin, "Nome": d['desc'], "Nominale": p_nom,
                        "Prezzo": d['prezzo'], "Valore": val_mercato, "Netto%": m['tir_netto']*100
                    })
                    st.success("Aggiunto!")
                else:
                    st.error("Non trovato.")
        
        if st.session_state.portfolio:
            df = pd.DataFrame(st.session_state.portfolio)
            st.dataframe(df)
            tot = df["Valore"].sum()
            if tot > 0:
                media = (df["Netto%"] * (df["Valore"]/tot)).sum()
                st.metric("Rendimento Portafoglio", f"{media:.2f}%", f"Tot: € {tot:,.2f}")
            
            if st.button("Reset"):
                st.session_state.portfolio = []
                st.rerun()
