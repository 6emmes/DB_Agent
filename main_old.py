from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
import json
# Importujemy klienta MCP zamiast bazy danych
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

app = FastAPI()

class UserQuery(BaseModel):
    prompt: str

# Adres serwera MCP (wewnątrz sieci Docker to nazwa usługi "mcp")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp:8001/sse")

async def get_mcp_data(resource_uri: str):
    """
    Fetches data from MCP resource (read-only data access)
    """
    print(f"🔌 [MCP] Connecting to read resource: {resource_uri}")
    
    try:
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Read resource returns raw string data
                result = await session.read_resource(resource_uri)
                return result
    
    except Exception as e:
        print(f"❌ [MCP] Error reading resource: {e}")
        return None

async def get_mcp_prompt(prompt_name: str, prompt_args: dict):
    """
    Fetches an analysis prompt from MCP (includes current data + analysis instructions)
    """
    print(f"🔌 [MCP] Fetching prompt: {prompt_name}")
    
    try:
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Get prompt with arguments
                prompt_text = await session.get_prompt(prompt_name, prompt_args)
                return prompt_text
    
    except Exception as e:
        print(f"❌ [MCP] Error fetching prompt: {e}")
        return None

async def call_mcp_tool(tool_name: str, tool_args: dict):
    """
    Calls an MCP tool (for actions with side effects)
    """
    print(f"🔌 [MCP] Calling tool: {tool_name}")
    
    try:
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                result = await session.call_tool(tool_name, tool_args)
                return result.content[0].text if result.content else None
    
    except Exception as e:
        print(f"❌ [MCP] Error calling tool: {e}")
        return None

async def decide_action_simple(user_query: str):
    """
    Simple keyword-based decision without LLM call (faster)
    """
    query_lower = user_query.lower()
    
    # Keywords for different actions
    if any(word in query_lower for word in ["porównaj", "compare", "lepszy", "który", "versus", "vs"]):
        # Compare multiple stocks
        symbols = extract_symbols(user_query)
        return "get_prompt_compare", symbols, ""
    
    elif any(word in query_lower for word in ["analiz", "analyze", "jak się", "jak wygląd", "powinien"]):
        # Analyze single stock
        symbols = extract_symbols(user_query)
        return "get_prompt_analyze", symbols, ""
    
    elif any(word in query_lower for word in ["alert", "powiadom", "alarm", "gdy", "kiedy", "spadnie", "wzrost"]):
        # Set alert
        symbols = extract_symbols(user_query)
        price = extract_price(user_query)
        return "call_tool_alert", symbols, price
    
    elif any(word in query_lower for word in ["rynek", "market", "wig20", "indeks", "pokaż wszystko"]):
        # Market overview
        return "get_prompt_overview", "", ""
    
    else:
        # Default: fetch data
        return "read_resource", "", ""

def extract_symbols(text: str) -> str:
    """Extract company symbols from text (simple heuristic)"""
    # Common WIG20 symbols
    symbols = ["PKO", "PZU", "PKNORLEN", "ORLEN", "ALIOR", "ALLEGRO", "SANTANDER", 
               "KGHM", "EUROCASH", "JSBANK", "MBANK", "PLAY", "ING", "POWERENERGY"]
    
    found = []
    for symbol in symbols:
        if symbol.lower() in text.lower():
            found.append(symbol)
    
    return ",".join(found) if found else ""

def extract_price(text: str) -> str:
    """Extract price from text"""
    import re
    # Look for numbers (price)
    prices = re.findall(r'\d+[\.,]\d+', text)
    return prices[0].replace(",", ".") if prices else ""

@app.post("/ask")
async def ask_agent(query: UserQuery):
    user_text = query.prompt
    print(f"\n📝 User query: {user_text}")
    
    # --- STEP 1: Decide action (fast, keyword-based) ---
    action_type, symbols, target_price = await decide_action_simple(user_text)
    print(f"📋 Decision: {action_type} (symbols: {symbols})")
    
    context = ""
    analysis_guidance = ""
    
    # --- STEP 2: Execute action based on LLM decision ---
    
    if action_type == "read_resource":
        # Fetch all stock prices
        data = await get_mcp_data("stock://wig20/all")
        if data:
            context = f"[STOCK DATA]:\n{data}"
        else:
            context = "[ERROR]: Could not fetch stock data"
    
    elif action_type == "get_prompt_analyze" and symbols:
        # Get analysis prompt for specific stock
        prompt_text = await get_mcp_prompt("analyze_stock", {"symbol": symbols})
        if prompt_text:
            analysis_guidance = prompt_text
            context = f"[ANALYSIS GUIDANCE]:\n{prompt_text}"
    
    elif action_type == "get_prompt_compare" and symbols:
        # Get comparison prompt
        prompt_text = await get_mcp_prompt("compare_stocks", {"symbols": symbols})
        if prompt_text:
            analysis_guidance = prompt_text
            context = f"[COMPARISON GUIDANCE]:\n{prompt_text}"
    
    elif action_type == "get_prompt_overview":
        # Get market overview prompt
        prompt_text = await get_mcp_prompt("market_overview", {})
        if prompt_text:
            analysis_guidance = prompt_text
            context = f"[MARKET OVERVIEW GUIDANCE]:\n{prompt_text}"
    
    elif action_type == "call_tool_alert" and symbols and target_price:
        # Set a price alert
        try:
            price = float(target_price)
            alert_type = "above" if "above" in user_text.lower() or "wzroście" in user_text.lower() else "below"
            result = await call_mcp_tool("set_price_alert", {
                "symbol": symbols,
                "target_price": price,
                "alert_type": alert_type
            })
            context = f"[ALERT]:\n{result}"
        except ValueError:
            context = "[ERROR]: Invalid price format"

    # --- STEP 3: Build final prompt for AI response ---
    system_instruction = (
        "Jesteś asystentem giełdowym WIG20. "
        "Masz dostęp do narzędzi MCP, które dostarczają aktualne ceny i analizy. "
        "Odpowiadaj na podstawie dostarczonego kontekstu. "
        "Jeśli brakuje danych, powiedz to wprost. "
        "WAŻNE: Dane to tylko ceny akcji - brak P/E, dywidend i innych fundamentów."
    )

    if analysis_guidance:
        # Use the guidance prompt as part of system instruction
        full_prompt = f"{system_instruction}\n\n{analysis_guidance}\n\nPYTANIE UŻYTKOWNIKA:\n{user_text}"
    else:
        # Regular response with data context
        full_prompt = f"{system_instruction}\n\nKONTEKST:\n{context}\n\nPYTANIE UŻYTKOWNIKA:\n{user_text}"

    # --- STEP 4: Send to Ollama for final response ---
    ollama_url = "http://ollama:11434/api/generate"
    payload = {
        "model": "qwen2:0.5b",
        "prompt": full_prompt,
        "stream": False
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()
        ai_reply = response.json().get("response", "")
    except Exception as e:
        ai_reply = f"Błąd komunikacji z modelem AI: {str(e)}"

    return {
        "response": ai_reply,
        "action_taken": action_type,
        "context_used": context[:500] + "..." if len(context) > 500 else context
    }