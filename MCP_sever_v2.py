from flask import Flask, request, jsonify
import requests
import json
import mysql.connector

app = Flask(__name__)

# --- KONFIGURACJA ---
OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"  # Upewnij się, że masz ten model (lub qwen3:8b jeśli taki masz)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'agent',
    'password': 'Haslo123!', 
    'database': 'chmura_db'
}

# --- SCHEMAT I PROMPT (Bez zmian) ---
DB_SCHEMA = """
Table: WIG20
Columns:
- name (VARCHAR): The ticker symbol.
- value (FLOAT): The current stock price.
- time (DATETIME): Timestamp.
"""

SYSTEM_PROMPT = {
    "role": "system",
    "content": f"""You are a MySQL 8.0 expert. 
    Schema:
    {DB_SCHEMA}

    User asks -> You generate SQL query -> Call 'run_sql_query'.
    Rules:
    1. Output ONLY the tool call.
    2. Use LIMIT 1 for 'top/best'.
    3. Order by time DESC usually.

    Tools:
    [
      {{
        "name": "run_sql_query",
        "description": "Executes SQL.",
        "parameters": {{
          "type": "object",
          "properties": {{
            "query": {{ "type": "string" }}
          }},
          "required": ["query"]
        }}
      }}
    ]
    """
}

# --- FUNKCJA BAZODANOWA (Bez zmian) ---
def run_sql_query(query: str) -> str:
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
    if any(word in query.upper() for word in forbidden):
        return "Error: Read-only access."

    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"Wykonuję SQL: {query}") 
        cursor.execute(query)
        
        rows = cursor.fetchall()
        if not rows:
            return "Brak wyników w bazie."
        
        # Zwracamy czyste dane w formie stringa
        return str(rows)

    except mysql.connector.Error as err:
        return f"SQL Error: {err}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- NOWA, NAPRAWIONA WERSJA ENDPOINTU CHAT ---
@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    if not user_input:
        return jsonify({"error": "Missing message"}), 400

    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": user_input}
    ]

    try:
        # 1. Pytamy Ollamę
        response = requests.post(OLLAMA_API_URL, json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0} # Zmniejszamy kreatywność, żeby JSON był stabilny
        })
        response.raise_for_status()
        
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        # --- PLAN B: Ręczne parsowanie JSON-a z tekstu ---
        # Jeśli Ollama zwróciła JSON w tekście (content), a nie w tool_calls
        if not tool_calls and "run_sql_query" in content:
            try:
                # Czasami model otacza JSON znakami ```json ... ```, musimy to wyczyścić
                clean_content = content.replace("```json", "").replace("```", "").strip()
                
                # Próbujemy zamienić tekst na obiekt Python
                tool_data = json.loads(clean_content)
                
                # Jeśli się udało, tworzymy sztuczny obiekt tool_call
                if "name" in tool_data and "parameters" in tool_data:
                    tool_calls = [{
                        "name": tool_data["name"],
                        "parameters": tool_data["parameters"]
                    }]
                    print("ZNALEZIONO JSON W TEKŚCIE! Naprawiam strukturę...")
            except json.JSONDecodeError:
                print("Nie udało się sparsować JSON-a z tekstu.")

        # --- KONIEC PLANU B ---

        # Jeśli nadal nie ma narzędzia, zwracamy tekst
        if not tool_calls:
            return jsonify({"response": content})

        # 2. Wykonanie narzędzia
        for call in tool_calls:
            # Obsługa różnych formatów (czasem jest 'function', czasem bezpośrednio)
            func_name = call.get("function", {}).get("name") or call.get("name")
            args = call.get("function", {}).get("arguments") or call.get("parameters")
            
            if func_name == "run_sql_query":
                # Wyciągamy zapytanie. Czasami args to słownik, a czasem string JSON
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        pass
                
                sql_query = args.get("query", "")
                
                # WYKONANIE ZAPYTANIA
                db_result = run_sql_query(sql_query)
                
                # Zwracamy wynik bezpośrednio do klienta
                return jsonify({"response": f"Wynik SQL: {db_result}"})

        return jsonify({"response": "Error: Tool found but parse failed."})

    except Exception as e:
        print("Błąd:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)