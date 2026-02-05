import pandas as pd
import requests
import datetime
import time
from scipy import optimize

# ==============================================================================
# 1. CONFIGURAZIONE: LINK DA ANALIZZARE
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR"
]

# ==============================================================================
# 2. MOTORE DI SCARICAMENTO (ROBUSTO E CAMUFFATO)
# ==============================================================================
def costruisci_database_unificato():
    print(f"📥 Avvio scaricamento dati da {len(PAGINE_DA_ANALIZZARE)} fonti...")
    
    database_totale = pd.DataFrame()
    
    # Maschera completa da Browser Reale per evitare blocchi
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    with requests.Session() as s:
        s.headers.update(headers)
        
        for url in PAGINE_DA_ANALIZZARE:
            # Estrai nome per log
            try: nome_monitor = url.split("monitor=")[1].split("&")[0]
            except: nome_monitor = "Pagina"
            
            print(f"   ...connessione a: {nome_monitor}...", end="\r")
            
            try:
                r = s.get(url, timeout=15)
                
                # Controllo Anti-Ban
                if r.status_code != 200:
                    print(f"\n❌ Errore HTTP {r.status_code} su {nome_monitor} (Accesso negato)")
                    continue

                # Lettura tabelle con Pandas
                # Usiamo 'lxml' se disponibile, altrimenti default
                try:
                    tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                except ValueError:
                    print(f"\n⚠️ Nessuna tabella trovata su {nome_monitor}")
                    continue

                # --- RICERCA INTELLIGENTE ---
                # Non prendiamo la più lunga a caso. Cerchiamo quella con la colonna ISIN.
                tabella_trovata = False
                for df in tabelle:
                    df.columns = df.columns.str.strip() # Pulisce spazi
                    
                    if 'ISIN' in df.columns:
                        # Converti ISIN in stringa per evitare errori di formato
                        df['ISIN'] = df['ISIN'].astype(str)
                        database_totale = pd.concat([database_totale, df], ignore_index=True)
                        tabella_trovata = True
                        break # Trovata la tabella giusta in questa pagina, esco dal loop tabelle
                
                if not tabella_trovata:
                    print(f"\n⚠️ Tabella dati non trovata su {nome_monitor} (Il sito potrebbe aver cambiato layout)")

                # Pausa di cortesia per non sembrare un attacco DDoS
                time.sleep(1)

            except Exception as e:
                print(f"\n⚠️ Errore tecnico su {nome_monitor}: {e}")
                continue
            
    print(f"\n✅ DATABASE PRONTO. Titoli caricati in memoria: {len(database_totale)}")
    return database_totale

# ==============================================================================
# 3. CALCOLO FINANZIARIO (TIR / XIRR)
# ==============================================================================
def calcola_tir_netto(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000
    oggi = datetime.date.today()
    
    # Uscita iniziale (Prezzo di acquisto)
    flussi = [-nominale * (prezzo/100)]
    date_flussi = [oggi]
    
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    # Generazione timeline dei pagamenti
    cursor = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # All'ultima data ricevi: Ultima Cedola + Capitale + Eventuale guadagno tassato
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            rimborso = nominale - tassa_gain
            
            flussi.append(cedola_netta + rimborso)
            date_flussi.append(dt)
            break
        else:
            # Cedola annuale standard
            flussi.append(cedola_netta)
            date_flussi.append(dt)

    # Funzione Matematica XIRR
    def xirr(cf, dts):
        dts_days = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts_days)]), 0.05)
        except: return 0
        
    return xirr(flussi, date_flussi) * 100

# ==============================================================================
# 4. INTERFACCIA UTENTE
# ==============================================================================
def main():
    # 1. Scarica database (con gestione errori)
    db = costruisci_database_unificato()
    
    if db.empty:
        print("\n⛔ IMPOSSIBILE PROSEGUIRE: Database vuoto.")
        print("Consiglio: Controlla la tua connessione internet o riprova più tardi.")
        return

    while True:
        print("\n" + "="*50)
        isin_input = input("🔎 Inserisci ISIN (o 'exit' per uscire): ").strip()
        
        if isin_input.lower() in ['exit', 'esci', 'stop']:
            print("👋 Alla prossima!")
            break
            
        # 2. Cerca nel database
        riga = db[db['ISIN'] == isin_input]
        
        if riga.empty:
            print(f"❌ ISIN {isin_input} non trovato.")
            
            # Opzione manuale in caso di fallimento
            risposta = input("   Vuoi inserire i dati manualmente? (s/n): ").lower()
            if risposta == 's':
                try:
                    p = float(input("   💰 Prezzo (es. 98.50): ").replace(',', '.'))
                    c = float(input("   🎫 Cedola % (es. 3.50): ").replace(',', '.')) / 100
                    s_str = input("   📅 Scadenza (GG/MM/AAAA): ")
                    s = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
                    
                    t = input("   È Titolo di Stato? (s/n): ").lower()
                    tax = 12.5 if t == 's' else 26.0
                    
                    res = calcola_tir_netto(p, c, s, tax)
                    print(f"\n🚀 RENDIMENTO NETTO REALE (Manuale): {res:.2f}%")
                except Exception as e:
                    print(f"Errore inserimento: {e}")
            continue
            
        # 3. Estrai dati (se trovato)
        try:
            # Gestione colonne con nomi variabili (Price/Last/Bid)
            cols = riga.columns
            prezzo = 0.0
            if 'Price' in cols: prezzo = float(str(riga.iloc[0]['Price']).replace(',', '.'))
            elif 'Last' in cols: prezzo = float(str(riga.iloc[0]['Last']).replace(',', '.'))
            elif 'Bid' in cols: prezzo = float(str(riga.iloc[0]['Bid']).replace(',', '.'))
            
            # Gestione Cedola (pulizia caratteri strani)
            c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
            if c_raw in ['ZC', 'zero', '-', 'nan', 'None']: 
                cedola = 0.0
            else:
                cedola = float(c_raw.replace(',', '.')) / 100
                
            # Gestione Scadenza
            s_str = str(riga.iloc[0]['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            
            nome = riga.iloc[0]['Name'] if 'Name' in cols else "Obbligazione"

            # Output Dati
            print("-" * 40)
            print(f"📄 Titolo:   {nome}")
            print(f"💰 Prezzo:   {prezzo}")
            print(f"🎫 Cedola:   {cedola*100:.2f}%")
            print(f"📅 Scadenza: {scadenza.strftime('%d/%m/%Y')}")
            print("-" * 40)
            
            

            # Domanda Tasse
            tipo = input("È un Titolo di Stato (BTP/BOT/Bund...)? [s/n]: ").lower()
            tasse = 12.5 if tipo == 's' else 26.0
            
            # Calcolo Finale
            rendimento = calcola_tir_netto(prezzo, cedola, scadenza, tasse)
            
            print(f"\n🚀 RENDIMENTO NETTO REALE: {rendimento:.2f}%")
            
        except Exception as e:
            print(f"⚠️ Errore nel leggere i dati del titolo: {e}")

if __name__ == "__main__":
    main()
