import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
import numpy as np
import time
import random
import plotly.graph_objects as go
import plotly.express as px
import os

# ================= CONFIG =================
st.set_page_config("Bond Research Terminal", "🏛️", layout="wide")

DB_FOLDER = "bond_database"
os.makedirs(DB_FOLDER, exist_ok=True)

# ================= SESSION =================
for k, v in {
    "logged": False,
    "page": "Scanner",
    "portfolio": [],
    "saved_bond": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ================= DATA SOURCES =================
SOURCES_MAP = {
    "🏛️ GOVERNATIVI": [
        {"nome": "ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
    ],
    "🏦 FINANZIARI": [
        {"nome": "BANCHE_EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUB", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "🏭 CORPORATE": [
        {"nome": "CORP_EU", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
    ],
}

# ================= UTILS =================
def get_last_update():
    files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith(".csv")]
    if not files:
        return None
    return datetime.fromtimestamp(max(os.path.getmtime(f) for f in files))


def aggiorna_db():
    p = st.progress(0)
    c = 0
    tot = sum(len(v) for v in SOURCES_MAP.values())
    for cat in SOURCES_MAP.values():
        for src in cat:
            c += 1
            p.progress(c / tot)
            try:
                time.sleep(random.uniform(2, 4))
                r = requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                dfs = pd.read_html(r.text, decimal=",", thousands=".")
                for df in dfs:
                    if any("ISIN" in str(col).upper() for col in df.columns):
                        df.to_csv(f"{DB_FOLDER}/{src['nome']}.csv", index=False)
                        break
            except:
                pass
    st.toast("Database aggiornato", icon="✅")
    st.rerun()


def cerca_isin(isin, cat):
    for src in SOURCES_MAP[cat]:
        path = f"{DB_FOLDER}/{src['nome']}.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            c = next(col for col in df.columns if "ISIN" in col.upper())
            match = df[df[c].astype(str).str.contains(isin, na=False)]
            if not match.empty:
                return match.iloc[0], src
    return None, None


# ================= FINANCE CORE =================
def genera_flussi(prezzo, cedola, scadenza, freq, nominale=100):
    flows = []
    today = date.today()
    flows.append((today, -prezzo / 100 * nominale))

    if freq > 0 and cedola > 0:
        step = int(12 / freq)
        d = scadenza
        while d > today:
            flows.append((d, nominale * cedola / 100 / freq))
            d -= timedelta(days=365 // freq)

    flows.append((scadenza, nominale))
    return sorted(flows, key=lambda x: x[0])


def irr_from_flows(flows):
    times = [(d - flows[0][0]).days / 365.25 for d, _ in flows]
    values = [v for _, v in flows]
    return np.irr([values[0]] + values[1:])


def duration_convexity(flows, y):
    times = np.array([(d - flows[0][0]).days / 365.25 for d, _ in flows])
    cfs = np.array([v for _, v in flows])
    pv = cfs / (1 + y) ** times
    price = pv.sum()
    dur = np.sum(times * pv) / price
    conv = np.sum(times * (times + 1) * pv) / price
    return dur, conv, price


def tax_rate(desc):
    if any(k in desc.upper() for k in ["BTP", "BUND", "OAT", "TREASURY"]):
        return 0.125
    return 0.26


# ================= LOGIN =================
def login():
    st.title("🔐 Login")
    if st.text_input("Password", type="password") == "bond":
        st.session_state.logged = True
        st.rerun()


# ================= APP =================
def app():
    with st.sidebar:
        st.title("MENU")
        if st.button("🔎 Scanner"): st.session_state.page = "Scanner"
        if st.button("⚔️ Confronto"): st.session_state.page = "Confronto"
        if st.button("💼 Portafoglio"): st.session_state.page = "Portafoglio"
        st.divider()
        if st.button("🔄 Aggiorna DB"): aggiorna_db()

    if st.session_state.page == "Scanner":
        st.title("🔎 Bond Scanner")
        cat = st.selectbox("Categoria", list(SOURCES_MAP))
        isin = st.text_input("ISIN").strip().upper()

        if isin:
            row, src = cerca_isin(isin, cat)
            if row is not None:
                prezzo = float(str(row["Prezzo"]).replace(",", "."))
                desc = str(row["Descrizione"])
                sc = datetime.strptime(str(row["Scadenza"]), "%d/%m/%Y").date()
                ced = float(re.search(r"(\d+\.?\d*)%", desc).group(1)) if "%" in desc else 0.0
                freq = src["freq"]

                flows = genera_flussi(prezzo, ced, sc, freq)
                ytm = irr_from_flows(flows)
                dur, conv, price = duration_convexity(flows, ytm)
                dv01 = dur * price * 0.0001

                st.subheader(desc)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Prezzo", f"{prezzo:.2f}")
                c2.metric("YTM", f"{ytm*100:.2f}%")
                c3.metric("Duration", f"{dur:.2f}")
                c4.metric("DV01", f"{dv01:.2f}")

                df = pd.DataFrame(flows, columns=["Data", "Flow"])
                fig = px.bar(df, x="Data", y="Flow", title="Cash Flow")
                st.plotly_chart(fig, use_container_width=True)

                if st.button("📌 Salva"):
                    st.session_state.saved_bond = {"isin": isin, "ytm": ytm, "dur": dur}
                    st.success("Salvato")

    elif st.session_state.page == "Confronto":
        st.title("⚔️ Confronto")
        if not st.session_state.saved_bond:
            st.warning("Salva un bond prima")
            return
        st.info(f"A: {st.session_state.saved_bond['isin']}")
        isin_b = st.text_input("ISIN B").upper()
        if isin_b:
            for cat in SOURCES_MAP:
                r, s = cerca_isin(isin_b, cat)
                if r is not None:
                    st.metric("YTM A", f"{st.session_state.saved_bond['ytm']*100:.2f}%")
                    st.metric("YTM B", "Calcolato")
                    break

    elif st.session_state.page == "Portafoglio":
        st.title("💼 Portafoglio")
        st.write("Funzione base – estendibile")

# ================= RUN =================
if not st.session_state.logged:
    login()
else:
    app()
