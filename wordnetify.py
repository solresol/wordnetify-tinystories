#!/usr/bin/env python3

import argparse
import nltk
import sqlite3
from nltk.corpus import wordnet

# Ensure necessary NLTK resources are downloaded
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('punkt_tab')


def read_file_in_chunks(file_path, starting_position=None, max_chunks=None):
    """Read a file and yield chunks of text separated by a specific delimiter."""
    chunk = []
    chunks_delivered = 0
    if max_chunks == 0:
        return
    with open(file_path, 'r') as file:
        if starting_position is not None:
            file.seek(starting_position)
        while True:
            line = file.readline()
            if not line:
                break
            if line.strip() == '<|endoftext|>':
                yield (file.tell(), ''.join(chunk))
                chunks_delivered += 1
                chunk = []
                if max_chunks is not None and max_chunks <= chunks_delivered:
                    return
            else:
                chunk.append(line)
        if chunk:
            yield (file.tell(), ''.join(chunk))


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the database schema."""
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS filepositions (
       filename text primary key,
       position integer not null
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        story_number INTEGER NOT NULL,
        UNIQUE(filename, story_number),
        FOREIGN KEY(filename) references filepositions (filename)
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sentences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        sentence_number INTEGER NOT NULL,
        sentence TEXT NOT NULL,
        FOREIGN KEY(story_id) REFERENCES stories(id)
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sentence_id INTEGER NOT NULL,
        word_number INTEGER NOT NULL,
        word TEXT NOT NULL,
        synset_count INTEGER NOT NULL,
        resolved_synset TEXT CHECK (resolved_synset is null or resolved_synset like '%._.__' or resolved_synset like '(%' AND resolved_synset like '%.other'),
        resolving_model TEXT,
        resolved_timestamp datetime,
        resolution_compute_time FLOAT,
        FOREIGN KEY(sentence_id) REFERENCES sentences(id)
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS word_synsets (
        word_id INTEGER NOT NULL,
        synset_id TEXT NOT NULL,
        PRIMARY KEY(word_id, synset_id),
        FOREIGN KEY(word_id) REFERENCES words(id)
    );""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS synsets (
        id TEXT PRIMARY KEY,
        description TEXT,
        examples TEXT
    );""")

    cursor.execute("""
    CREATE INDEX if not exists idx_words_sentence_id ON words(sentence_id);
    """)

    cursor.execute("""
    CREATE INDEX if not exists idx_sentences_story_id_number ON sentences(story_id, sentence_number);
    """)

    cursor.execute("""
    CREATE INDEX if not exists idx_words_sentence_word_number ON words(sentence_id, word_number);
    """)
    
    
    conn.commit()

def insert_story(conn, filename, story_number):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO stories (filename, story_number) VALUES (?, ?)
    """, (filename, story_number))
    return cursor.lastrowid

def insert_sentence(conn, story_id, sentence_number, sentence):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sentences (story_id, sentence_number, sentence) VALUES (?, ?, ?)
    """, (story_id, sentence_number, sentence))
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
    parser.add_argument("--progress", action="store_true", help="Show a progress bar")
    parser.add_argument("--restart", action="store_true",
                        help="If we have read this file before, delete everything from the last run")
    parser.add_argument("--stop-after", type=int, help="Number of stories to stop after")

    args = parser.parse_args()

    conn = sqlite3.connect(args.database)
    create_schema(conn)

    cursor = conn.cursor()
    if args.restart:
        cursor.execute("delete from word_synsets where word_id in (select words.id from words join sentences on (sentence_id = sentences.id) join stories on (story_id = stories.id) where filename = ?)", [args.file])
        cursor.execute("delete from words where sentence_id in (select sentence_id from sentences join stories on (story_id = stories.id) where filename = ?)", [args.file])
        cursor.execute("delete from sentences where story_id in (select story_id from stories where filename = ?)", [args.file])
        cursor.execute("delete from stories where filename = ?", [args.file])
        cursor.execute("delete from filepositions where filename = ?", [args.file])
        conn.commit()

    cursor.execute("select position from filepositions where filename = ?", [args.file])
    row = cursor.fetchone()
    if row is None:
        start_position = 0
        cursor.execute("insert into filepositions (filename, position) values (?,?)", [args.file, 0])
    else:
        start_position = row[0]

    cursor.execute("select max(id) from stories where filename = ?", [args.file])
    row = cursor.fetchone()
    if row is None or row[0] is None:
        story_number = 0
    else:
        story_number = row[0] + 1
    iterator = read_file_in_chunks(args.file, start_position, max_chunks=args.stop_after)
    if args.progress:
        import tqdm
        iterator = tqdm.tqdm(iterator)
    for (pos, story) in iterator:
        # Every story is a transaction
        story_id = insert_story(conn, args.file, story_number)
        story_number += 1
        sentence_number = 0
        for sentence in nltk.sent_tokenize(story):
            sentence_id = insert_sentence(conn, story_id, sentence_number, sentence)
            sentence_number += 1
            word_number = 0
            for word in nltk.word_tokenize(sentence):
                synsets = nltk.corpus.wordnet.synsets(word)
                synset_count = len(synsets)
                # This was a bad idea. If a word has one synset, but happens to also be
                # a preposition or a pronoun or something, then this gets the wrong answer.
                # Also, I should have lemmatized it first.
                # I think in the future we can get rid of the resolved_synset and synset_count
                # TBH, now that I know that the fastest way to resolve synsets is to use chatgpt + batch
                # it probably makes more sense to fire off a query for every word to get the lemmatized
                # form and then come back to get the synsets.
                resolved_synset = synsets[0].name() if synset_count == 1 else None
                word_id = insert_word(conn, sentence_id, word_number, word, synset_count, resolved_synset)
                word_number += 1

                if synset_count > 1:
                    for synset in synsets:
                        insert_word_synset(conn, word_id, synset.name())
                        insert_synset(conn, synset)
        cursor.execute("update filepositions set position = ? where filename = ?", [pos, args.file])
        conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
