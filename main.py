from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json
import database  # Korzystamy z nowej funkcji w tym pliku

app = FastAPI()

class UserQuery(BaseModel):
    prompt: str

@app.post("/ask")
def ask_agent(query: UserQuery):
    user_text = query.prompt
    
    # --- KROK 1: Dynamiczne szukanie w Bazie Danych ---
    
    # Domyślny kontekst (jeśli nic nie znajdziemy)
    context = "[SYSTEM INFO]: Nie znaleziono w bazie danych żadnych informacji pasujących do zapytania."
    
    # Rozbijamy pytanie na słowa (np. "Jaka jest cena Alior?" -> ["Jaka", "jest", "cena", "Alior?"])
    words = user_text.split()
    
    found_data = None
    
    for word in words:
        # Czyścimy słowo ze śmieci (np. "Orlenu?" -> "ORLENU")
        clean_word = word.strip("?,.!").upper()
        
        # Ignorujemy krótkie słowa (np. "CZY", "PO", "JAK"), żeby nie męczyć bazy
        if len(clean_word) < 3:
            continue
            
        # Szukamy tego słowa w bazie
        # Szukamy np. "%ORLENU%" - jeśli w bazie jest PKNORLEN, to może nie znaleźć,
        # ale jeśli wpiszesz "Alior" to znajdzie "ALIOR".
        # Warto spróbować też skrótów, np. wpisując "PKN".
        result = database.get_stock_price(clean_word)
        
        if result:
            found_data = result
            # Jeśli znaleźliśmy firmę, przerywamy pętlę (nie szukamy dalej)
            break
            
    # Jeśli coś znaleźliśmy, nadpisujemy kontekst
    if found_data:
        ticker = found_data['name']
        price = found_data['price']
        context = f"[SYSTEM INFO]: Znaleziono w bazie spółkę {ticker}. Jej najnowsza cena rynkowa to {price} PLN."

    # --- KROK 2: Przygotowanie Promptu dla AI ---
    
    system_instruction = (
        "Jesteś asystentem giełdowym WIG20. "
        "Poniżej otrzymasz informacje z bazy danych oznaczone jako [SYSTEM INFO]. "
        "Twoim zadaniem jest odpowiedzieć na pytanie użytkownika WYŁĄCZNIE w oparciu o te informacje. "
        "Jeśli w [SYSTEM INFO] jest podana cena, podaj ją użytkownikowi. "
        "Jeśli informacji nie ma, powiedz krótko, że nie posiadasz tych danych."
    )

    full_prompt = f"{system_instruction}\n\nKONTEKST:\n{context}\n\nPYTANIE UŻYTKOWNIKA:\n{user_text}"

    # --- KROK 3: Wysłanie do Ollamy ---
    
    ollama_url = "http://ollama:11434/api/generate"
    payload = {
        "model": "qwen3:1.7b",
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(ollama_url, json=payload)
        response.raise_for_status()
        ai_reply = response.json().get("response", "")
    except Exception as e:
        ai_reply = f"Błąd komunikacji z modelem AI: {str(e)}"

    return {
        "response": ai_reply,
        "used_context": context
    }