import sqlite3


def initialize_database(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute("CREATE TABLE IF NOT EXISTS sentences (id INTEGER PRIMARY KEY AUTOINCREMENT, sentence TEXT NOT NULL)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence_id INTEGER NOT NULL,
            word_number INTEGER NOT NULL,
            word TEXT NOT NULL,
            resolved_synset TEXT,
            synset_count INTEGER DEFAULT 0,
            FOREIGN KEY(sentence_id) REFERENCES sentences(id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentence_id ON words(sentence_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolved_synset ON words(resolved_synset)")
    
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    initialize_database('sample.sqlite')
