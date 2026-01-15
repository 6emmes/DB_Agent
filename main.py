from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
import mysql.connector

app = FastAPI()

class UserQuery(BaseModel):
    prompt: str

def get_db_connection():
    """Connect to MySQL database"""
    return mysql.connector.connect(
        host="db",
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )

def get_stock_price(symbol: str) -> dict:
    """Get current stock price from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT s.name, p.value as price, p.time
            FROM Prices p
            JOIN Symbols s ON p.symbol_id = s.id
            WHERE UPPER(s.name) LIKE %s
            ORDER BY p.time DESC
            LIMIT 1
        """
        cursor.execute(query, (f"%{symbol.upper()}%",))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result if result else None
    except Exception as e:
        print(f"❌ [DB] Error: {e}")
        return None

def get_all_prices() -> list:
    """Get all stock prices from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT s.name, p.value as price, p.time
            FROM Prices p
            JOIN Symbols s ON p.symbol_id = s.id
            WHERE p.time = (SELECT MAX(time) FROM Prices)
            ORDER BY s.name
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return results if results else []
    except Exception as e:
        print(f"❌ [DB] Error: {e}")
        return []

def extract_symbols(text: str) -> list:
    """Extract company symbols from text"""
    symbols = ["PKO", "PZU", "PKNORLEN", "ORLEN", "ALIOR", "ALLEGRO", "SANTANDER", 
               "KGHM", "EUROCASH", "JSBANK", "MBANK", "PLAY", "ING", "POWERENERGY"]
    
    found = []
    for symbol in symbols:
        if symbol.lower() in text.lower():
            found.append(symbol)
    
    return found

@app.post("/ask")
async def ask_agent(query: UserQuery):
    user_text = query.prompt
    print(f"\n📝 User query: {user_text}")
    
    query_lower = user_text.lower()
    
    # Decide what data to fetch
    if any(word in query_lower for word in ["porównaj", "compare", "lepszy", "który"]):
        # Compare stocks
        symbols = extract_symbols(user_text)
        if symbols:
            data_list = []
            for symbol in symbols:
                price_data = get_stock_price(symbol)
                if price_data:
                    data_list.append(f"{price_data['name']}: {price_data['price']} PLN")
            context = "Porównanie:\n" + "\n".join(data_list) if data_list else "Brak danych"
        else:
            context = "Nie znaleziono symboli do porównania"
    
    elif any(word in query_lower for word in ["analiz", "analyze", "jak się", "jak wygląd"]):
        # Analyze single stock
        symbols = extract_symbols(user_text)
        if symbols:
            price_data = get_stock_price(symbols[0])
            if price_data:
                context = f"{price_data['name']}: {price_data['price']} PLN (aktualizacja: {price_data['time']})"
            else:
                context = f"Brak danych dla: {symbols[0]}"
        else:
            context = "Nie znaleziono symbolu"
    
    elif any(word in query_lower for word in ["rynek", "market", "wig20", "indeks", "wszystkie", "wszystko"]):
        # Market overview
        prices = get_all_prices()
        if prices:
            price_list = "\n".join([f"  - {p['name']}: {p['price']} PLN" for p in prices])
            context = f"Ceny WIG20:\n{price_list}"
        else:
            context = "Brak danych giełdowych"
    
    else:
        # Default: get prices
        symbols = extract_symbols(user_text)
        if symbols:
            price_data = get_stock_price(symbols[0])
            if price_data:
                context = f"{price_data['name']}: {price_data['price']} PLN"
            else:
                context = f"Brak danych dla: {symbols[0]}"
        else:
            # Get all prices
            prices = get_all_prices()
            if prices:
                price_list = "\n".join([f"  - {p['name']}: {p['price']} PLN" for p in prices[:5]])
                context = f"Ceny WIG20 (top 5):\n{price_list}"
            else:
                context = "Brak danych giełdowych w bazie"

    # Build prompt for Ollama - VERY EXPLICIT
    # Use simple, clear instructions
    if "Brak danych" in context:
        full_prompt = f"""You are a stock assistant. You only have this data:
{context}

User question: {user_text}

Answer: The requested stock data is not available."""
    else:
        # Data is available, use it directly
        full_prompt = f"""You are a stock assistant. Answer based ONLY on this data:
{context}

User question: {user_text}

Answer: Simply state the stock name and price in PLN. Do not add extra information. Be short and direct."""

    # Send to Ollama - using larger 3B model for better reliability
    ollama_url = "http://ollama:11434/api/generate"
    payload = {
        "model": "qwen2.5:3b",
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=120)
        response.raise_for_status()
        ai_reply = response.json().get("response", "")
    except Exception as e:
        ai_reply = f"Błąd Ollama: {str(e)}"

    return {
        "response": ai_reply,
        "context_used": context
    }
