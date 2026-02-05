import pandas as pd
import requests
import datetime
import time
import random  # <--- Per generare ritardi casuali
from scipy import optimize

# ==============================================================================
# 1. CONFIGURAZIONE LINK
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 2. MOTORE DI SCARICAMENTO "UMANO"
# ==============================================================================
def costruisci_database_stealth():
    print(f"🕵️‍♂️ Avvio scaricamento 'Stealth' da {len(PAGINE_DA_ANALIZZARE)} fonti...")
    print("⏳ Nota: Il processo sarà volutamente lento per evitare blocchi.")
    
    database_totale = pd.DataFrame()
    
    # Headers completi per sembrare un vero Chrome su Windows
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://google.com",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # Usiamo una Sessione per mantenere i cookie (come un browser vero)
    with requests.Session() as session:
        session.headers.update(headers)
        
        for i, url in enumerate(PAGINE_DA_ANALIZZARE):
            try:
                # Estrai il nome della pagina dall'URL per stamparlo
                nome_monitor = url.split("monitor=")[1].split("&")[0].upper()
                
                # --- LA PARTE FONDAMENTALE: IL RITARDO CASUALE ---
                # Se non è la prima pagina, aspettiamo un po'
                if i > 0:
                    tempo_attesa = random.uniform(2.5, 5.5) # Ritardo casuale tra 2.5 e 5.5 secondi
                    print(f"☕ Pause caffè... ({tempo_attesa:.1f}s)", end="\r")
                    time.sleep(tempo_attesa)
                
                print(f"📥 Scarico: {nome_monitor:<20}...", end="\r")
                
                response = session.get(url, timeout=20)
                
                if response.status_code == 200:
                    # Legge le tabelle
                    tabelle = pd.read_html(response.text, thousands='.', decimal=',')
                    
                    # Cerca la tabella giusta (quella con ISIN)
                    for df in tabelle:
                        df.columns = df.columns.str.strip() # Pulisce spazi nei nomi colonne
                        if 'ISIN' in df.columns:
                            # Trovata! Pulizia preventiva
                            df['ISIN'] = df['ISIN'].astype(str) # Forza ISIN come testo
                            database_totale = pd.concat([database_totale, df], ignore_index=True)
                            break 
                else:
                    print(f"\n❌ Blocco Server su {nome_monitor} (Status: {response.status_code})")

            except Exception as e:
                print(f"\n⚠️ Errore su {url}: {e}")
                continue

    print(f"\n✅ DATABASE COMPLETATO. {len(database_totale)} titoli pronti per l'analisi.")
    return database_totale

# ==============================================================================
# 3. MOTORE MATEMATICO (Calcolo Rendimento Netto)
# ==============================================================================
def calcola_rendimento_netto(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000
    oggi = datetime.date.today()
    
    flussi = [-nominale * (prezzo/100)]
    date_flussi = [oggi]
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    cursor = today_f = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            rimborso = nominale - tassa_gain
            flussi.append(cedola_netta + rimborso)
            date_flussi.append(dt)
            break
        else:
            flussi.append(cedola_netta)
            date_flussi.append(dt)

    def xirr(cf, dts):
        dts = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts)]), 0.05)
        except: return 0
        
    return xirr(flussi, date_flussi) * 100

# ==============================================================================
# 4. INTERFACCIA
# ==============================================================================
def main():
    # 1. Scarica i dati in modalità lenta/sicura
    db = costruisci_database_stealth()
    
    if db.empty:
        print("\n⛔ ERRORE CRITICO: Nessun dato scaricato. Riprova più tardi.")
        return

    while True:
        print("\n" + "="*50)
        isin_input = input("🔎 Inserisci ISIN (o 'exit'): ").strip()
        
        if isin_input.lower() in ['exit', 'esci']: break
            
        riga = db[db['ISIN'] == isin_input]
        
        if riga.empty:
            print(f"❌ ISIN {isin_input} non trovato.")
            # Fallback manuale opzionale
            if input("Vuoi inserire i dati a mano? (s/n): ").lower() == 's':
                 try:
                    p = float(input("   Prezzo: ").replace(',', '.'))
                    c = float(input("   Cedola %: ").replace(',', '.')) / 100
                    s = datetime.datetime.strptime(input("   Scadenza (gg/mm/aaaa): "), "%d/%m/%Y").date()
                    res = calcola_rendimento_netto(p, c, s, 12.5)
                    print(f"   --> Rendimento Manuale: {res:.2f}%")
                 except: pass
            continue
            
        try:
            # Estrazione dati robusta
            cols = riga.columns
            # Prezzo
            if 'Price' in cols: p_raw = riga.iloc[0]['Price']
            elif 'Last' in cols: p_raw = riga.iloc[0]['Last']
            elif 'Bid' in cols: p_raw = riga.iloc[0]['Bid']
            else: p_raw = 0
            prezzo = float(str(p_raw).replace(',', '.'))
            
            # Cedola
            c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
            cedola = 0.0 if c_raw in ['ZC', 'zero', '-'] else float(c_raw.replace(',', '.')) / 100
            
            # Scadenza
            s_str = str(riga.iloc[0]['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            
            nome = riga.iloc[0]['Name'] if 'Name' in cols else "Bond"
            
            print("-" * 40)
            print(f"📄 Titolo:   {nome}")
            print(f"💰 Prezzo:   {prezzo}")
            print(f"🎫 Cedola:   {cedola*100:.2f}%")
            print(f"📅 Scadenza: {scadenza}")
            print("-" * 40)
            
            tipo = input("È Titolo di Stato? (s/n): ").lower()
            tasse = 12.5 if tipo == 's' else 26.0
            
            res = calcola_rendimento_netto(prezzo, cedola, scadenza, tasse)
            print(f"\n🚀 RENDIMENTO NETTO REALE: {res:.2f}%")
            
        except Exception as e:
            print(f"⚠️ Errore lettura dati: {e}")

if __name__ == "__main__":
    main()
