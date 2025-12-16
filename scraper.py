import requests
from bs4 import BeautifulSoup
import re
import time
import db_updater

def run_scraper():
    print("[SCRAPER] Pobieram dane z Bankier.pl...")
    url = "https://www.bankier.pl/inwestowanie/profile/quote.html?symbol=WIG20"

    # 1. PRZEBRANIE (User-Agent) - Kluczowe, żeby nie zostać zablokowanym
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[SCRAPER] Błąd połączenia: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    
    # 2. DEBUG - Sprawdźmy, gdzie wylądowaliśmy
    page_title = soup.title.string.strip() if soup.title else "Brak tytułu"
    print(f"[DEBUG] Tytuł strony: '{page_title}'")

    # Szukamy tabeli z notowaniami
    rows = soup.find_all("tr")
    
    symbols = []
    values = []
    marketcaps = []

    print(f"👀 [DEBUG] Analizuję {len(rows)} wierszy...")

    for row in rows:
        # Konwersja wiersza na tekst, żeby użyć regexów Twojego kolegi
        text = str(row)
        
        # Szukamy linku z symbolem (np. ?symbol=PKN)
        # To jest filtr, który pozwala odróżnić wiersze z danymi od nagłówków
        if "?symbol=" in text:
            try:
                # REGEX 1: Wyciąganie Symbolu (np. KGHM)
                symbol_match = re.search(r'\?symbol=([A-Z0-9]+)', text)
                if not symbol_match: continue
                symbol = symbol_match.group(1)
                
                # Jeśli to WIG20 (indeks), to pomijamy, szukamy spółek
                if symbol == "WIG20": continue

                # REGEX 2: Wyciąganie Ceny (szukamy liczby przed zamknięciem komórki)
                # Uprościłem regex, żeby był mniej wrażliwy na spacje
                value_match = re.search(r'>\s*(\d+[\s\xa0]?\d*,\d+)\s*<', text)
                if not value_match: continue
                
                raw_value = value_match.group(1)
                value = raw_value.replace(',', '.').replace('\xa0', '').replace(' ', '')
                val_float = float(value)

                # Dla uproszczenia (bo scraper kolegi miał tu skomplikowaną logikę wolumenu)
                # Przyjmijmy fikcyjny Market Cap, żeby nie wywalać błędu, 
                # albo (lepiej) zapiszmy samą cenę.
                # Tutaj: Kapitalizacja = Cena * 1000000 (symulacja, bo bankier w tym widoku nie podaje liczby akcji)
                cap = int(val_float * 1000000)

                symbols.append(symbol)
                values.append(val_float)
                marketcaps.append(cap)
                
            except Exception as e:
                # Cichy błąd przy jednym wierszu nie powinien zatrzymać całości
                continue

    # 3. WYNIKI
    if symbols:
        print(f"[SCRAPER] Znalazłem {len(symbols)} spółek (np. {symbols[0]}: {values[0]} PLN).")
        db_updater.insert(values, symbols, marketcaps)
    else:
        print("[SCRAPER] Tabela pusta. Prawdopodobnie zmieniła się struktura strony lub regex nie pasuje.")
        # Wypisz kawałek HTML dla debugowania
        print(f"💀 [HTML DUMP] Początek tabeli: {str(soup)[:500]}")

if __name__ == "__main__":
    print("🚀 [SYSTEM] Uruchamiam Scraper v2.0...")
    time.sleep(5) 
    while True:
        try:
            run_scraper()
        except Exception as e:
            print(f"💀 [CRITICAL] Błąd: {e}")
        print("💤 Czekam 60 sekund...")
        time.sleep(60)