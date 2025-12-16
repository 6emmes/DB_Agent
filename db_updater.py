import mysql.connector
from datetime import datetime

def insert(prices, names, total_value):
    #get timestamp
    timestamp = datetime.now()

    # Connect to MySQL as myuser
    conn = mysql.connector.connect(
        host="localhost",       # or your server IP
        user="agent",
        password="haslo",
        database="chmura_db"
    )

    cursor = conn.cursor()

    # Table for symbols (with market cap)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Symbols (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            market_cap FLOAT NOT NULL
        )
    """)

    # Table for prices (normalized values linked to symbol)
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

    # Insert or update symbols with market cap
    for n, cap in zip(names, total_value):
        cursor.execute("""
            INSERT INTO Symbols (name, market_cap)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE market_cap = VALUES(market_cap)
        """, (n, cap))

    # Insert prices linked to symbols
    for p, n in zip(prices, names):
        cursor.execute("SELECT id FROM Symbols WHERE name=%s", (n,))
        symbol_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO Prices (symbol_id, value, time)
            VALUES (%s, %s, %s)
        """, (symbol_id, p, timestamp))

    # Commit changes
    conn.commit()

    print("Key-value pair inserted/updated successfully!")

    # Close connection
    cursor.close()
    conn.close()