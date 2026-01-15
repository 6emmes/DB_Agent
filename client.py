import requests
import sys
import time

# Adres Twojego API (działa, bo przekierowałeś port 8000)
API_URL = "http://localhost:8000/ask"

# Kolory do terminala (ANSI escape codes)
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def type_writer(text):
    """Efekt pisania na maszynie dla odpowiedzi AI"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.01) # Szybkość pisania
    print()

def main():
    print(f"{BOLD}{GREEN}=========================================={RESET}")
    print(f"{BOLD}{GREEN}   WIG20 INTELLIGENT AGENT v1.0 (ONLINE)   {RESET}")
    print(f"{BOLD}{GREEN}=========================================={RESET}")
    print(f"{YELLOW}Połączono z systemem... Wpisz 'exit' aby wyjść.{RESET}\n")

    while True:
        try:
            # 1. Pobierz pytanie od użytkownika
            user_input = input(f"{CYAN}TY >> {RESET}")
            
            if user_input.lower() in ['exit', 'quit', 'wyjscie']:
                print(f"{RED}Zamykanie sesji... Do widzenia!{RESET}")
                break
            
            if not user_input.strip():
                continue

            print(f"{YELLOW}[System]: Analizuję zapytanie i przeszukuję bazę danych...{RESET}")

            # 2. Wyślij do API
            payload = {"prompt": user_input}
            try:
                response = requests.post(API_URL, json=payload, timeout=120)  # Increased to 2 minutes
                response.raise_for_status()
                data = response.json()
                
                ai_response = data.get("response", "Brak odpowiedzi.")
                used_context = data.get("used_context", "")

            except requests.exceptions.ConnectionError:
                print(f"{RED}BŁĄD: Nie można połączyć się z API. Czy Docker działa?{RESET}")
                continue
            except Exception as e:
                print(f"{RED}BŁĄD: {e}{RESET}")
                continue

            # 3. Wyświetl wynik
            # Opcjonalnie: Pokaż co agent znalazł w bazie (debug)
            if "Cena" in ai_response or "cena" in ai_response.lower() or len(ai_response) > 10:
                print(f"\n{BOLD}[CONTEXT]:{RESET} {used_context[:100]}...")
            else:
                 print(f"\n{BOLD}[CONTEXT]:{RESET} Brak danych w bazie.")

            print(f"\n{GREEN}AGENT >> {RESET}", end="")
            type_writer(ai_response)
            print("-" * 50)

        except KeyboardInterrupt:
            print(f"\n{RED}Przerwano.{RESET}")
            break

if __name__ == "__main__":
    main()