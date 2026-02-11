import pandas as pd
import requests
import os
import random
import time
from datetime import datetime

# ==============================================================================
# CONFIGURAZIONE CARTELLA
# ==============================================================================
DB_FOLDER = "bond_database"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# ==============================================================================
# LISTA COMPLETA DELLE FONTI (TUTTO IL DATASET)
# ==============================================================================
SOURCES_MAP = {
    "GOV_IT": [
        {"nome": "BTP_FISSI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=italia&yieldtype=G&timescale=DUR"},
        {"nome": "BTP_ITALIA_INF", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=btpitalia&yieldtype=G&timescale=DUR"},
        {"nome": "BOT_12M", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bot&yieldtype=G&timescale=DUR"},
        {"nome": "CCT_VARIABILI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=cct&yieldtype=G&timescale=DUR"}
    ],
    "GOV_EU": [
        {"nome": "GERMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=germania&yieldtype=G&timescale=DUR"},
        {"nome": "FRANCIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=francia&yieldtype=G&timescale=DUR"},
        {"nome": "AUSTRIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=austria&yieldtype=G&timescale=DUR"},
        {"nome": "BELGIO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=belgio&yieldtype=G&timescale=DUR"},
        {"nome": "OLANDA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=olanda&yieldtype=G&timescale=DUR"}
    ],
    "GOV_PERIF": [
        {"nome": "SPAGNA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=spagna&yieldtype=G&timescale=DUR"},
        {"nome": "PORTOGALLO", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=portogallo&yieldtype=G&timescale=DUR"},
        {"nome": "GRECIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=grecia&yieldtype=G&timescale=DUR"},
        {"nome": "ALTRI_EUROPA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=altri_europa&yieldtype=G&timescale=DUR"}
    ],
    "GOV_WORLD": [
        {"nome": "USA_TREASURY", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=usa&yieldtype=G&timescale=DUR"},
        {"nome": "ROMANIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=romania&yieldtype=G&timescale=DUR"},
        {"nome": "TURCHIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=turchia&yieldtype=G&timescale=DUR"},
        {"nome": "BRASILE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=brasile&yieldtype=G&timescale=DUR"},
        {"nome": "UNGHERIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=ungheria&yieldtype=G&timescale=DUR"}
    ],
    "SUPRA": [
        {"nome": "EU_BEI_ESM", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=sovranazionali&yieldtype=G&timescale=DUR"},
        {"nome": "GREEN_BONDS", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=greenbonds&yieldtype=G&timescale=DUR"}
    ],
    "BANCHE": [
        {"nome": "BANCHE_SENIOR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=bancheitalia&yieldtype=G&timescale=DUR"},
        {"nome": "SUBORDINATE_TIER2", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=subordinate&yieldtype=G&timescale=DUR"},
        {"nome": "ASSICURATIVI", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=assicurazioni&yieldtype=G&timescale=DUR"}
    ],
    "CORP": [
        {"nome": "CORP_IG_EUROPE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporate&yieldtype=G&timescale=DUR"},
        {"nome": "CORP_ITALIA", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=corporateitalia&yieldtype=G&timescale=DUR"},
        {"nome": "HIGH_YIELD_EUR", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=highyield&yieldtype=G&timescale=DUR"},
        {"nome": "AUTOMOTIVE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=automotive&yieldtype=G&timescale=DUR"}
    ],
    "SPEC": [
        {"nome": "ZERO_COUPON", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=zerocoupon&yieldtype=G&timescale=DUR"},
        {"nome": "CALLABLE", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=callable&yieldtype=G&timescale=DUR"},
        {"nome": "LUNGHI_25Y+", "url": "https://www.simpletoolsforinvestors.eu/monitor_info.php?monitor=25yearsEUR&yieldtype=G&timescale=DUR"}
    ]
}

# ==============================================================================
# FUNZIONE DI SCARICAMENTO
# ==============================================================================
def scarica_tutto():
    print("🚀 Inizio Scraping Automatico COMPLETO...")
    
    # 1. Pulizia vecchi file per evitare duplicati o dati vecchi
    if os.path.exists(DB_FOLDER):
        for f in os.listdir(DB_FOLDER):
            if f.endswith(".csv"):
                try:
                    os.remove(os.path.join(DB_FOLDER, f))
                except: pass
    
    # Calcolo totale fonti
    tot = sum(len(v) for v in SOURCES_MAP.values())
    count = 0
    successi = 0
    
    # Header per sembrare un browser vero
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for cat, sources in SOURCES_MAP.items():
        print(f"\n--- Categoria: {cat} ---")
        for src in sources:
            count += 1
            nome = src['nome']
            url = src['url']
            
            print(f"[{count}/{tot}] Scarico: {nome}...")
            
            try:
                # Ritardo casuale (1-3 secondi) per non farsi bannare
                time.sleep(random.uniform(1.0, 3.0))
                
                # Richiesta HTTP
                r = requests.get(url, headers=headers, timeout=20)
                
                if r.status_code == 200:
                    # Parsing delle tabelle HTML
                    # Nota: decimal="," e thousands="." sono fondamentali per i siti europei
                    dfs = pd.read_html(r.text, decimal=",", thousands=".")
                    
                    found = False
                    for df in dfs:
                        # Cerchiamo la tabella giusta: deve avere una colonna che contiene "ISIN"
                        cols = [str(c).upper() for c in df.columns]
                        if any('ISIN' in c for c in cols):
                            path = os.path.join(DB_FOLDER, f"{nome}.csv")
                            df.to_csv(path, index=False)
                            print(f"   ✅ Salvato: {path} ({len(df)} righe)")
                            successi += 1
                            found = True
                            break
                    
                    if not found:
                        print(f"   ⚠️ Nessuna tabella valida trovata per {nome}")
                else:
                    print(f"   ❌ Errore HTTP {r.status_code} per {nome}")
                    
            except Exception as e:
                print(f"   ❌ Errore critico su {nome}: {e}")

    print(f"\n🏁 Scraping Completato. Scaricati {successi}/{tot} dataset.")

if __name__ == "__main__":
    scarica_tutto()
