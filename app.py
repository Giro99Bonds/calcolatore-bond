import pandas as pd
import requests
import datetime
import numpy as np
import matplotlib.pyplot as plt
from scipy import optimize

# ==============================================================================
# 1. LINK AI MONITOR (La tua "Miniera Dati")
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 2. MOTORE SCARICAMENTO DATI
# ==============================================================================
def scarica_database():
    print(f"📥 Scarico i listini aggiornati...")
    db = pd.DataFrame()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in PAGINE_DA_ANALIZZARE:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            tabelle = pd.read_html(r.text, thousands='.', decimal=',')
            if tabelle:
                df = max(tabelle, key=len)
                df.columns = df.columns.str.strip()
                if 'ISIN' in df.columns:
                    db = pd.concat([db, df], ignore_index=True)
        except: continue
    
    print(f"✅ Database pronto: {len(db)} obbligazioni indicizzate.\n")
    return db

# ==============================================================================
# 3. ANALISI FINANZIARIA AVANZATA
# ==============================================================================
def analizza_bond(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000 # Lotto minimo standard
    oggi = datetime.date.today()
    
    # --- A. CALCOLO RATEO (Stima Semplificata) ---
    # Per essere precisi al centesimo servirebbe la data godimento esatta.
    # Qui stimiamo il rateo su base annuale standard (30/360 approx per semplicità)
    # Se la cedola è 0 (ZC), rateo è 0.
    rateo_netto = 0.0
    if cedola > 0:
        # Assumiamo cedola annuale come worst-case per il rateo massimo, 
        # oppure calcoliamo giorni da inizio anno se non abbiamo data stacco precedente.
        # Per semplicità in questo script: rateo = 0 (Il prezzo TEL QUEL lo vede l'utente in banca).
        # Ma visualizziamo che l'utente paga Prezzo + Commissioni.
        pass 

    # --- B. COSTRUZIONE PIANO CEDOLARE ---
    flussi = []     # Importi
    date_f = []     # Date
    tipi = []       # Label (Cedola o Rimborso)
    
    # 1. Uscita Iniziale
    investimento = -nominale * (prezzo/100)
    flussi.append(investimento)
    date_f.append(oggi)
    tipi.append("Acquisto")
    
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    # 2. Generazione Flussi Futuri
    cursor = today_f = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Calcolo Tasse su Capital Gain (se comprato sotto 100)
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            rimborso_netto = nominale - tassa_gain
            
            flussi.append(cedola_netta + rimborso_netto)
            date_f.append(dt)
            tipi.append("Cedola + Rimborso")
            break
        else:
            flussi.append(cedola_netta)
            date_f.append(dt)
            tipi.append("Cedola")

    # --- C. CALCOLO RENDIMENTO (XIRR) ---
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0
    
    rend_netto = xirr(flussi, date_f)
    
    # --- D. CALCOLO DURATION (Sensibilità) ---
    # Macaulay Duration semplificata (media ponderata dei tempi)
    numeratore = 0
    denominatore = 0
    for i in range(1, len(flussi)): # Saltiamo l'acquisto (indice 0)
        t_anni = (date_f[i] - oggi).days / 365.25
        valore_att = flussi[i] / ((1 + rend_netto)**t_anni)
        numeratore += t_anni * valore_att
        denominatore += valore_att
        
    duration = numeratore / denominatore if denominatore != 0 else 0
    modified_duration = duration / (1 + rend_netto)

    # --- E. DATAFRAME FLUSSI (Per visualizzazione) ---
    df_flussi = pd.DataFrame({
        "Data": date_f,
        "Tipo": tipi,
        "Importo Netto (€)": [round(f, 2) for f in flussi]
    })
    
    # Guadagno Totale in Euro
    profitto_totale = sum(flussi)

    return {
        "rendimento": rend_netto * 100,
        "duration": modified_duration,
        "profitto_euro": profitto_totale,
        "df_flussi": df_flussi,
        "investimento": investimento
    }

# ==============================================================================
# 4. DASHBOARD GRAFICA (VISUALIZZAZIONE)
# ==============================================================================
def mostra_dashboard(dati_analisi, nome_bond):
    df = dati_analisi["df_flussi"]
    investimento = abs(dati_analisi["investimento"])
    profitto = dati_analisi["profitto_euro"]
    
    print("\n" + "="*60)
    print(f" 📊 REPORT ANALISI: {nome_bond}")
    print("="*60)
    
    # SEZIONE 1: KPI PRINCIPALI
    print(f"🔹 RENDIMENTO NETTO ANNUO:  {dati_analisi['rendimento']:.2f}%")
    print(f"🔹 DURATION (RISCHIO):      {dati_analisi['duration']:.2f} anni")
    print(f"   (Se i tassi salgono dell'1%, il prezzo scende di circa il {dati_analisi['duration']:.2f}%)")
    print(f"🔹 GUADAGNO TOTALE PULITO:  {profitto:+.2f} € (su 1000€ investiti)")
    print("-" * 60)
    
    # SEZIONE 2: TABELLA FLUSSI (Primi 5 e ultimi 5 se lunga)
    print("📅 PIANO DEI PAGAMENTI (Cash Flow):")
    if len(df) > 10:
        print(df.head(5).to_string(index=False))
        print("... (altre cedole) ...")
        print(df.tail(3).to_string(index=False))
    else:
        print(df.to_string(index=False))
    print("-" * 60)

    # SEZIONE 3: GRAFICO
    print("📈 Generazione grafico flussi in corso...")
    
    colors = ['red' if x < 0 else 'green' for x in df["Importo Netto (€)"]]
    
    plt.figure(figsize=(10, 6))
    
    # Bar Chart
    plt.bar(df["Data"], df["Importo Netto (€)"], color=colors, width=100)
    
    # Linea cumulativa (Break-even)
    cumsum = df["Importo Netto (€)"].cumsum()
    plt.plot(df["Data"], cumsum, color='blue', marker='o', linestyle='--', label='Saldo Cumulativo')
    
    plt.axhline(0, color='black', linewidth=0.8)
    plt.title(f"Analisi Flussi: {nome_bond}\nRendimento Netto: {dati_analisi['rendimento']:.2f}%")
    plt.xlabel("Data")
    plt.ylabel("Euro (€)")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend()
    
    # Formattazione Date asse X
    plt.gcf().autofmt_xdate()
    
    plt.show()

# ==============================================================================
# 5. LOOP PRINCIPALE
# ==============================================================================
if __name__ == "__main__":
    db = scarica_database()
    
    while True:
        isin = input("\n🔎 Inserisci ISIN (o 'exit'): ").strip()
        if isin.lower() == 'exit': break
        
        riga = db[db['ISIN'] == isin]
        
        if riga.empty:
            print("❌ ISIN non trovato.")
            # Qui potresti attivare l'input manuale se vuoi
            continue
            
        try:
            # Estrazione Dati
            prezzo = float(str(riga.iloc[0]['Price' if 'Price' in riga.columns else 'Last']).replace(',', '.'))
            c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
            cedola = 0.0 if c_raw in ['ZC', 'zero'] else float(c_raw.replace(',', '.')) / 100
            s_str = str(riga.iloc[0]['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            nome = riga.iloc[0]['Name'] if 'Name' in riga.columns else isin
            
            # Input Tasse
            tipo = input("È Titolo di Stato? [s/n]: ").lower()
            tasse = 12.5 if tipo == 's' else 26.0
            
            # Analisi e Visualizzazione
            risultati = analizza_bond(prezzo, cedola, scadenza, tasse)
            mostra_dashboard(risultati, nome)
            
        except Exception as e:
            print(f"⚠️ Errore dati: {e}")
