import mysql.connector
from datetime import datetime
import os
import time

def insert(prices, names, total_value):
    # Czekamy chwilę na start bazy (tylko dla pewności)
    timestamp = datetime.now()

    print("Łączenie z bazą danych...")
    
    # POPRAWKA 1: Używamy Twoich zmiennych z .env i hosta 'db'
    conn = mysql.connector.connect(
        host="db",
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE")
    )
    cursor = conn.cursor()

    # Tabela spółek
    print("Tworzenie tabeli Symbols...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Symbols (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            market_cap FLOAT NOT NULL
        )
    """)

    # Tabela cen (relacyjna!)
    print("Tworzenie tabeli Prices...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Prices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            symbol_id INT NOT NULL,
            value FLOAT NOT NULL,
            time DATETIME NOT NULL,
            FOREIGN KEY (symbol_id) REFERENCES Symbols(id),
            UNIQUE(symbol_id, time)
        )
    """)


    # 1. Najpierw Spółki
    for n, cap in zip(names, total_value):
        cursor.execute("""
            INSERT INTO Symbols (name, market_cap)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE market_cap = VALUES(market_cap)
        """, (n, cap))

    # 2. Potem ceny (musimy znaleźć ID spółki)
    for p, n in zip(prices, names):
        cursor.execute("SELECT id FROM Symbols WHERE name=%s", (n,))
        result = cursor.fetchone()
        if result:
            symbol_id = result[0]
            # Używamy INSERT IGNORE, żeby nie wywalało błędu jak uruchomisz skrypt 2 razy
            cursor.execute("""
                INSERT IGNORE INTO Prices (symbol_id, value, time)
                VALUES (%s, %s, %s)
            """, (symbol_id, p, timestamp))

    conn.commit()
    print("SUKCES! Baza strukturalna została utworzona.")
    cursor.close()
    conn.close()
