import mysql.connector
import os
import time

def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            connection = mysql.connector.connect(
                host="db",
                user=os.getenv("MYSQL_USER"),
                password=os.getenv("MYSQL_PASSWORD"),
                database=os.getenv("MYSQL_DATABASE")
            )
            return connection
        except mysql.connector.Error as err:
            print(f"Baza nie gotowa... ({err}). Czekam 5s.")
            retries -= 1
            time.sleep(5)
    return None


def get_stock_price(user_query_fragment):
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    
    # SZUKANIE DYNAMICZNE (LIKE)
    # Szukamy w tabeli Symbols firmy, która ma w nazwie to, co wpisał użytkownik.
    # Np. wpiszesz "orlen", a baza znajdzie "PKNORLEN".
    # Wpiszesz "pko", a baza znajdzie "PKOBP".
    query = """
        SELECT s.name, p.value as price 
        FROM Prices p
        JOIN Symbols s ON p.symbol_id = s.id
        WHERE s.name LIKE %s
        ORDER BY p.time DESC
        LIMIT 1
    """
    
    # Dodajemy procenty do zapytania SQL dla mechanizmu LIKE
    search_term = f"%{user_query_fragment}%"
    
    cursor.execute(query, (search_term,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result
