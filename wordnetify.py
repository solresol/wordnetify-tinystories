#!/usr/bin/env python3

#!/usr/bin/env python3

import argparse
import nltk
import sqlite3
from nltk.corpus import wordnet
import tqdm

# Ensure necessary NLTK resources are downloaded
nltk.download('punkt')
nltk.download('wordnet')

def read_file_in_chunks(file_path):
    """Read a file and yield chunks of text separated by a specific delimiter."""
    chunk = []
    with open(file_path, 'r') as file:
        for line in file:
            if line.strip() == '<|endoftext|>':
                yield ''.join(chunk)
                chunk = []
            else:
                chunk.append(line)
        if chunk:
            yield ''.join(chunk)

def create_schema(conn):
    """Create the database schema."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        story_number INTEGER NOT NULL,
        UNIQUE(filename, story_number)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        sentence_number INTEGER NOT NULL,
        sentence TEXT NOT NULL,
        FOREIGN KEY(story_id) REFERENCES stories(id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence_id INTEGER NOT NULL,
        word_number INTEGER NOT NULL,
        word TEXT NOT NULL,
        synset_count INTEGER NOT NULL,
        resolved_synset TEXT,
        FOREIGN KEY(sentence_id) REFERENCES sentences(id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS word_synsets (
        word_id INTEGER NOT NULL,
        synset_id TEXT NOT NULL,
        PRIMARY KEY(word_id, synset_id),
        FOREIGN KEY(word_id) REFERENCES words(id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS synsets (
        id TEXT PRIMARY KEY,
        description TEXT,
        examples TEXT
    )""")
    
    conn.commit()

def insert_story(conn, filename, story_number):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO stories (filename, story_number) VALUES (?, ?)
    """, (filename, story_number))
    conn.commit()
    return cursor.lastrowid

def insert_sentence(conn, story_id, sentence_number, sentence):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sentences (story_id, sentence_number, sentence) VALUES (?, ?, ?)
    """, (story_id, sentence_number, sentence))
    conn.commit()
    return cursor.lastrowid

def insert_word(conn, sentence_id, word_number, word, synset_count, resolved_synset):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO words (sentence_id, word_number, word, synset_count, resolved_synset) VALUES (?, ?, ?, ?, ?)
    """, (sentence_id, word_number, word, synset_count, resolved_synset))
    return cursor.lastrowid

def insert_word_synset(conn, word_id, synset_id):
    cursor = conn.cursor()
    # beats me how it's possible but I got multiple hits on old.s.04
    cursor.execute("""
    INSERT OR IGNORE INTO word_synsets (word_id, synset_id) VALUES (?, ?)
    """, (word_id, synset_id))

def insert_synset(conn, synset):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO synsets (id, description, examples) VALUES (?, ?, ?)
    """, (synset.name(), synset.definition(), "; ".join(synset.examples())))

def main():
    parser = argparse.ArgumentParser(description="Read a file in chunks separated by a delimiter and store the data in an SQLite database.")
    parser.add_argument("--file", type=str, help="The path to the file to be read.")
    parser.add_argument("--database", type=str, help="The SQLite database file.")

    args = parser.parse_args()

    conn = sqlite3.connect(args.database)
    create_schema(conn)

    story_number = 0
    for chunk in tqdm.tqdm(read_file_in_chunks(args.file)):
        story_id = insert_story(conn, args.file, story_number)
        story_number += 1
        sentence_number = 0
        for sentence in nltk.sent_tokenize(chunk):
            sentence_id = insert_sentence(conn, story_id, sentence_number, sentence)
            sentence_number += 1
            word_number = 0
            for word in nltk.word_tokenize(sentence):
                synsets = nltk.corpus.wordnet.synsets(word)
                synset_count = len(synsets)
                resolved_synset = synsets[0].name() if synset_count == 1 else None
                word_id = insert_word(conn, sentence_id, word_number, word, synset_count, resolved_synset)
                word_number += 1

                if synset_count > 1:
                    for synset in synsets:
                        insert_word_synset(conn, word_id, synset.name())
                        insert_synset(conn, synset)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
