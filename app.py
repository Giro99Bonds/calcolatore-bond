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
import shutil
import logging
import calendar
from io import StringIO
from dataclasses import dataclass
from typing import Optional
from scipy.optimize import brentq
import hashlib
import yfinance as yf
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger("bond_terminal")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ============================================================
# 1. PAGE CONFIG & CSS
# ============================================================
st.set_page_config(page_title="Bond Research Terminal", page_icon="🏛️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card { background-color: #1e2130; padding: 15px; border-radius: 8px; border: 1px solid #3e445b; margin-bottom: 10px; color: #fff !important; }
    .cat-card { padding: 15px; border-radius: 10px; margin-bottom: 10px; height: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: white; }
    .cat-title { font-weight: bold; font-size: 18px; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; }
    .cat-desc { font-size: 14px; opacity: 0.95; margin-bottom: 8px; line-height: 1.4; }
    .cat-meta { font-size: 12px; font-weight: bold; background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
    .bg-gov { background: linear-gradient(135deg, #1a4a2e 0%, #28a745 100%); }
    .bg-bank { background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); }
    .bg-corp { background: linear-gradient(135deg, #1e3a5f 0%, #17a2b8 100%); }
    .bg-spec { background: linear-gradient(135deg, #581845 0%, #d63384 100%); }
    .receipt-box { border-radius: 8px; padding: 15px; margin-bottom: 10px; background-color: rgba(255,255,255,0.02); }
    .receipt-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 14px; }
    .receipt-total { display: flex; justify-content: space-between; font-size: 16px; font-weight: bold; margin-top: 10px; padding-top: 10px; border-top: 1px solid #444; }
    .user-box { padding: 10px; background-color: rgba(0,204,150,0.1); border-left: 5px solid #00CC96; border-radius: 5px; margin-bottom: 20px; font-weight: bold; }
    [data-testid="stSidebar"] div.stButton > button { background-color: transparent; border: none; text-align: left; color: inherit !important; font-weight: 600; }
    [data-testid="stSidebar"] div.stButton > button:hover { padding-left: 10px; background-color: rgba(128,128,128,0.1); border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 2. AUTH & PERSISTENCE
# ============================================================
SECRET_KEY = os.environ.get("BOND_TERMINAL_SECRET", "change-me-in-production-please")

UTENTI_IN_CHIARO = {"giulio": "Giulio99mac!", "guest": "mifumoleboix"}
UTENTI_ABILITATI = {u: hashlib.sha256(p.encode()).hexdigest() for u, p in UTENTI_IN_CHIARO.items()}

DB_FOLDER = "bond_database"
TMP_FOLDER = "bond_database_tmp"
os.makedirs(DB_FOLDER, exist_ok=True)


def make_session_token(user: str) -> str:
    return hashlib.sha256(f"{user}|{SECRET_KEY}".encode()).hexdigest()


def verify_session_token(token: str) -> Optional[str]:
    for user in UTENTI_ABILITATI:
        if make_session_token(user) == token:
            return user
    return None


def init_session_state():
    qp = st.query_params
    token = qp.get("session", None)
    defaults = {
        'portfolio': [], 'alerts': [], 'connection_status': "In attesa...",
        'page': "Scanner", 'last_scrape_time': None, 'patrimonio': 50000.0,
        'selected_isin_from_chart': None, 'last_scrape_results': []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if 'logged_in' not in st.session_state:
        found = verify_session_token(token) if token else None
        st.session_state.logged_in = bool(found)
        st.session_state.current_user = found or ""


init_session_state()

# ============================================================
# 3. SOURCES MAP
# ============================================================
SOURCES_MAP = {
    "GOV_IT": [
        {"nome": "BTP_FISSI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BTP_ITALIA_INF", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=btpitalia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CCT_VARIABILI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cct&yieldtype=G&timescale=DUR", "freq": 2},
    ],
    "GOV_EU": [
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUSTRIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=austria&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BELGIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=belgio&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OLANDA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=olanda&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "GOV_PERIF": [
        {"nome": "SPAGNA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=spagna&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "PORTOGALLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=portogallo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ALTRI_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "GOV_WORLD": [
        {"nome": "USA_TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TURCHIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=turchia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BRASILE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=brasile&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNGHERIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=ungheria&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "SUPRA": [
        {"nome": "EU_BEI_ESM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovranazionali&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbonds&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "BANCHE": [
        {"nome": "BANCHE_SENIOR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SUBORDINATE_TIER2", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ASSICURATIVI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=assicurazioni&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "CORP": [
        {"nome": "CORP_IG_EUROPE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "HIGH_YIELD_EUR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=highyield&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
    ],
    "SPEC": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "LUNGHI_25Y", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR", "freq": 1},
    ],
}

MACRO_CATEGORIES = {
    "🌐 TUTTE": [],
    "🏛️ GOVERNATIVI": ["GOV_IT", "GOV_EU", "GOV_PERIF", "GOV_WORLD", "SUPRA"],
    "🏦 BANCARI": ["BANCHE"],
    "🏭 CORPORATE": ["CORP"],
    "💎 SPECIALI": ["SPEC"],
}

# ============================================================
# 4. PURE MATH FUNCTIONS (UNIT-TESTABLE)
# ============================================================
def years_to_maturity(settlement: date, maturity: date) -> float:
    return max((maturity - settlement).days / 365.25, 0.0)


def ytm_from_price(price: float, coupon_pct: float, maturity: date,
                   freq: int = 1, settlement: Optional[date] = None,
                   face: float = 100.0) -> Optional[float]:
    """YTM via brentq solver. Returns decimal (0.0345 = 3.45%) or None."""
    if price <= 0 or face <= 0:
        return None
    if settlement is None:
        settlement = date.today()
    if maturity <= settlement:
        return None
    if freq <= 0:
        freq = 1

    years = years_to_maturity(settlement, maturity)
    n = max(1, int(round(years * freq)))
    c = (coupon_pct / 100.0) * face / freq

    def npv(y):
        if y <= -0.999:
            return float("inf")
        df = 1.0 + y / freq
        return sum(c / df**t for t in range(1, n + 1)) + face / df**n - price

    try:
        return brentq(npv, -0.49, 2.0, maxiter=100, xtol=1e-8)
    except (ValueError, RuntimeError):
        return None


def macaulay_and_modified_duration(price, coupon_pct, maturity, freq=1, settlement=None, face=100.0):
    if settlement is None:
        settlement = date.today()
    y = ytm_from_price(price, coupon_pct, maturity, freq, settlement, face)
    if y is None:
        return None, None
    if freq <= 0:
        freq = 1

    years = years_to_maturity(settlement, maturity)
    n = max(1, int(round(years * freq)))
    c = (coupon_pct / 100.0) * face / freq
    df = 1.0 + y / freq

    weighted = pv_total = 0.0
    for t in range(1, n + 1):
        cf = c + (face if t == n else 0.0)
        pv = cf / df**t
        weighted += (t / freq) * pv
        pv_total += pv

    if pv_total <= 0:
        return None, None
    mac = weighted / pv_total
    return mac, mac / df


def coupon_dates(maturity: date, freq: int, settlement: date):
    if freq <= 0:
        return settlement, maturity
    months_step = 12 // freq
    next_c = maturity
    target_day = maturity.day
    while next_c > settlement:
        prev = next_c
        y = prev.year
        m = prev.month - months_step
        while m <= 0:
            m += 12
            y -= 1
        last_day = calendar.monthrange(y, m)[1]
        next_c = date(y, m, min(target_day, last_day))
        if next_c <= settlement:
            return next_c, prev
    return next_c, maturity


def calcola_rendimento_grezzo(prezzo, cedola_pct, scadenza, freq=1):
    """Gross YTM as % (e.g. 3.45). Falls back to simple yield if solver fails."""
    y = ytm_from_price(prezzo, cedola_pct, scadenza, freq)
    if y is not None:
        return y * 100
    years = max((scadenza - date.today()).days / 365.25, 0.01)
    if prezzo <= 0:
        return 0.0
    return ((cedola_pct + (100 - prezzo) / years) / ((100 + prezzo) / 2)) * 100


def calcola_metriche_rischio(prezzo, cedola_pct, scadenza, freq):
    y = ytm_from_price(prezzo, cedola_pct, scadenza, freq)
    if y is None:
        return {"ytm": 0.0, "mod_dur": 0.0}
    _, mod = macaulay_and_modified_duration(prezzo, cedola_pct, scadenza, freq)
    return {"ytm": y * 100, "mod_dur": mod or 0.0}


def determina_tasse(nome, desc):
    keys = ["BTP", "BOT", "BUND", "OAT", "USA", "TREASURY", "BEI", "EU ", "ROMANIA", "UNGHERIA", "TURCHIA", "REPUBBLICA", "SCHATZ", "BOBL", "FRANCE", "SPAIN", "BONOS", "T-NOTE", "T-BOND", "EIB", "EBRD", "WORLD BANK", "KFW", "IADB", "HUNGARY", "POLAND"]
    s = (str(nome) + " " + str(desc)).upper()
    return 12.5 if any(k in s for k in keys) else 26.0

# ============================================================
# 5. SCRAPING (PRODUCTION-GRADE)
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
]


@dataclass
class ScrapeResult:
    name: str
    success: bool
    rows: int = 0
    error: Optional[str] = None
    elapsed_ms: int = 0


def _build_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"], respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _validate_bond_table(df):
    cols = [str(c).lower() for c in df.columns]
    has_isin = any("isin" in c for c in cols)
    has_price = any(any(k in c for k in ("prezzo", "price", "last", "ultimo")) for c in cols)
    has_mat = any(any(k in c for k in ("scadenza", "matur")) for c in cols)
    return has_isin and has_price and has_mat and len(df) > 0


def scrape_source(source, session, ua_index=0):
    name = source["nome"]
    t0 = time.monotonic()
    headers = {
        "User-Agent": USER_AGENTS[ua_index % len(USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    try:
        resp = session.get(source["url"], headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.warning(f"[{name}] HTTP failed: {e}")
        return None, ScrapeResult(name, False, error=str(e)[:80], elapsed_ms=elapsed)

    try:
        tables = pd.read_html(StringIO(resp.text), decimal=",", thousands=".")
    except ValueError:
        elapsed = int((time.monotonic() - t0) * 1000)
        return None, ScrapeResult(name, False, error="no_tables", elapsed_ms=elapsed)

    for df in tables:
        if _validate_bond_table(df):
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.info(f"[{name}] OK ({len(df)} rows, {elapsed}ms)")
            return df, ScrapeResult(name, True, rows=len(df), elapsed_ms=elapsed)

    elapsed = int((time.monotonic() - t0) * 1000)
    return None, ScrapeResult(name, False, error="invalid_schema", elapsed_ms=elapsed)


def aggiorna_db():
    """Non-destructive update with atomic swap."""
    if os.path.exists(TMP_FOLDER):
        shutil.rmtree(TMP_FOLDER)
    os.makedirs(TMP_FOLDER, exist_ok=True)

    session = _build_session()
    total = sum(len(v) for v in SOURCES_MAP.values())
    progress = st.progress(0.0)
    status = st.empty()
    results = []
    done = 0

    for cat, sources in SOURCES_MAP.items():
        for src in sources:
            done += 1
            status.text(f"⏳ {src['nome']} ({done}/{total})")
            progress.progress(done / total)
            df, res = scrape_source(src, session, ua_index=done)
            results.append(res)
            if df is not None:
                df.to_csv(os.path.join(TMP_FOLDER, f"{src['nome']}.csv"), index=False)
            if done < total:
                time.sleep(random.uniform(1.0, 2.5))

    success_count = sum(1 for r in results if r.success)
    if success_count >= total * 0.5:
        if os.path.exists(DB_FOLDER):
            shutil.rmtree(DB_FOLDER)
        shutil.move(TMP_FOLDER, DB_FOLDER)
        st.session_state.last_scrape_time = datetime.now()
        st.session_state.last_scrape_results = results
        st.toast(f"✅ DB aggiornato: {success_count}/{total}", icon="🛡️")
    else:
        shutil.rmtree(TMP_FOLDER, ignore_errors=True)
        st.error(f"❌ Solo {success_count}/{total} fonti OK. DB precedente preservato.")

    progress.empty()
    status.empty()
    time.sleep(1)
    st.rerun()

# ============================================================
# 6. UTILS & DATA ACCESS
# ============================================================
def valida_isin(isin):
    return bool(isin) and len(isin) == 12 and isin[:2].isalpha() and isin[2:].isalnum()


def get_last_update_time():
    try:
        if not os.path.exists(DB_FOLDER):
            return None
        files = [os.path.join(DB_FOLDER, f) for f in os.listdir(DB_FOLDER) if f.endswith('.csv')]
        if not files:
            return None
        return datetime.fromtimestamp(os.path.getmtime(max(files, key=os.path.getmtime)))
    except Exception:
        return None


def check_connection_status():
    try:
        requests.get("https://www.google.com", timeout=3)
        return "🟢 ONLINE"
    except Exception:
        return "🔴 OFFLINE"


def pulisci_taglio(v):
    s = str(v).lower().strip()
    if 'k' in s:
        try:
            return float(s.replace('k', '')) * 1000
        except Exception:
            return 1000.0
    try:
        return float(s.replace('.', '').replace(',', '.'))
    except Exception:
        return 1000.0


def detect_valuta(desc, isin):
    d = str(desc).upper()
    i = str(isin).upper()
    if "USA" in d or "TREASURY" in d or "DOLLAR" in d:
        return "USD"
    if "TURCHIA" in d or "LIRA" in d or "TRY" in d:
        return "TRY"
    if "BRASILE" in d or "REAL" in d:
        return "BRL"
    if "ROMANIA" in d or "LEU" in d or "RON" in d:
        return "RON"
    if i.startswith("GB") or "UK" in d:
        return "GBP"
    return "EUR"


@st.cache_data(ttl=3600)
def get_tasso_cambio_live(da, a):
    da = da.upper()
    a = a.upper()
    if da == a:
        return 1.0
    try:
        data = yf.Ticker(f"{da}{a}=X").history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        data_inv = yf.Ticker(f"{a}{da}=X").history(period="1d")
        if not data_inv.empty:
            return 1.0 / float(data_inv['Close'].iloc[-1])
    except Exception as e:
        logger.debug(f"FX fetch failed {da}/{a}: {e}")
    fallback = {"EURUSD": 1.05, "EURTRY": 36.0, "EURBRL": 6.10, "EURGBP": 0.85, "EURRON": 4.97}
    return fallback.get(f"{da}{a}", 1.0)


def processa_riga(row, info):
    try:
        cols = row.index if isinstance(row, pd.Series) else row.columns
        c_pr = next((c for c in cols if any(k in str(c).lower() for k in ['prezzo', 'last', 'price'])), None)
        c_sc = next((c for c in cols if 'scadenza' in str(c).lower()), None)
        c_de = next((c for c in cols if 'desc' in str(c).lower()), None)
        c_min = next((c for c in cols if 'min' in str(c).lower()), None)
        c_rat = next((c for c in cols if 'rating' in str(c).lower()), None)
        c_isin = next((c for c in cols if 'isin' in str(c).lower()), None)
        if not all([c_pr, c_sc, c_de]):
            return None

        pr = float(str(row[c_pr]).replace(',', '.').replace('€', '').strip())
        if pr <= 0:
            return None
        sc_str = str(row[c_sc]).strip()
        sc = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                sc = datetime.strptime(sc_str, fmt).date()
                break
            except ValueError:
                pass
        if sc is None or sc <= date.today():
            return None

        desc = str(row[c_de]).replace("â‚¬", "€").strip()
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        ced = float(m.group(1).replace(',', '.')) if m else 0.0
        taglio = pulisci_taglio(row[c_min]) if c_min and pd.notna(row[c_min]) else 1000.0
        rating = str(row[c_rat]).strip() if c_rat and pd.notna(row[c_rat]) else "NR"
        isin_val = str(row[c_isin]).strip() if c_isin else ""

        return {"desc": desc, "pr": pr, "sc": sc, "ced": ced, "freq": info['freq'],
                "fonte": info['nome'], "taglio": taglio, "rating": rating, "isin": isin_val}
    except Exception as e:
        logger.debug(f"processa_riga failed: {e}")
        return None


def identikit_bond(d):
    desc = d['desc'].upper()
    fonte = d['fonte'].upper()
    if "ITALIA" in fonte or "BTP" in desc or "BOT" in desc:
        chi, tipo, risk = "🇮🇹 STATO ITALIANO", "Titolo di Stato", "Rischio Paese: Medio"
    elif "GERMANIA" in fonte or "BUND" in desc:
        chi, tipo, risk = "🇩🇪 GERMANIA", "Bund (Risk Free)", "Bene Rifugio"
    elif "USA" in fonte or "TREASURY" in desc:
        chi, tipo, risk = "🇺🇸 USA", "Treasury Bond", "Rischio Cambio"
    elif "BANCHE" in fonte or "INTESA" in desc or "UNICREDIT" in desc:
        chi, tipo, risk = "🏦 SETTORE BANCARIO", "Bond Bancario", "Rischio Settoriale"
    elif "CORP" in fonte or "ENI" in desc or "ENEL" in desc:
        chi, tipo, risk = "🏭 AZIENDA", "Corporate Bond", "Rischio Emittente"
    else:
        chi, tipo, risk = "🌍 EMITTENTE", "Obbligazione", "Rating da verificare"
    diff = (d['sc'] - date.today())
    tempo = f"{diff.days // 365} Anni e {(diff.days % 365) // 30} Mesi"
    return chi, tipo, tempo, risk


def analizza_bond_quality_dettagliata(d, risk, tax, patrimonio):
    breakdown = []
    score = 100
    taglio = d.get('taglio', 1000.0)
    prezzo = d.get('pr', 100.0)

    peso = (taglio / patrimonio) * 100
    if peso > 20:
        p, msg, col = -30, f"Rischio alto: pesa il {peso:.1f}%", "score-bad"
    elif peso > 10:
        p, msg, col = -10, f"Taglio impegnativo: pesa il {peso:.1f}%", "score-neutral"
    else:
        p, msg, col = 0, f"Taglio sostenibile: pesa il {peso:.1f}%", "score-good"
    score += p
    breakdown.append({"cat": "🏗️ Sostenibilità", "val": f"{taglio/1000:.0f}k €", "msg": msg, "pts": p, "col": col})

    if prezzo > 110:
        p, msg, col = -15, "Molto sopra la pari", "score-bad"
    elif prezzo > 102:
        p, msg, col = -5, "Sopra la pari", "score-neutral"
    elif prezzo < 95:
        p, msg, col = 5, "Sotto la pari", "score-good"
    else:
        p, msg, col = 0, "Prezzo Fair", "score-good"
    score += p
    breakdown.append({"cat": "🏷️ Prezzo", "val": f"{prezzo:.2f}", "msg": msg, "pts": p, "col": col})

    ytm_lordo = risk.get('ytm', 0)
    ytm_net = ytm_lordo * (1 - tax / 100)
    if ytm_net < 1.5:
        p, msg, col = -20, "Rendimento basso", "score-bad"
    elif ytm_net > 3.0:
        p, msg, col = 15, "Ottimo rendimento", "score-good"
    else:
        p, msg, col = 0, "Rendimento medio", "score-neutral"
    score += p
    breakdown.append({"cat": "📈 Rendimento", "val": f"{ytm_net:.2f}%", "msg": msg, "pts": p, "col": col})

    if tax < 20:
        p, msg, col = 5, "Tassazione agevolata", "score-good"
    else:
        p, msg, col = -5, "Tassazione piena", "score-neutral"
    score += p
    breakdown.append({"cat": "🏛️ Tassazione", "val": f"{tax}%", "msg": msg, "pts": p, "col": col})

    flags = [("red", "Score Basso")] if score < 50 else []
    return {"score": max(0, min(100, score)), "breakdown": breakdown, "ytm_netto": ytm_net, "flags": flags}


def carica_dati_mercato():
    all_bonds = []
    if not os.path.exists(DB_FOLDER):
        return pd.DataFrame()
    files = [f for f in os.listdir(DB_FOLDER) if f.endswith(".csv")]
    if not files:
        return pd.DataFrame()

    for filename in files:
        path = os.path.join(DB_FOLDER, filename)
        try:
            try:
                df = pd.read_csv(path, sep=None, engine='python')
            except Exception:
                try:
                    df = pd.read_csv(path, sep=';')
                except Exception:
                    continue
            df.columns = [str(c).strip().lower() for c in df.columns]
            cols = df.columns

            c_pr = next((c for c in cols if any(x in c for x in ['prezzo', 'last', 'price', 'ultimo'])), None)
            c_sc = next((c for c in cols if 'scadenza' in c or 'matur' in c), None)
            c_de = next((c for c in cols if 'desc' in c or 'nome' in c or 'titolo' in c), None)
            c_isin = next((c for c in cols if 'isin' in c), None)
            c_ced = next((c for c in cols if 'cedola' in c or 'coupon' in c), None)
            if not all([c_pr, c_sc, c_de]):
                continue
            df = df.dropna(subset=[c_pr, c_sc])

            for _, row in df.iterrows():
                try:
                    pr = float(str(row[c_pr]).replace('€', '').replace(',', '.').strip())
                    if pr <= 0:
                        continue
                    sc_str = str(row[c_sc]).strip()
                    sc = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                        try:
                            sc = datetime.strptime(sc_str, fmt).date()
                            break
                        except ValueError:
                            pass
                    if sc is None or sc <= date.today():
                        continue

                    desc = str(row[c_de])
                    isin_v = str(row[c_isin]).strip().upper() if c_isin else "NO_ISIN"
                    ced = 0.0
                    if c_ced and pd.notna(row[c_ced]):
                        try:
                            ced = float(str(row[c_ced]).replace(',', '.').replace('%', ''))
                        except Exception:
                            pass
                    if ced == 0.0:
                        m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
                        if m:
                            ced = float(m.group(1).replace(',', '.'))

                    cat = "Altro"
                    du = desc.upper()
                    if any(x in du for x in ["BTP", "BOT", "BUND", "TREASURY", "OAT", "BONOS", "USA", "SPAGNA"]):
                        cat = "Governativo"
                    elif any(x in du for x in ["INTESA", "UNICREDIT", "BANCA", "MEDIOBANCA"]):
                        cat = "Bancario"
                    elif any(x in du for x in ["ENI", "ENEL", "STELLANTIS", "FERRARI", "TELECOM"]):
                        cat = "Corporate"

                    y_lordo = calcola_rendimento_grezzo(pr, ced, sc, freq=1)

                    all_bonds.append({
                        "ISIN": isin_v, "Desc": desc, "Prezzo": pr, "Scadenza": sc,
                        "Cedola": ced, "YTM_Grezzo": y_lordo,
                        "Anni": (sc - date.today()).days / 365.25,
                        "Fonte": filename.replace('.csv', ''), "Categoria": cat,
                        "Valuta": detect_valuta(desc, isin_v),
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Failed reading {filename}: {e}")
    return pd.DataFrame(all_bonds)


def categorizza_rischio(isin, fonte, desc):
    s = (str(fonte) + " " + str(desc)).upper()
    if any(x in s for x in ["BUND", "GERMANIA", "AUSTRIA", "OLANDA"]):
        return 1
    if any(x in s for x in ["BTP", "BOT", "ITALIA", "FRANCIA", "SPAGNA", "USA", "TREASURY"]):
        return 2
    if any(x in s for x in ["BANCA", "INTESA", "UNICREDIT", "CORPORATE", "ENI", "ENEL"]):
        return 3
    if any(x in s for x in ["HIGH", "TURCHIA", "BRASILE", "SUB"]):
        return 4
    return 3


def trova_alternative_migliori(target, df_market):
    if df_market.empty:
        return pd.DataFrame()
    anni_t = (target['sc'] - date.today()).days / 365.25
    tax_t = determina_tasse(target['fonte'], target['desc'])
    ytm_net_t = calcola_rendimento_grezzo(target['pr'], target['ced'], target['sc']) * (1 - tax_t / 100)
    isin_t = target.get('isin', '')
    risk_t = categorizza_rischio(isin_t, target['fonte'], target['desc'])

    alt = []
    for _, row in df_market.iterrows():
        if row['ISIN'] == isin_t:
            continue
        if not (anni_t - 3 <= row['Anni'] <= anni_t + 3):
            continue
        if row['Prezzo'] > 120:
            continue

        risk_a = categorizza_rischio(row['ISIN'], row['Fonte'], row['Desc'])
        tax_a = determina_tasse(row['Fonte'], row['Desc'])
        ytm_net_a = row['YTM_Grezzo'] * (1 - tax_a / 100)
        extra = ytm_net_a - ytm_net_t

        tipo = ""
        if risk_a <= risk_t and extra > 0.01:
            tipo = "✅ Gemello (+Safe)"
        elif risk_a == risk_t + 1 and extra > 0.30:
            tipo = "⚠️ Boost (Rischio+)"
        elif risk_a < risk_t and extra > -0.20:
            tipo = "🛡️ Rifugio (Safe)"
        elif row['Anni'] < anni_t - 1 and extra > -0.10:
            tipo = "⏳ Scade Prima"

        if tipo:
            d = row.to_dict()
            d.update({"Tipologia": tipo, "YTM_Netto": ytm_net_a, "Extra": extra,
                      "Link": f"https://www.google.com/search?q={row['ISIN']}+bond"})
            alt.append(d)

    df_alt = pd.DataFrame(alt)
    if not df_alt.empty:
        return df_alt.sort_values('Extra', ascending=False).head(10)
    return pd.DataFrame()


def cerca_db(isin, cat_macro):
    if not valida_isin(isin):
        return None, None
    keys = list(SOURCES_MAP.keys()) if not cat_macro or cat_macro == "🌐 TUTTE" else MACRO_CATEGORIES.get(cat_macro, [])
    for key in keys:
        for src in SOURCES_MAP.get(key, []):
            path = os.path.join(DB_FOLDER, f"{src['nome']}.csv")
            if not os.path.exists(path):
                continue
            try:
                df = pd.read_csv(path)
                col = next((c for c in df.columns if 'ISIN' in str(c).upper()), None)
                if col:
                    mask = df[col].astype(str).str.contains(isin, case=False, na=False)
                    if mask.any():
                        return df[mask].iloc[0], {"nome": src['nome'], "freq": src['freq'], "cat_reale": key}
            except Exception:
                continue
    return None, None


def get_settlement_date():
    d = date.today()
    added = 0
    while added < 2:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def calcola_rateo(d, settlement):
    try:
        if d['freq'] <= 0 or settlement >= d['sc']:
            return 0.0
        last_c, next_c = coupon_dates(d['sc'], int(d['freq']), settlement)
        days_total = (next_c - last_c).days
        days_passed = (settlement - last_c).days
        if days_total <= 0:
            return 0.0
        cedola_periodo = d['ced'] / d['freq']
        return max(0.0, cedola_periodo * (days_passed / days_total))
    except Exception:
        return 0.0


def genera_flussi_dettagliati(d, nominale, tax_rate, commissioni, prezzo_acquisto):
    flussi = []
    settlement = get_settlement_date()
    rateo_pct = calcola_rateo(d, settlement)
    costo_titolo = (nominale * prezzo_acquisto) / 100
    costo_rateo_netto = (nominale * rateo_pct) / 100 * (1 - tax_rate / 100)
    spesa_totale = costo_titolo + costo_rateo_netto + commissioni
    flussi.append({"Data": settlement, "Tipo": "USCITA", "Importo": -spesa_totale,
                   "Dettagli": f"Acquisto (Valuta {settlement.strftime('%d/%m')})"})

    totale_cedole = 0.0
    if d['freq'] > 0:
        cedola_netta = (nominale * (d['ced'] / 100) / d['freq']) * (1 - tax_rate / 100)
        curr = d['sc']
        while curr > settlement:
            if curr != d['sc']:
                flussi.append({"Data": curr, "Tipo": "ENTRATA", "Importo": cedola_netta, "Dettagli": "Cedola"})
                totale_cedole += cedola_netta
            mesi = 12 // int(d['freq'])
            ny, nm = curr.year, curr.month - mesi
            while nm <= 0:
                nm += 12
                ny -= 1
            last_day = calendar.monthrange(ny, nm)[1]
            curr = date(ny, nm, min(d['sc'].day, last_day))

    flussi.sort(key=lambda x: x['Data'])

    rimborso_lordo = nominale
    gain_prezzo = max(0, 100 - prezzo_acquisto)
    plusvalenza_lorda = (gain_prezzo / 100) * nominale
    tassa_gain = plusvalenza_lorda * (tax_rate / 100)
    rimborso_netto = rimborso_lordo - tassa_gain
    ultima_ced = (nominale * (d['ced'] / 100) / d['freq']) * (1 - tax_rate / 100) if d['freq'] > 0 else 0
    flussi.append({"Data": d['sc'], "Tipo": "ENTRATA", "Importo": rimborso_netto + ultima_ced,
                   "Dettagli": "Rimborso + Ultima Cedola"})

    incasso_totale = totale_cedole + rimborso_netto + ultima_ced
    totale_cedole += ultima_ced
    return pd.DataFrame(flussi), spesa_totale, incasso_totale, costo_rateo_netto, totale_cedole, plusvalenza_lorda

# ============================================================
# 7. UI PAGES
# ============================================================
def login():
    st.title("🔒 Login Terminale")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("---")
        u = st.text_input("Utente", placeholder="es. giulio").strip()
        p = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True):
            ph = hashlib.sha256(p.encode()).hexdigest()
            if u in UTENTI_ABILITATI and UTENTI_ABILITATI[u] == ph:
                st.session_state.logged_in = True
                st.session_state.current_user = u
                st.query_params["session"] = make_session_token(u)
                st.rerun()
            else:
                st.error("Errore Credenziali")


def scanner_ui():
    st.title("🔎 Scanner Obbligazionario Pro")
    st.caption("Analisi professionale: flussi reali, fiscalità italiana e stress test valutario.")

    st.markdown("### 🧭 Guida Rapida")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="cat-card bg-gov"><div class="cat-title">🏛️ GOVERNATIVI</div><div class="cat-desc">Stati Sovrani. Tax 12.5%.</div><span class="cat-meta">Rischio: BASSO</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="cat-card bg-bank"><div class="cat-title">🏦 BANCARI</div><div class="cat-desc">Senior/Sub. Tax 26%.</div><span class="cat-meta">Rischio: MEDIO</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="cat-card bg-corp"><div class="cat-title">🏭 CORPORATE</div><div class="cat-desc">Aziende. Tax 26%.</div><span class="cat-meta">Rischio: ALTO</span></div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="cat-card bg-spec"><div class="cat-title">💎 SPECIALI</div><div class="cat-desc">High Yield/Distressed.</div><span class="cat-meta">Rischio: VARIO</span></div>', unsafe_allow_html=True)

    st.divider()
    cc1, cc2, cc3 = st.columns([2, 2, 1])
    with cc1:
        cat_select = st.selectbox("Filtra Categoria DB", list(MACRO_CATEGORIES.keys()))
    with cc2:
        default_isin = st.session_state.selected_isin_from_chart or ""
        isin = st.text_input("ISIN", value=default_isin, placeholder="IT... / XS...",
                             help="Formato: 2 lettere + 10 caratteri").strip().upper()
        if st.session_state.selected_isin_from_chart:
            st.session_state.selected_isin_from_chart = None
    with cc3:
        st.write("")
        st.write("")
        trigger = st.button("🔎 Analizza", use_container_width=True)

    if not isin:
        st.info("Inserisci un ISIN per iniziare.")
        return
    if not valida_isin(isin):
        st.error("❌ ISIN non valido")
        return

    filtro = cat_select if not default_isin else "🌐 TUTTE"
    row, info = cerca_db(isin, filtro)
    d = processa_riga(row, info) if row is not None else None

    if not d:
        st.error("❌ Bond non trovato nel database. Prova ad aggiornare i dati.")
        return

    tax_rate = determina_tasse(d['fonte'], d['desc'])
    valuta_bond = detect_valuta(d['desc'], d['isin'])
    risk = calcola_metriche_rischio(d['pr'], d['ced'], d['sc'], d['freq'])

    # XIRR for accurate net yield
    df_base, _, _, _, _, _ = genera_flussi_dettagliati(d, 100.0, tax_rate, 0, d['pr'])

    def xirr_calc(df):
        try:
            dates_l = df['Data'].tolist()
            amounts = df['Importo'].tolist()
            if not amounts or amounts[0] >= 0:
                return 0.0
            d0 = dates_l[0]

            def xnpv(rate):
                if rate <= -0.999:
                    return float('inf')
                return sum(a / ((1 + rate) ** ((dt - d0).days / 365.0)) for a, dt in zip(amounts, dates_l))

            return brentq(xnpv, -0.49, 2.0, maxiter=100) * 100
        except Exception:
            return 0.0

    rendimento_netto = xirr_calc(df_base)
    chi, tipo, tempo, risk_msg = identikit_bond(d)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e2130 0%,#2a2d4a 100%);padding:20px;border-radius:12px;border-left:6px solid #00CC96;margin-bottom:20px;box-shadow:0 4px 6px rgba(0,0,0,0.3);">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div style="flex-grow:1;">
                <div style="color:#b0b3c5;font-size:13px;text-transform:uppercase;letter-spacing:1px;">{chi}</div>
                <div style="color:white;font-size:22px;font-weight:bold;line-height:1.2;">{d['desc']}</div>
                <div style="color:#00CC96;font-size:13px;">{tipo} | {risk_msg}</div>
            </div>
            <div style="text-align:right;min-width:90px;">
                <h2 style="color:#00CC96;margin:0;font-size:28px;">{d['ced']}%</h2>
                <div style="color:#b0b3c5;font-size:12px;">Cedola</div>
            </div>
        </div>
        <hr style="border-color:rgba(255,255,255,0.1);margin:15px 0;">
        <div style="display:flex;justify-content:space-between;color:#e0e0e0;font-size:14px;">
            <div>📅 Scadenza: <b>{d['sc'].strftime('%d/%m/%Y')}</b></div>
            <div>⏳ Manca: <b>{tempo}</b></div>
            <div>🧾 Prezzo: <b>{d['pr']} {valuta_bond}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("📊 Dati Chiave")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    sym = "€" if valuta_bond == "EUR" else valuta_bond
    m1.metric("Prezzo", f"{d['pr']} {sym}")
    m2.metric("Rend. NETTO", f"{rendimento_netto:.2f}%", help="XIRR sui flussi netti reali")
    m3.metric("Rend. LORDO", f"{risk['ytm']:.2f}%")
    m4.metric("Cedola", f"{d['ced']}%")
    m5.metric("Valuta", valuta_bond)
    m6.metric("Mod. Duration", f"{risk['mod_dur']:.2f}", help="Sensibilità ai tassi")

    st.divider()
    st.subheader("💰 Simulatore & Stress Test")
    s1, s2, s3 = st.columns(3)
    with s1:
        valuta_user = st.selectbox("La tua Valuta", ["EUR", "USD", "GBP", "CHF", "TRY", "BRL", "RON", "JPY"], index=0)
    with s2:
        budget_user = st.number_input(f"Budget ({valuta_user})", value=10000.0, step=1000.0)
    with s3:
        commissioni = st.number_input("Commissioni", value=5.0)

    tasso_spot = get_tasso_cambio_live(valuta_user, valuta_bond)
    st.caption(f"📡 Tasso LIVE: 1 {valuta_user} = {tasso_spot:.4f} {valuta_bond}")

    scenario_fx = 0
    if valuta_user != valuta_bond:
        u1, u2 = st.columns([2, 1])
        with u1:
            risk_txt, sugg = "MEDIO", "-10/-20%"
            if valuta_bond in ("TRY", "ARS", "RUB"):
                risk_txt, sugg = "ALTISSIMO", "-40%"
            elif valuta_bond in ("BRL", "ZAR", "MXN"):
                risk_txt, sugg = "ALTO", "-25%"
            st.info(f"**Rischio {valuta_bond}: {risk_txt}** (suggerito {sugg})")
        with u2:
            scenario_fx = st.slider(f"📉 Variazione {valuta_bond}", -50, 50, 0, format="%d%%")

    rateo_unit = calcola_rateo(d, get_settlement_date())
    prezzo_telquel = d['pr'] + rateo_unit
    costo_100 = prezzo_telquel / tasso_spot
    nominale_teor = ((budget_user - commissioni) / costo_100) * 100
    lotto = d['taglio'] if d['taglio'] > 0 else 1000.0
    nominale_eff = int(nominale_teor / lotto) * lotto
    force = False
    if nominale_eff == 0 and budget_user > 0:
        nominale_eff = lotto
        force = True

    if nominale_eff <= 0:
        st.warning(f"⚠️ Budget insufficiente. Taglio minimo: {lotto:,.0f} {valuta_bond}.")
        return

    if force:
        st.warning(f"⚠️ Budget basso. Calcolo su 1 lotto ({lotto:,.0f} {valuta_bond}).")

    df_flussi, spesa_loc, incasso_loc, rateo_loc, tot_ced_loc, _ = genera_flussi_dettagliati(d, nominale_eff, tax_rate, 0, d['pr'])

    rate_rientro = tasso_spot * (1 - scenario_fx / 100) if valuta_user != valuta_bond else 1.0
    if rate_rientro < 0.001:
        rate_rientro = 0.001

    costo_titolo_user = (nominale_eff * d['pr'] / 100) / tasso_spot
    rateo_user = rateo_loc / tasso_spot
    spesa_user = costo_titolo_user + rateo_user + commissioni
    df_flussi['Importo_User'] = df_flussi.apply(
        lambda x: x['Importo'] / tasso_spot if x['Tipo'] == 'USCITA' else x['Importo'] / rate_rientro, axis=1)

    incasso_user = df_flussi[df_flussi['Tipo'] != 'USCITA']['Importo_User'].sum()
    cedole_user = tot_ced_loc / rate_rientro
    rimborso_v = incasso_user - cedole_user
    guadagno = incasso_user - spesa_user
    roi = (guadagno / spesa_user) * 100 if spesa_user > 0 else 0
    anni_res = max((d['sc'] - date.today()).days / 365.25, 0.1)
    roi_annuo = ((incasso_user / spesa_user) ** (1 / anni_res) - 1) * 100 if spesa_user > 0 else -100

    st.write("")
    st.markdown(f"### 🧾 Analisi Flussi (Nominale: {nominale_eff:,.0f} {valuta_bond})")
    cu, ce = st.columns(2)
    with cu:
        st.markdown(f"""
        <div class="receipt-box" style="border-left:4px solid #FF4B4B;background-color:rgba(255,75,75,0.05);padding:15px;border-radius:8px;">
            <div style="font-weight:bold;color:#FF4B4B;">📉 USCITE (Oggi)</div>
            <div class="receipt-row"><span>Costo Titoli:</span><span>{costo_titolo_user:,.2f} {valuta_user}</span></div>
            <div class="receipt-row"><span>Rateo:</span><span>{rateo_user:,.2f} {valuta_user}</span></div>
            <div class="receipt-row"><span>Commissioni:</span><span>{commissioni:,.2f} {valuta_user}</span></div>
            <div class="receipt-total" style="color:#FF4B4B;">TOTALE: -{spesa_user:,.2f} {valuta_user}</div>
        </div>""", unsafe_allow_html=True)
    with ce:
        col_res = "#00CC96" if guadagno > 0 else "#FF4B4B"
        lbl = f"{rate_rientro:.2f}" if valuta_user != valuta_bond else "Inv."
        st.markdown(f"""
        <div class="receipt-box" style="border-left:4px solid {col_res};background-color:rgba(0,204,150,0.05);padding:15px;border-radius:8px;">
            <div style="font-weight:bold;color:{col_res};">📈 ENTRATE (Tasso {lbl})</div>
            <div class="receipt-row"><span>Cedole Nette:</span><span>+{cedole_user:,.2f} {valuta_user}</span></div>
            <div class="receipt-row"><span>Rimborso:</span><span>+{rimborso_v:,.2f} {valuta_user}</span></div>
            <div class="receipt-row" style="color:#888;"><span>(Effetto Cambio: {scenario_fx}%)</span></div>
            <div class="receipt-total" style="color:{col_res};">TOTALE: +{incasso_user:,.2f} {valuta_user}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()
    if guadagno > 0:
        st.success(f"✅ **PROFITTO:** +{guadagno:,.2f} {valuta_user} (Tot: +{roi:.2f}% | **Annuo: +{roi_annuo:.2f}%**)")
    else:
        st.error(f"❌ **PERDITA:** {guadagno:,.2f} {valuta_user} (Tot: {roi:.2f}% | **Annuo: {roi_annuo:.2f}%**)")

    st.subheader("🗓️ Recupero Capitale (Break-Even)")
    df_flussi['Cumulativo'] = df_flussi['Importo_User'].cumsum()
    colors = ['#FF4B4B' if v < 0 else '#00CC96' for v in df_flussi['Cumulativo']]

    be_date = None
    df_neg = df_flussi[df_flussi['Cumulativo'] < 0]
    df_pos = df_flussi[df_flussi['Cumulativo'] >= 0]
    if not df_neg.empty and not df_pos.empty:
        ln, fp = df_neg.iloc[-1], df_pos.iloc[0]
        y1, y2 = ln['Cumulativo'], fp['Cumulativo']
        x1, x2 = ln['Data'].toordinal(), fp['Data'].toordinal()
        if y2 != y1:
            xz = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
            be_date = date.fromordinal(int(xz))
        else:
            be_date = fp['Data']

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_flussi['Data'], y=df_flussi['Cumulativo'], mode='lines',
                             line=dict(color='#888', width=1, dash='dot'), name='Trend'))
    fig.add_trace(go.Scatter(x=df_flussi['Data'], y=df_flussi['Cumulativo'], mode='markers',
                             marker=dict(symbol='circle-open', size=9, color=colors, line=dict(width=2.5)),
                             text=df_flussi['Dettagli'],
                             hovertemplate="<b>%{text}</b><br>Saldo: %{y:,.2f}<extra></extra>"))
    if be_date:
        fig.add_trace(go.Scatter(x=[be_date], y=[0], mode='markers', name='Break-Even',
                                 marker=dict(symbol='star', size=18, color='#FFD700', line=dict(width=1, color='white')),
                                 hoverinfo='text', hovertext=f"★ BREAK-EVEN<br>{be_date.strftime('%d/%m/%Y')}"))
    fig.add_hline(y=0, line_color='white', line_width=1, layer="below")
    fig.update_layout(template="plotly_dark", height=350, showlegend=False,
                      margin=dict(l=20, r=20, t=30, b=20), yaxis_title="Saldo Cumulativo")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📅 Cedolario Dettagliato")
    def style_c(v):
        return f'color:{"#00CC96" if v >= 0 else "#FF4B4B"};font-weight:bold;'
    st.dataframe(
        df_flussi[['Data', 'Tipo', 'Importo', 'Importo_User', 'Dettagli']]
        .style.format({'Importo': f'{{:+,.2f}} {valuta_bond}', 'Importo_User': f'{{:+,.2f}} {valuta_user}'})
        .map(style_c, subset=['Importo', 'Importo_User']),
        use_container_width=True)


def bond_screener_ui():
    st.title("🌐 Global Fixed Income Ranking")
    st.caption("Analisi comparativa rendimenti reali con stima costo copertura valutaria.")

    defaults = {"EUR": 2.50, "USD": 4.00, "GBP": 4.25, "CHF": 0.75, "JPY": 0.90,
                "CAD": 3.20, "AUD": 4.10, "TRY": 28.00, "BRL": 12.00, "ZAR": 9.50,
                "MXN": 9.00, "RON": 6.50, "HUF": 6.00}

    with st.spinner("Caricamento database..."):
        df_market = carica_dati_mercato()
        if df_market.empty:
            st.error("Database offline. Aggiorna i dati dalla sidebar.")
            return
        if 'Valuta' not in df_market.columns:
            df_market['Valuta'] = df_market.apply(lambda x: detect_valuta(x.get('Desc', ''), x.get('ISIN', '')), axis=1)

    st.divider()
    cw, cs = st.columns(2)
    with cw:
        valuta_wallet = st.selectbox("1️⃣ Valuta Portafoglio", ["EUR", "USD"], index=0)
    with cs:
        scope = st.radio("2️⃣ Universo", [f"🔒 Locale ({valuta_wallet})", "🌍 Globale (Hedged)"], index=1)

    rates = defaults.copy()
    try:
        usd_live = yf.Ticker("^TNX").history(period="1d")
        if not usd_live.empty:
            rates["USD"] = float(usd_live['Close'].iloc[-1])
    except Exception:
        pass

    if "Globale" in scope:
        with st.expander("⚙️ Tassi Risk Free (Modificabili)", expanded=False):
            cols = st.columns(5)
            priority = ["EUR", "USD", "TRY", "BRL", "ZAR"]
            others = [k for k in rates if k not in priority]
            for i, k in enumerate(priority + others):
                with cols[i % 5]:
                    rates[k] = st.number_input(f"{k} (%)", value=float(rates[k]), step=0.25, format="%.2f", key=f"rate_{k}")

    tasso_base = rates.get(valuta_wallet, 3.0)
    df_w = df_market.copy()
    spot = {v: (1.0 if v == valuta_wallet else get_tasso_cambio_live(valuta_wallet, v)) for v in df_w['Valuta'].unique()}
    df_w['FX_Rate'] = df_w['Valuta'].map(spot).fillna(1.0)
    df_w['Prezzo_Wallet'] = df_w.apply(lambda x: x['Prezzo'] / x['FX_Rate'] if x['FX_Rate'] > 0 else x['Prezzo'], axis=1)

    def calc_real(row):
        if row['Valuta'] == valuta_wallet:
            return row['YTM_Grezzo']
        return row['YTM_Grezzo'] - (rates.get(row['Valuta'], 5.0) - tasso_base)

    df_w['YTM_Reale'] = df_w.apply(calc_real, axis=1)
    if "Locale" in scope:
        df_w = df_w[df_w['Valuta'] == valuta_wallet]

    st.divider()
    st.subheader("🛠️ Filtri")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        min_y = st.number_input("Yield Min (%)", value=2.0, step=0.5)
    with f2:
        max_p = st.number_input("Prezzo Max", value=120.0, step=1.0)
    with f3:
        min_d = st.number_input("Anni Min", value=0.0, step=1.0)
    with f4:
        max_d = st.number_input("Anni Max", value=30.0, step=1.0)

    cats = ["🌐 TUTTE"] + sorted(df_w['Categoria'].unique().tolist())
    sel = st.multiselect("Settore", cats, default=["🌐 TUTTE"])

    st.write("")
    if st.button("🚀 TROVA OPPORTUNITÀ", type="primary", use_container_width=True):
        res = df_w[(df_w['YTM_Reale'] >= min_y) & (df_w['Anni'] >= min_d) &
                   (df_w['Anni'] <= max_d) & (df_w['Prezzo_Wallet'] <= max_p)]
        if sel and "🌐 TUTTE" not in sel:
            res = res[res['Categoria'].isin(sel)]
        res = res.sort_values('YTM_Reale', ascending=False)

        if res.empty:
            st.warning("Nessun risultato.")
        else:
            st.success(f"Trovati **{len(res)}** titoli.")
            st.dataframe(
                res[['Desc', 'Valuta', 'Prezzo_Wallet', 'YTM_Reale', 'YTM_Grezzo', 'Anni', 'ISIN']].head(100),
                use_container_width=True, height=600,
                column_config={
                    "Desc": st.column_config.TextColumn("Titolo", width="medium"),
                    "Valuta": st.column_config.TextColumn("Ccy", width="small"),
                    "Prezzo_Wallet": st.column_config.NumberColumn(f"Px {valuta_wallet}", format="%.2f"),
                    "YTM_Reale": st.column_config.NumberColumn("✅ Yield Reale", format="%.2f%%"),
                    "YTM_Grezzo": st.column_config.NumberColumn("Yield Nominale", format="%.2f%%"),
                    "Anni": st.column_config.ProgressColumn("Duration", format="%.1f y", min_value=0, max_value=30),
                    "ISIN": "ISIN",
                },
                hide_index=True)

            st.divider()
            ci, cb = st.columns([3, 1])
            with ci:
                isin_chk = st.text_input("ISIN", placeholder="Copia ISIN...", label_visibility="collapsed")
            with cb:
                if st.button("Analizza ➡️", use_container_width=True) and isin_chk:
                    st.session_state.selected_isin_from_chart = isin_chk
                    st.session_state.page = "Scanner"
                    st.rerun()


def smart_analysis_ui():
    st.title("🧠 Smart Analysis & Fair Value")
    st.caption("Mappa del mercato: posizionamento e alternative migliori.")

    with st.spinner("Analisi mercato..."):
        df_market = carica_dati_mercato()
    if df_market.empty:
        st.warning("⚠️ Database vuoto. Aggiorna i dati.")
        return

    def get_tipo(row):
        s = (str(row['Fonte']) + " " + str(row['Desc'])).upper()
        if any(x in s for x in ['BTP', 'BOT', 'ITALIA', 'GERMANIA', 'BUND', 'USA', 'TREASURY', 'SPAGNA']):
            return "Governativo"
        if any(x in s for x in ['BANCA', 'INTESA', 'UNICREDIT', 'BANCARI', 'SUB', 'ASSICURAZIONI']):
            return "Bancario"
        if any(x in s for x in ['CORP', 'ENI', 'ENEL', 'STELLANTIS', 'INDUSTRIA', 'AUTO']):
            return "Corporate"
        return "Altro / High Yield"

    df_market['Tipo'] = df_market.apply(get_tipo, axis=1)

    default_isin = st.session_state.selected_isin_from_chart or ""
    if st.session_state.selected_isin_from_chart:
        st.session_state.selected_isin_from_chart = None

    cs, cc = st.columns([1, 3])
    with cs:
        isin = st.text_input("Analizza ISIN", value=default_isin, placeholder="IT...").strip().upper()
    with cc:
        cat_opt = [""] + sorted(set(df_market['Tipo'].unique()))
        cat_filter = st.selectbox("Filtra Categoria", cat_opt, format_func=lambda x: "Tutto" if x == "" else x)

    if not (isin and valida_isin(isin)):
        st.info("Inserisci un ISIN valido per iniziare.")
        return

    row, info = cerca_db(isin, None)
    d = processa_riga(row, info) if row is not None else None
    if not d:
        st.error("ISIN non trovato.")
        return

    d['isin'] = isin
    ytm_s = calcola_rendimento_grezzo(d['pr'], d['ced'], d['sc'])
    dur_s = (d['sc'] - date.today()).days / 365.25
    tipo_s = get_tipo({'Fonte': d['fonte'], 'Desc': d['desc']})

    st.divider()
    st.subheader("📊 Mappa del Mercato")

    mask = (df_market['Anni'] >= dur_s - 3) & (df_market['Anni'] <= dur_s + 3) & (df_market['YTM_Grezzo'] < ytm_s + 8)
    if cat_filter:
        mask &= df_market['Tipo'] == cat_filter
    df_zoom = df_market[mask].copy()

    fig = px.scatter(df_zoom, x='Anni', y='YTM_Grezzo', color='Tipo',
                     hover_data={'ISIN': True, 'Desc': True, 'Prezzo': ':.2f', 'YTM_Grezzo': ':.2f', 'Tipo': True, 'Anni': False},
                     labels={'Anni': 'Durata (Anni)', 'YTM_Grezzo': 'Rendimento Lordo (%)'},
                     color_discrete_map={"Governativo": "#00CC96", "Bancario": "#FFA15A",
                                          "Corporate": "#636EFA", "Altro / High Yield": "#EF553B"})
    fig.update_traces(marker=dict(symbol='circle-open', size=9, line=dict(width=2)))
    fig.add_trace(go.Scatter(x=[dur_s], y=[ytm_s], mode='markers+text', name='IL TUO BOND',
                             text=['📍 TU'], textposition="top center",
                             marker=dict(color='red', size=18, symbol='star', line=dict(width=1, color='white')),
                             hoverinfo='text', hovertext=f"TUO BOND<br>{d['desc']}<br>YTM: {ytm_s:.2f}%"))
    fig.update_layout(template="plotly_dark", height=500, legend=dict(orientation="h", y=1.1),
                      hovermode="closest", margin=dict(l=20, r=20, t=20, b=20))
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

    if sel and len(sel.get('selection', {}).get('points', [])) > 0:
        try:
            pt = sel['selection']['points'][0]
            if 'customdata' in pt:
                st.session_state.selected_isin_from_chart = pt['customdata'][0]
                st.rerun()
        except Exception:
            pass

    st.divider()
    st.subheader("🔄 Smart Switch (Alternative)")
    alt = trova_alternative_migliori(d, df_market)
    if not alt.empty:
        st.dataframe(alt[['Tipologia', 'ISIN', 'Desc', 'Prezzo', 'YTM_Netto', 'Extra', 'Link']],
                     column_config={
                         "Link": st.column_config.LinkColumn("Scheda", display_text="🔗 Apri"),
                         "YTM_Netto": st.column_config.NumberColumn("YTM Netto", format="%.2f%%"),
                         "Extra": st.column_config.NumberColumn("Delta", format="+%.2f%%"),
                         "Prezzo": st.column_config.NumberColumn("Prezzo", format="%.2f€"),
                         "Tipologia": st.column_config.TextColumn("Analisi", width="medium"),
                     },
                     use_container_width=True, hide_index=True)
    else:
        st.success("🏆 Nessuna alternativa nettamente migliore trovata.")


def dashboard_mercato_ui():
    st.title("📊 Dashboard Mercato")
    with st.spinner("Analisi macro..."):
        df = carica_dati_mercato()
    if df.empty:
        st.error("❌ Database vuoto.")
        return

    st.subheader("📈 Statistiche Generali")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bond Censiti", len(df))
    c2.metric("YTM Medio", f"{df['YTM_Grezzo'].mean():.2f}%")
    c3.metric("Prezzo Medio", f"{df['Prezzo'].mean():.2f}€")
    c4.metric("Duration Media", f"{df['Anni'].mean():.1f} anni")

    st.divider()
    st.subheader("🏆 Top 10 Rendimenti Nominali")
    top = df.nlargest(10, 'YTM_Grezzo').sort_values('YTM_Grezzo', ascending=True)
    cc, ct = st.columns([2, 1])
    with cc:
        fig = px.bar(top, x='YTM_Grezzo', y='Desc', orientation='h', text='YTM_Grezzo',
                     color='YTM_Grezzo', color_continuous_scale='Viridis',
                     labels={'YTM_Grezzo': 'Rendimento %', 'Desc': 'Titolo'})
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        fig.update_layout(showlegend=False, height=400, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    with ct:
        st.dataframe(top[['ISIN', 'YTM_Grezzo', 'Prezzo']].sort_values('YTM_Grezzo', ascending=False),
                     use_container_width=True, height=400,
                     column_config={"YTM_Grezzo": st.column_config.NumberColumn("Yield", format="%.2f%%"),
                                    "Prezzo": st.column_config.NumberColumn("Px", format="%.2f")},
                     hide_index=True)

    st.divider()
    st.subheader("📊 Rendimenti per Settore")
    if 'Categoria' in df.columns:
        dc = df.groupby('Categoria').agg({'YTM_Grezzo': 'mean', 'ISIN': 'count'}).reset_index()
        dc.columns = ['Categoria', 'YTM Medio', 'Numero Bond']
        fig = px.bar(dc, x='Categoria', y='YTM Medio', text='YTM Medio', color='Categoria')
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🔥 Heatmap: Scadenza vs Rendimento")
    try:
        df['Bucket'] = pd.cut(df['Anni'], bins=[0, 2, 5, 10, 20, 50],
                              labels=['Breve (0-2y)', 'Medio (2-5y)', 'Lungo (5-10y)', 'Extra-Lungo (10-20y)', 'Lunghissimo (20y+)'])
        pivot = df.pivot_table(values='YTM_Grezzo', index='Categoria', columns='Bucket', aggfunc='mean').fillna(0)
        fig = px.imshow(pivot, text_auto='.2f', aspect="auto", color_continuous_scale='RdYlGn',
                        labels={'color': 'YTM %'})
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.warning("Dati insufficienti per Heatmap.")


def diversificazione_portfolio_ui():
    st.title("🧩 Costruisci il tuo Portafoglio")
    st.caption("Selezione automatica in base ai tuoi obiettivi.")

    with st.spinner("Analisi universo..."):
        df = carica_dati_mercato()
    if df.empty:
        st.error("Database vuoto.")
        return

    st.subheader("1️⃣ Capitale")
    c1, c2 = st.columns(2)
    with c1:
        capitale = st.number_input("Importo (€)", min_value=5000.0, step=5000.0, value=50000.0)
    with c2:
        n_bond = st.slider("Numero Titoli", 3, 12, 6)
        st.caption(f"💡 ~{capitale/n_bond:,.0f} € per titolo")

    st.divider()
    st.subheader("2️⃣ Profilo di Rischio")

    PROFILI = {
        "🛡️ Prudente": {"desc": "Difesa del capitale.", "regole": ["Solo Titoli di Stato", "Max 5 anni"],
                        "alloc": {"Gov": 1.0, "Corp": 0.0, "HY": 0.0}, "max_dur": 5},
        "⚖️ Bilanciato": {"desc": "Equilibrio.", "regole": ["60% Gov / 40% Corp", "Max 10 anni"],
                          "alloc": {"Gov": 0.6, "Corp": 0.4, "HY": 0.0}, "max_dur": 10},
        "🚀 Aggressivo": {"desc": "Massimo rendimento.", "regole": ["Include HY", "Anche >10 anni"],
                          "alloc": {"Gov": 0.3, "Corp": 0.4, "HY": 0.3}, "max_dur": 30},
    }
    scelta = st.radio("Obiettivo:", list(PROFILI.keys()), index=1, horizontal=True)
    p = PROFILI[scelta]
    with st.chat_message("assistant"):
        st.markdown(f"**{scelta}**: {p['desc']}")
        for r in p['regole']:
            st.markdown(f"- {r}")

    st.divider()
    st.subheader("3️⃣ Risultato")

    if st.button("✨ Genera Portafoglio", type="primary", use_container_width=True):
        df_pool = df.copy()

        def tagga(row):
            d = (str(row['Desc']) + " " + str(row['Categoria'])).upper()
            if any(x in d for x in ["TRY", "ZAR", "PEMEX", "PETROBRAS", "SUB", "BRL"]):
                return "HY"
            if any(x in d for x in ["BTP", "BOT", "BUND", "OAT", "TREASURY", "USA", "SPAGNA", "BEI", "EU "]):
                return "Gov"
            return "Corp"

        df_pool['TipoAsset'] = df_pool.apply(tagga, axis=1)
        slots = []
        for ac, w in p['alloc'].items():
            slots.extend([ac] * int(round(n_bond * w)))
        while len(slots) < n_bond:
            slots.append("Gov")
        slots = slots[:n_bond]

        portfolio = []
        used = []
        for tt in slots:
            cand = df_pool[(df_pool['TipoAsset'] == tt) & (df_pool['Anni'] <= p['max_dur']) & (~df_pool['ISIN'].isin(used))]
            if cand.empty and tt == "HY":
                cand = df_pool[(df_pool['TipoAsset'] == "Corp") & (df_pool['Anni'] <= p['max_dur']) & (~df_pool['ISIN'].isin(used))]
            if cand.empty:
                cand = df_pool[(df_pool['TipoAsset'] == "Gov") & (df_pool['Anni'] <= p['max_dur']) & (~df_pool['ISIN'].isin(used))]
            if cand.empty:
                continue

            cand = cand.sort_values('Anni' if "Prudente" in scelta else 'YTM_Grezzo',
                                    ascending=("Prudente" in scelta))
            best = cand.iloc[0]
            portfolio.append({"Categoria": best['TipoAsset'], "Emittente": best['Desc'],
                              "Prezzo": best['Prezzo'], "Cedola %": best['Cedola'],
                              "YTM %": best['YTM_Grezzo'], "Scadenza": best['Anni'],
                              "ISIN": best['ISIN'], "Allocazione": capitale / n_bond})
            used.append(best['ISIN'])

        if not portfolio:
            st.error("Nessun bond adatto trovato.")
            return

        df_pf = pd.DataFrame(portfolio)
        ytm_m = df_pf['YTM %'].mean()
        dur_m = df_pf['Scadenza'].mean()
        cedola_a = (capitale * df_pf['Cedola %'].mean() / 100) * 0.875

        st.success("✅ Portafoglio Generato!")
        k1, k2, k3 = st.columns(3)
        k1.metric("Rendimento Lordo", f"{ytm_m:.2f}%")
        k2.metric("Durata Media", f"{dur_m:.1f} anni")
        k3.metric("Flusso Annuo", f"~{cedola_a:,.0f} €")

        st.dataframe(df_pf, use_container_width=True, hide_index=True,
                     column_config={
                         "Allocazione": st.column_config.NumberColumn("Investimento", format="%.0f €"),
                         "Prezzo": st.column_config.NumberColumn("Prezzo", format="%.2f"),
                         "YTM %": st.column_config.NumberColumn("Rendimento", format="%.2f%%"),
                         "Scadenza": st.column_config.ProgressColumn("Durata", format="%.1f y", min_value=0, max_value=30),
                     })

        df_pf = df_pf.sort_values('Scadenza')
        fig = px.bar(df_pf, x='Scadenza', y='Allocazione', color='Categoria', text='Emittente',
                     color_discrete_map={"Gov": "#00CC96", "Corp": "#636EFA", "HY": "#EF553B"})
        st.plotly_chart(fig, use_container_width=True)

        csv = df_pf.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Scarica CSV", csv, "portafoglio.csv", "text/csv")


def alert_manager_ui():
    st.title("🔔 Alert Intelligenti")
    st.warning("⚠️ Funzione in sviluppo (simulazione).")

    if 'alerts' not in st.session_state:
        st.session_state.alerts = []

    st.subheader("➕ Crea Alert")
    tipo = st.selectbox("Tipo", ["Prezzo Scende Sotto", "YTM Sale Sopra", "Nuova Emissione"])
    c1, c2 = st.columns(2)
    with c1:
        if tipo == "Prezzo Scende Sotto":
            st.text_input("ISIN")
            target = st.number_input("Prezzo Target", value=95.0)
        elif tipo == "YTM Sale Sopra":
            st.selectbox("Categoria", ["Governativo", "Bancario", "Corporate"])
            target = st.number_input("YTM Min %", value=3.5)
        else:
            st.selectbox("Categoria", ["BTP", "Corporate", "Bancari"])
            target = None
    with c2:
        st.radio("Notifica", ["Email", "App (N/D)"], disabled=True)

    if st.button("✅ Attiva"):
        st.session_state.alerts.append({'tipo': tipo, 'target': target, 'data': date.today()})
        st.success("Alert attivato!")

    st.divider()
    st.subheader("📋 Alert Attivi")
    if st.session_state.alerts:
        for i, a in enumerate(st.session_state.alerts):
            ci, cb = st.columns([4, 1])
            ci.info(f"**{a['tipo']}** - Target: {a.get('target', 'N/A')} - {a['data']}")
            with cb:
                if st.button("❌", key=f"del_{i}"):
                    st.session_state.alerts.pop(i)
                    st.rerun()
    else:
        st.info("Nessun alert attivo")

# ============================================================
# 8. MAIN APP
# ============================================================
def main_app():
    with st.sidebar:
        st.title("🏛️ BOND TERMINAL")
        if st.session_state.current_user:
            st.markdown(f'<div class="user-box">👤 {st.session_state.current_user.capitalize()}</div>',
                        unsafe_allow_html=True)

        st.subheader("🧭 NAVIGAZIONE")
        if st.button("🔎 Scanner Singolo", use_container_width=True):
            st.session_state.page = "Scanner"
            st.rerun()
        if st.button("🎯 Screener Avanzato", use_container_width=True):
            st.session_state.page = "Screener"
            st.rerun()
        if st.button("🧠 Smart Analysis", use_container_width=True):
            st.session_state.page = "SmartAnalysis"
            st.rerun()
        if st.button("📊 Dashboard Mercato", use_container_width=True):
            st.session_state.page = "Dashboard"
            st.rerun()
        if st.button("🧮 Diversificazione", use_container_width=True):
            st.session_state.page = "Diversificazione"
            st.rerun()
        if st.button("🔔 Alert Manager", use_container_width=True):
            st.session_state.page = "Alerts"
            st.rerun()

        st.divider()
        st.caption("⚙️ STATO SISTEMA")

        files = [f for f in os.listdir(DB_FOLDER) if f.endswith('.csv')] if os.path.exists(DB_FOLDER) else []
        tot = sum(len(v) for v in SOURCES_MAP.values())
        cov = len(files) / tot if tot else 0

        s1, s2 = st.columns(2)
        s1.metric("Files", f"{len(files)}/{tot}")
        last = get_last_update_time()
        if last:
            delta = datetime.now() - last
            if delta < timedelta(minutes=5):
                lbl = "Ora"
            elif delta < timedelta(hours=1):
                lbl = f"{int(delta.total_seconds()/60)}m fa"
            elif delta < timedelta(days=1):
                lbl = f"{int(delta.total_seconds()/3600)}h fa"
            else:
                lbl = f"{delta.days}g fa"
        else:
            lbl = "Mai"
        s2.metric("Aggiornato", lbl)

        if cov < 1.0:
            st.progress(cov, text=f"Copertura {cov:.0%}")

        results = st.session_state.get("last_scrape_results", [])
        if results:
            failed = [r for r in results if not r.success]
            if failed:
                with st.expander(f"⚠️ {len(failed)} fonti fallite"):
                    for r in failed:
                        st.caption(f"❌ {r.name}: {r.error}")

        if st.button("🔄 AGGIORNA DATI", type="primary", use_container_width=True):
            if "OFFLINE" in check_connection_status():
                st.error("❌ Sei offline")
            else:
                aggiorna_db()

        with st.expander("🛠️ Manutenzione"):
            st.caption(f"Status: {check_connection_status()}")
            if st.button("🗑️ Reset Database", use_container_width=True):
                try:
                    if os.path.exists(DB_FOLDER):
                        for f in os.listdir(DB_FOLDER):
                            os.remove(os.path.join(DB_FOLDER, f))
                    st.toast("Database svuotato!", icon="🧹")
                    time.sleep(1)
                    st.rerun()
                except Exception:
                    pass

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.query_params.clear()
            st.rerun()

    page = st.session_state.page
    if page == "Scanner":
        scanner_ui()
    elif page == "Screener":
        bond_screener_ui()
    elif page == "SmartAnalysis":
        smart_analysis_ui()
    elif page == "Dashboard":
        dashboard_mercato_ui()
    elif page == "Diversificazione":
        diversificazione_portfolio_ui()
    elif page == "Alerts":
        alert_manager_ui()


if st.session_state.logged_in:
    main_app()
else:
    login()
