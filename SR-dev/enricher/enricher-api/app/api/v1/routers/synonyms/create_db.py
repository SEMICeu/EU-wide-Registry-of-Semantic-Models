import sqlite3
import os
from datetime import datetime

CACHE_DB = "synonyms_cache.db"

def init_cache():
    if os.path.exists(CACHE_DB):
        print(f"{CACHE_DB} already exists.")
    else:
        print(f"Creating {CACHE_DB}...")

    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS synonyms_cache (
            term TEXT NOT NULL,
            source TEXT NOT NULL,
            synonyms TEXT NOT NULL,
            timestamp REAL NOT NULL,
            PRIMARY KEY (term, source)
        )
    """)
    conn.commit()
    conn.close()
    print(f"Database {CACHE_DB} initialized.")

if __name__ == "__main__":
    init_cache()