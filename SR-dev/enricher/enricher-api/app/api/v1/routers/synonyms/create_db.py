import sqlite3
import os

CACHE_DB = "synonyms_cache.db"

def init_cache():
    if os.path.exists(CACHE_DB):
        print(f"{CACHE_DB} already exists, wiping and re-creating.")
        os.remove(CACHE_DB)

    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()

    # synonyms cache table
    c.execute("""
        CREATE TABLE synonyms_cache (
            term TEXT NOT NULL,
            source TEXT NOT NULL,
            synonyms TEXT NOT NULL,
            timestamp REAL NOT NULL,
            PRIMARY KEY (term, source)
        )
    """)

    # cache stats table
    c.execute("""
        CREATE TABLE cache_stats (
            source TEXT PRIMARY KEY,
            hits INTEGER DEFAULT 0,
            misses INTEGER DEFAULT 0
        )
    """)

    # insert default sources
    for src in ("nltk", "altervista", "datamuse"):
        c.execute("INSERT INTO cache_stats (source, hits, misses) VALUES (?, 0, 0)", (src,))

    conn.commit()
    conn.close()
    print(f"Database {CACHE_DB} initialized with synonyms_cache and cache_stats.")

if __name__ == "__main__":
    init_cache()
