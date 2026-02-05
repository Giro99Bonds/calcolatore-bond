import pandas as pd
import requests
import datetime
import time
import random
from scipy import optimize

# ==============================================================================
# 1. CONFIGURAZIONE
# ==============================================================================
PAGINE_DA_ANALIZZARE = [
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia_inflation&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=europe&yieldtype=G&timescale=DUR",
    "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR",
    # "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR" # Commentato per velocizzare test
]

# ==============================================================================
# 2. MOTORE DI SCARICAMENTO (DIAGNOSTICO)
# ==============================================================================
def costruisci_database_diagnostico():
    print(f"\n📥 AVVIO SCARICAMENTO DATI (Modalità Diagnostica)...")
    
    database_totale = pd.DataFrame()
    
    # Headers aggiornati
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    with requests.Session() as s:
        s.headers.update(headers)
        
        for i, url in enumerate(PAGINE_DA_ANALIZZARE):
            # Piccolo ritardo per non farsi bloccare
            if i > 0: time.sleep(random.uniform(1.5, 3.0))
            
            nome_monitor = url.split("monitor=")[1].split("&")[0].upper()
            print(f"   ⏳ Leggo {nome_monitor}...", end="")
            
            try:
                r = s.get(url, timeout=15)
                
                # DIAGNOSTICA: Controlliamo se la pagina è vuota
                if len(r.text) < 1000:
                    print(f" ❌ (Pagina troppo corta/vuota! Probabile blocco IP)")
                    continue
                
                tabelle = pd.read_html(r.text, thousands='.', decimal=',')
                
                righe_aggiunte = 0
                for df in tabelle:
                    # Pulizia colonne
                    df.columns = df.columns.str.strip()
                    
                    if 'ISIN' in df.columns:
                        # Pulizia DATI (Rimuove spazi dagli ISIN)
                        df['ISIN'] = df['ISIN'].astype(str).str.strip().str.upper()
                        
                        database_totale = pd.concat([database_totale, df], ignore_index=True)
                        righe_aggiunte = len(df)
                        break
                
                if righe_aggiunte > 0:
                    print(f" ✅ OK ({righe_aggiunte} titoli)")
                else:
                    print(f" ⚠️ (Nessuna tabella ISIN trovata)")

            except Exception as e:
                print(f" ❌ Errore: {e}")
                continue

    num_totale = len(database_totale)
    print(f"\n📊 STATO DATABASE: {num_totale} titoli caricati in memoria.")
    
    if num_totale > 0:
        print(f"   Esempio titoli caricati: {database_totale['ISIN'].head(3).tolist()}")
    else:
        print("\n⛔ ATTENZIONE: Il database è vuoto!")
        print("   Motivo probabile: Il sito ha bloccato temporaneamente il tuo IP per troppe richieste.")
        print("   Soluzione: Aspetta 10 minuti o cambia connessione (es. usa hotspot telefono).")
    
    return database_totale

# ==============================================================================
# 3. MOTORE DI CALCOLO
# ==============================================================================
def calcola_rendimento_netto(prezzo, cedola, scadenza, tasse=12.5):
    nominale = 1000
    oggi = datetime.date.today()
    flussi = [-nominale * (prezzo/100)]
    date_flussi = [oggi]
    cedola_netta = (cedola * nominale) * (1 - tasse/100)
    
    cursor = oggi
    while True:
        try: cursor = cursor.replace(year=cursor.year + 1)
        except: cursor = cursor + datetime.timedelta(days=365)
        if cursor > scadenza: break
        dt = scadenza if cursor >= scadenza else cursor
        
        if dt == scadenza:
            gain = max(0, 100 - prezzo)
            tassa_gain = gain * (tasse/100) * (nominale/100)
            flussi.append(cedola_netta + (nominale - tassa_gain))
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
    db = costruisci_database_diagnostico()
    
    if db.empty: return # Si ferma se non c'è nulla

    while True:
        print("\n" + "="*50)
        isin_input = input("🔎 Inserisci ISIN (o parte di esso): ").strip().upper()
        if isin_input in ['EXIT', 'ESCI']: break
            
        # --- RICERCA FLESSIBILE ("CONTAINS") ---
        # Invece di == usiamo .str.contains()
        risultati = db[db['ISIN'].str.contains(isin_input, na=False)]
        
        if risultati.empty:
            print(f"❌ Nessun risultato per '{isin_input}'")
            print("   (Suggerimento: Prova a scrivere meno caratteri, es. solo le prime 5 lettere)")
            continue
            
        # Se trova più risultati (o uno solo)
        if len(risultati) > 1:
            print(f"⚠️ Ho trovato {len(risultati)} titoli simili. Analizzo il primo della lista:")
            print(f"   (Trovati: {risultati['ISIN'].tolist()[:3]}...)")
        
        # Prende il primo risultato
        riga = risultati.iloc[0]
        
        try:
            # Estrazione Dati
            isin_trovato = riga['ISIN']
            
            # Prezzo
            cols = riga.index
            if 'Price' in cols: p_raw = riga['Price']
            elif 'Last' in cols: p_raw = riga['Last']
            else: p_raw = riga['Bid']
            prezzo = float(str(p_raw).replace(',', '.'))
            
            # Cedola
            c_raw = str(riga['Coupon']).replace('%', '').strip().split(' ')[0]
            cedola = 0.0 if c_raw in ['ZC', 'zero', '-'] else float(c_raw.replace(',', '.')) / 100
            
            # Scadenza
            s_str = str(riga['Maturity'])
            scadenza = datetime.datetime.strptime(s_str, "%d/%m/%Y").date()
            
            nome = riga['Name'] if 'Name' in cols else "Bond"
            
            print("-" * 40)
            print(f"✅ TROVATO:  {isin_trovato}")
            print(f"📄 Nome:     {nome}")
            print(f"💰 Prezzo:   {prezzo}")
            print(f"🎫 Cedola:   {cedola*100:.2f}%")
            print(f"📅 Scadenza: {scadenza}")
            print("-" * 40)
            
            tipo = input("È Titolo di Stato? (s/n): ").lower()
            tasse = 12.5 if tipo == 's' else 26.0
            
            res = calcola_rendimento_netto(prezzo, cedola, scadenza, tasse)
            print(f"\n🚀 RENDIMENTO NETTO: {res:.2f}%")
            
        except Exception as e:
            print(f"⚠️ Errore lettura dati: {e}")

if __name__ == "__main__":
    main()
