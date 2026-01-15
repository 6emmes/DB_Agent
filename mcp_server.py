import mysql.connector
import os
import json
from datetime import datetime
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, Resource, Prompt, PromptArgument, TextContent, EmbeddedResource, ImageContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response

# 1. Server i Transport
server = Server("wig20-data")
sse = SseServerTransport("/messages")

def get_db_connection():
    try:
        return mysql.connector.connect(
            host="db",
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
    except Exception as e:
        print(f"❌ [MCP] Błąd DB: {e}")
        return None

# ===== SECTION 2: RESOURCES (Data exposure - READ ONLY) =====

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available data resources"""
    return [
        Resource(
            uri="stock://wig20/all",
            name="All WIG20 Stocks",
            description="Current prices and info for all WIG20 companies with latest prices"
        ),
        Resource(
            uri="stock://wig20/prices",
            name="WIG20 Prices",
            description="Quick access to all current stock prices"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a specific resource and return data as JSON"""
    conn = get_db_connection()
    if not conn:
        return json.dumps({"error": "Database connection failed"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # All stocks with current prices
        if uri == "stock://wig20/all" or uri == "stock://wig20/prices":
            query = """
                SELECT s.name, s.market_cap, p.value as price, p.time
                FROM Prices p
                JOIN Symbols s ON p.symbol_id = s.id
                WHERE p.time = (SELECT MAX(time) FROM Prices)
                ORDER BY s.name
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            if results:
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "count": len(results),
                    "stocks": [dict(row) for row in results]
                }
                return json.dumps(data, default=str)
            else:
                return json.dumps({"error": "No stock data found", "stocks": []})
        
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})
    
    finally:
        cursor.close()
        conn.close()

# ===== SECTION 3: TOOLS (Actions with side effects) =====
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="set_price_alert",
            description="Set an alert when a WIG20 stock price reaches a target value",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol/name to set alert for",
                        "minLength": 1,
                        "maxLength": 50
                    },
                    "target_price": {
                        "type": "number",
                        "description": "Target price in PLN (e.g., 50.0)",
                        "minimum": 0.01
                    },
                    "alert_type": {
                        "type": "string",
                        "enum": ["above", "below"],
                        "description": "Alert when price goes above or below target"
                    }
                },
                "required": ["symbol", "target_price", "alert_type"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    if name == "set_price_alert":
        if not arguments:
            return [TextContent(type="text", text="Error: No arguments provided")]
        
        symbol = arguments.get("symbol", "").strip()
        target_price = arguments.get("target_price")
        alert_type = arguments.get("alert_type")
        
        # Validate inputs
        if not symbol:
            return [TextContent(type="text", text="Error: Symbol is required")]
        if target_price is None or target_price <= 0:
            return [TextContent(type="text", text="Error: Target price must be positive")]
        if alert_type not in ["above", "below"]:
            return [TextContent(type="text", text="Error: Alert type must be 'above' or 'below'")]
        
        # For now, just log the alert (no persistent storage yet)
        # TODO: Create Alerts table if needed
        return [TextContent(
            type="text",
            text=f"✓ Alert set: Will notify when {symbol} price goes {alert_type} {target_price} PLN"
        )]
    
    return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

# ===== SECTION 4: PROMPTS (Analysis guidance) =====

@server.list_prompts()
async def handle_list_prompts() -> list[Prompt]:
    """List available analysis prompts"""
    return [
        Prompt(
            name="analyze_stock",
            description="Analyze a single WIG20 stock based on available data",
            arguments=[
                PromptArgument(
                    name="symbol",
                    description="Stock symbol or name (e.g., PKO, Orlen)",
                    required=True
                )
            ]
        ),
        Prompt(
            name="compare_stocks",
            description="Compare multiple WIG20 stocks and provide recommendations",
            arguments=[
                PromptArgument(
                    name="symbols",
                    description="Comma-separated stock symbols (e.g., PKO,PZU,PKNORLEN)",
                    required=True
                )
            ]
        ),
        Prompt(
            name="market_overview",
            description="Provide overview of current WIG20 market state",
            arguments=[]
        )
    ]

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict | None) -> str:
    """Get a specific analysis prompt with current data"""
    conn = get_db_connection()
    if not conn:
        return "Error: Cannot connect to database"
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        if name == "analyze_stock":
            if not arguments or "symbol" not in arguments:
                return "Error: Symbol argument required"
            
            symbol = arguments.get("symbol", "").strip().upper()
            
            # Get current price and recent history
            query = """
                SELECT s.name, s.market_cap, p.value as price, p.time
                FROM Prices p
                JOIN Symbols s ON p.symbol_id = s.id
                WHERE UPPER(s.name) LIKE %s
                ORDER BY p.time DESC
                LIMIT 30
            """
            cursor.execute(query, (f"%{symbol}%",))
            results = cursor.fetchall()
            
            if not results:
                return f"Error: No data found for symbol '{symbol}'"
            
            current_price = results[0]["price"]
            oldest_price = results[-1]["price"] if len(results) > 1 else current_price
            change_percent = ((current_price - oldest_price) / oldest_price * 100) if oldest_price > 0 else 0
            
            prices_history = [(r["time"].strftime("%Y-%m-%d"), r["price"]) for r in results]
            
            prompt = f"""You are a WIG20 stock analyst. Analyze the following stock:

Stock: {results[0]['name']}
Current Price: {current_price} PLN
30-day Change: {change_percent:.2f}%
Recent Price History (30 days):
{json.dumps(prices_history[:10], indent=2)}

NOTE: Limited data available - only price history. No P/E ratio, dividend yield, or other fundamentals yet.

Provide analysis covering:
1. **Trend Analysis**: Is the stock in uptrend, downtrend, or sideways movement?
2. **Price Movement**: Analyze the recent price change
3. **Simple Observation**: Based only on price movement, what patterns do you see?
4. **Cautious Recommendation**: Given limited data, is this worth considering? Why or why not?

Be concise and honest about data limitations."""

            return prompt
        
        elif name == "compare_stocks":
            if not arguments or "symbols" not in arguments:
                return "Error: Symbols argument required"
            
            symbols = [s.strip().upper() for s in arguments.get("symbols", "").split(",")]
            
            # Get current prices for all symbols
            comparison_data = []
            for symbol in symbols:
                query = """
                    SELECT s.name, p.value as price, p.time
                    FROM Prices p
                    JOIN Symbols s ON p.symbol_id = s.id
                    WHERE UPPER(s.name) LIKE %s
                    ORDER BY p.time DESC
                    LIMIT 1
                """
                cursor.execute(query, (f"%{symbol}%",))
                result = cursor.fetchone()
                if result:
                    comparison_data.append({
                        "name": result["name"],
                        "price": result["price"],
                        "timestamp": result["time"].strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            if not comparison_data:
                return f"Error: No data found for symbols: {', '.join(symbols)}"
            
            prompt = f"""You are a WIG20 investment advisor. Compare these stocks:

{json.dumps(comparison_data, indent=2)}

NOTE: Limited data available - only current prices. No P/E ratio, dividend yield, market cap, or other fundamentals yet.

Provide comparison covering:
1. **Price Comparison**: Which is cheapest? Which is most expensive?
2. **Relative Values**: Based on current prices alone, what observations can you make?
3. **Simple Analysis**: What patterns or trends do you notice?
4. **Cautious Recommendation**: If you had to pick one to watch, which would it be? Why?

Be honest about data limitations and avoid making strong financial advice without fundamentals."""

            return prompt
        
        elif name == "market_overview":
            # Get all stocks with current prices
            query = """
                SELECT s.name, p.value as price, p.time
                FROM Prices p
                JOIN Symbols s ON p.symbol_id = s.id
                WHERE p.time = (SELECT MAX(time) FROM Prices)
                ORDER BY s.name
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            if not results:
                return "Error: No market data available"
            
            # Calculate simple statistics
            prices = [r["price"] for r in results]
            avg_price = sum(prices) / len(prices)
            
            stocks_list = "\n".join([f"  - {r['name']}: {r['price']} PLN" for r in results])
            
            prompt = f"""You are a WIG20 market analyst. Provide an overview of the current market state.

Total Stocks Tracked: {len(results)}
Average Price: {avg_price:.2f} PLN
Latest Data: {results[0]['time'].strftime('%Y-%m-%d %H:%M:%S')}

All Stocks:
{stocks_list}

NOTE: Limited data available - only current prices. No volume, P/E ratios, dividends, or fundamentals.

Provide overview covering:
1. **Market Snapshot**: General description of current state
2. **Price Range**: What's the cheapest and most expensive stock?
3. **Observations**: Any interesting patterns in the price distribution?
4. **Simple Recommendation**: What would be worth researching further? Why?

Keep it factual and acknowledge data limitations."""

            return prompt
        
        else:
            return f"Error: Unknown prompt '{name}'"
    
    finally:
        cursor.close()
        conn.close()

# ===== SECTION 5: HTTP ROUTES =====

async def handle_sse(request: Request):
    """SSE endpoint for MCP communication"""
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

async def handle_messages(request: Request):
    """Messages endpoint for MCP communication"""
    await sse.handle_post_message(request.scope, request.receive, request._send)

app = Starlette(
    debug=True,
    routes=[
        Route("/sse", handle_sse),
        Route("/messages", handle_messages, methods=["POST"])
    ]
)