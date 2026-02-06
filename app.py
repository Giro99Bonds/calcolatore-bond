# --- MAPPA FONTI COMPLETA (Nomi Migliorati) ---
SOURCES_MAP = {
    "🇮🇹 Titoli di Stato Italiani (BTP, BOT, CCT)": [
        {"nome": "BTP", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BOT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "TDS Scadenza 2026", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovtds2026&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏦 Obbligazioni Bancarie Italiane (Senior)": [
        {"nome": "BANCHE ITA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "INTESA SANPAOLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=intesasanpaolo&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "UNICREDIT", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=unicredit&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "MEDIOBANCA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=mediobanca&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🇪🇺 Banche Estere ed Internazionali": [
        {"nome": "BANCHE EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheeuropee&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "BANCHE USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheusa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BANCHE GENERICO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=banche&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🏭 Aziende (Corporate, Auto, Energy, Tlc)": [
        {"nome": "CORP ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "CORP MONDO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "TELECOMUNICAZIONI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=telecom&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "SETTORE AUTO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ENERGIA & PETROLIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=petrolio&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "🌍 Stati Esteri (USA, Bund, Romania, EU)": [
        {"nome": "TREASURY USA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR", "freq": 2},
        {"nome": "BUND GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "OAT FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "EUROPA MIX", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europa&yieldtype=G&timescale=DUR", "freq": 1}
    ],
    "💎 Titoli Speciali (Sub, Callable, Zero Coupon)": [
        {"nome": "SUBORDINATE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "ZERO COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR", "freq": 0},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR", "freq": 1},
        {"nome": "GREEN BOND", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbond&yieldtype=G&timescale=DUR", "freq": 1}
    ]
}

# ... (Mantieni le funzioni xirr e get_bond_data_academic uguali) ...

# --- UI MIGLIORATA ---
st.title("🎓 Bond Research Console")

if 'access' not in st.session_state: st.session_state.access = False
if not st.session_state.access:
    st.info("Benvenuto nel sistema di analisi obbligazionaria accademica.")
    if st.button("ACCEDI AL TERMINALE"): st.session_state.access = True; st.rerun()
else:
    # LEGENDA DI AIUTO
    with st.expander("📖 LEGENDA: Come scegliere la categoria corretta", expanded=False):
        st.markdown("""
        | Se l'ISIN inizia per... | E il titolo è... | Scegli questa Categoria |
        | :--- | :--- | :--- |
        | **IT**... | Un BTP, BOT o BTP Valore | `🇮🇹 Titoli di Stato Italiani` |
        | **IT**... / **XS**... | Emesso da Intesa, Unicredit, etc. | `🏦 Obbligazioni Bancarie Italiane` |
        | **US**... / **IT**... | Emesso da Goldman Sachs, Morgan Stanley, etc. | `🇪🇺 Banche Estere ed Internazionali` |
        | **XS**... / **IT**... | Emesso da Enel, Eni, Stellantis, Telecom | `🏭 Aziende (Corporate, Auto, Energy...)` |
        | **US** / **DE** / **RO** | Uno Stato estero (USA, Germania, Romania) | `🌍 Stati Esteri` |
        | **Qualsiasi** | Uno Zero Coupon o un titolo Subordinato | `💎 Titoli Speciali` |
        """)

    st.divider()

    # LAYOUT DI RICERCA
    col_cat, col_isin, col_tax, col_btn = st.columns([2, 1.5, 1, 1])

    with col_cat:
        cat = st.selectbox("1. Seleziona Mercato", options=list(SOURCES_MAP.keys()))
    
    with col_isin:
        isin = st.text_input("2. Inserisci ISIN", placeholder="Es: IT0005566408").strip().upper()
    
    with col_tax:
        # Suggerimento automatico tassazione
        default_tax_index = 0 if "Stato" in cat or "Stati" in cat else 1
        tax = st.radio("3. Tassazione", [12.5, 26.0], index=default_tax_index, horizontal=True)
    
    with col_btn:
        st.write("") # Spazio estetico
        btn = st.button("ANALIZZA 🚀", use_container_width=True)

    # ... (Resto del codice per i risultati e grafici) ...
