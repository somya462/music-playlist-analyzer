

import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kan@3182",  # replace with your real password
        database="spotify"
    )

    if conn.is_connected():
        print("✅ Connection successful!")
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        print("Tables in 'spotify' database:")
        for (table,) in cursor.fetchall():
            print(" -", table)

except mysql.connector.Error as e:
    print("❌ Database connection failed:", e)

finally:
    if 'conn' in locals() and conn.is_connected():
        conn.close()
