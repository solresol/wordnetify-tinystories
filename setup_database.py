import os
import sqlite3


def initialize_database():
    database_path = 'sample.sqlite'
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence_id INTEGER,
        word_number INTEGER,
        word TEXT,
        resolved_synset TEXT,
        resolving_model TEXT,
        resolved_timestamp DATETIME,
        resolution_compute_time REAL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sentences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence TEXT
    )
    ''')

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    initialize_database()
