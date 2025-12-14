import mysql.connector
from datetime import datetime

def insert(prices, names):
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

    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS WIG20 (
            name VARCHAR(255) UNIQUE NOT NULL,
            value FLOAT NOT NULL,
            time DATETIME NOT NULL,
            PRIMARY KEY (name, time)
        )
    """)
    for p, n in zip(prices, names):
        cursor.execute("""
            INSERT INTO WIG20 (name, value, time)
            VALUES (%s, %s, %s)
        """, (n, p, timestamp))

    # Commit changes
    conn.commit()

    print("Key-value pair inserted/updated successfully!")

    # Close connection
    cursor.close()
    conn.close()