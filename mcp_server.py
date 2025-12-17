import mysql.connector
import os
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, EmbeddedResource, ImageContent
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

# 2. Rejestracja Narzędzi
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_stock_price",
            description="Pobiera aktualną cenę akcji spółki z indeksu WIG20.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {"type": "string", "description": "Nazwa spółki (np. Orlen)"}
                },
                "required": ["company_name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent | ImageContent | EmbeddedResource]:
    if name != "get_stock_price":
        raise ValueError(f"Unknown tool: {name}")

    if not arguments or "company_name" not in arguments:
        return [TextContent(type="text", text="Błąd: Nie podano nazwy spółki.")]

    company_name = arguments["company_name"]
    
    conn = get_db_connection()
    if not conn:
        return [TextContent(type="text", text="Błąd: Brak połączenia z bazą.")]

    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT s.name, p.value as price 
        FROM Prices p
        JOIN Symbols s ON p.symbol_id = s.id
        WHERE s.name LIKE %s
        ORDER BY p.time DESC
        LIMIT 1
    """
    param = f"%{company_name}%"
    cursor.execute(query, (param,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        return [TextContent(type="text", text=f"Znaleziono: {result['name']} kosztuje {result['price']} PLN.")]
    else:
        return [TextContent(type="text", text=f"Nie znaleziono spółki '{company_name}'.")]

# 3. Obsługa WWW (Poprawiona linijka!)

async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        # TU BYŁ BŁĄD. Zmieniono 'sse.' na 'server.'
        await server.run(streams[0], streams[1], server.create_initialization_options())

async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"])
    ]
)