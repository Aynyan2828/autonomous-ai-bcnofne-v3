import sqlite3
import os

db_path = "c:\\Users\\PC USER\\.gemini\\antigravity\\scratch\\autonomous_AI_BCNOFNe_system_v3\\data\\shipos.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_states")
    rows = cursor.fetchall()
    print("--- System States ---")
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    conn.close()
