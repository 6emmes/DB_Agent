from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
# Importujemy klienta MCP zamiast bazy danych
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

app = FastAPI()

class UserQuery(BaseModel):
    prompt: str

# Adres serwera MCP (wewnątrz sieci Docker to nazwa usługi "mcp")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp:8001/sse")

async def query_mcp_tool(query_text: str):
    """
    Ta funkcja łączy się z serwerem MCP i prosi go o użycie narzędzia.
    """
    print(f"🔌 Łączenie z MCP pod adresem: {MCP_SERVER_URL}...")
    
    try:
        # Nawiązujemy połączenie z serwerem MCP
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                # 1. Inicjalizacja sesji
                await session.initialize()
                
                # 2. Logika wyboru słowa kluczowego (prosta heurystyka)
                # Szukamy w pytaniu słowa dłuższego niż 2 znaki (potencjalna nazwa spółki)
                words = query_text.split()
                found_info = None
                
                for word in words:
                    clean_word = word.strip("?,.!").upper()
                    if len(clean_word) < 3: continue
                    
                    try:
                        # 3. WYWOŁANIE NARZĘDZIA MCP
                        # "Brain" prosi "Hands" o dane.
                        result = await session.call_tool(
                            "get_stock_price",
                            arguments={"company_name": clean_word}
                        )
                        
                        # Sprawdzamy wynik
                        text_result = result.content[0].text
                        
                        # Jeśli wynik nie zaczyna się od błędu/nie znaleziono, to bierzemy
                        if "Znaleziono" in text_result:
                            found_info = text_result
                            break 
                            
                    except Exception as e:
                        print(f"⚠️ Błąd przy pytaniu o {clean_word}: {e}")
                        continue
                
                return found_info

    except Exception as e:
        print(f"❌ Błąd ogólny połączenia z MCP: {e}")
        return None

@app.post("/ask")
async def ask_agent(query: UserQuery):
    user_text = query.prompt
    
    # --- KROK 1: Pobranie danych przez MCP ---
    mcp_result = await query_mcp_tool(user_text)
    
    if mcp_result:
        context = f"[SYSTEM INFO Z MCP]: {mcp_result}"
    else:
        context = "[SYSTEM INFO]: Nie znaleziono danych w bazie MCP dla tego zapytania."

    # --- KROK 2: Przygotowanie Promptu dla AI ---
    system_instruction = (
        "Jesteś asystentem giełdowym WIG20. "
        "Masz dostęp do narzędzia MCP, które dostarcza aktualne ceny. "
        "Odpowiadaj WYŁĄCZNIE na podstawie dostarczonego [SYSTEM INFO]. "
        "Jeśli informacji nie ma, powiedz to wprost."
    )

    full_prompt = f"{system_instruction}\n\nKONTEKST:\n{context}\n\nPYTANIE UŻYTKOWNIKA:\n{user_text}"

    # --- KROK 3: Wysłanie do Ollamy ---
    ollama_url = "http://ollama:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
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