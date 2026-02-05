import pandas as pd
import requests
import datetime
from scipy import optimize

# ==============================================================================
# 1. CONFIGURAZIONE: INCOLLA QUI I TUOI LINK
# ==============================================================================
# Puoi aggiungere quante righe vuoi tra le virgolette.
# Lo script scaricherà TUTTE queste tabelle e cercherà il tuo ISIN in mezzo a tutte.

PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    # Aggiungi qui altri link se vuoi (Spagna, Corporate, ecc.)
]

# ==============================================================================
# 2. IL MOTORE DI SCARICAMENTO (SCARICA TUTTO IN BLOCCO)
# ==============================================================================
def costruisci_database_unificato():
    print(f"📥 Sto scaricando i dati da {len(PAGINE_DA_ANALIZZARE)} pagine diverse...")
    
    database_totale = pd.DataFrame()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for url in PAGINE_DA_ANALIZZARE:
        try:
            print(f"   ...leggo: {url[-40:]}...", end="\r") # Stampa solo la parte finale del link
            r = requests.get(url, headers=headers, timeout=10)
            
            # Pandas legge tutte le tabelle
            tabelle = pd.read_html(r.text, thousands='.', decimal=',')
            
            # Prendiamo la tabella più grande della pagina (quella con i dati)
            if tabelle:
                df = max(tabelle, key=len)
                # Uniformiamo i nomi delle colonne (toglie spazi extra)
                df.columns = df.columns.str.strip()
                
                # Se c'è la colonna ISIN, aggiungiamo al database totale
                if 'ISIN' in df.columns:
                    database_totale = pd.concat([database_totale, df], ignore_index=True)
                    
        except Exception as e:
            print(f"\n⚠️ Errore su un link: {e}")
            continue
            
    print(f"\n✅ DATABASE PRONTO. Titoli caricati in memoria: {len(database_totale)}")
    return database_totale

# ==============================================================================
# 3. IL CERVELLO MATEMATICO (CALCOLO RENDIMENTO)
# ==============================================================================
def calcola_tir_netto(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000
    oggi = datetime.date.today()
    
    flussi = [-nominale * (prezzo/100)]
    date_flussi = [oggi]
    
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    # Generazione date future
    cursor = today_f = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        
        if cursor > scadenza: break
        
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            # Rimborso + Cedola + Tasse su Capital Gain (se prezzo < 100)
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            rimborso = nominale - tassa_gain
            flussi.append(cedola_netta + rimborso)
            date_flussi.append(dt)
            break
        else:
            flussi.append(cedola_netta)
            date_flussi.append(dt)

    # Funzione XIRR
    def xirr(cf, dts):
        dts = [(d - dts[0]).days for d in dts]
        try: return optimize.newton(lambda r: sum([v/(1+r)**(d/365) for v,d in zip(cf, dts)]), 0.05)
        except: return 0
        
    return xirr(flussi, date_flussi) * 100

# ==============================================================================
# 4. INTERFACCIA UTENTE (LOOP DI RICERCA)
# ==============================================================================
def main():
    # 1. Scarica tutto all'avvio
    db = costruisci_database_unificato()
    
    while True:
        print("\n" + "="*50)
        isin_input = input("🔎 Inserisci ISIN (o 'exit'): ").strip()
        
        if isin_input.lower() in ['exit', 'esci']:
            break
            
        # 2. Cerca nel database scaricato
        # Filtriamo il DataFrame per l'ISIN cercato
        riga = db[db['ISIN'] == isin_input]
        
        if riga.empty:
            print("❌ ISIN non trovato nelle pagine fornite.")
            # Fallback manuale opzionale
            scelta = input("Vuoi inserire i dati a mano? (s/n): ").lower()
            if scelta == 's':
                 # Qui potresti chiamare la funzione manuale se vuoi
                 pass
            continue
            
        # 3. Estrai dati (Prende la prima occorrenza trovata)
        try:
            # --- ESTRAZIONE INTELLIGENTE PREZZO ---
            # Il sito cambia nome colonna a volte: Price, Last, Bid
            prezzo = 0.0
            cols = riga.columns
            if 'Price' in cols: prezzo = float(str(riga.iloc[0]['Price']).replace(',', '.'))
            elif 'Last' in cols: prezzo = float(str(riga.iloc[0]['Last']).replace(',', '.'))
            elif 'Bid' in cols: prezzo = float(str(riga.iloc[0]['Bid']).replace(',', '.'))
            
            # --- ESTRAZIONE CEDOLA ---
            # Pulisce stringhe tipo "4,5%" o "ZC"
            c_raw = str(riga.iloc[0]['Coupon']).replace('%', '').strip().split(' ')[0]
            if c_raw in ['ZC', 'zero', '-']: 
                cedola = 0.0
            else:
                cedola = float(c_raw.replace(',', '.')) / 100
                
            # --- ESTRAZIONE SCADENZA ---
            s_str = str(riga.iloc[0]['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            
            nome = riga.iloc[0]['Name'] if 'Name' in cols else "Titolo"

            print("-" * 40)
            print(f"📄 Titolo:   {nome}")
            print(f"💰 Prezzo:   {prezzo}")
            print(f"🎫 Cedola:   {cedola*100}%")
            print(f"📅 Scadenza: {scadenza}")
            print("-" * 40)
            
            # --- DOMANDA TASSE ---
            tipo = input("È un Titolo di Stato (BTP/BOT/Bund...)? [s/n]: ").lower()
            tasse = 12.5 if tipo == 's' else 26.0
            
            # --- CALCOLO ---
            rendimento = calcola_tir_netto(prezzo, cedola, scadenza, tasse)
            
            print(f"\n🚀 RENDIMENTO NETTO REALE: {rendimento:.2f}%")
            
        except Exception as e:
            print(f"⚠️ Errore nell'interpretare i dati: {e}")

if __name__ == "__main__":
    main()
