#!/usr/bin/env python3

import argparse
import sqlite3
import sys
from collections import namedtuple
import wordpaths

def get_db_connection(database):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_sentences(conn):
    cursor = conn.cursor()    
    cursor.execute("SELECT id FROM sentences ORDER BY story_id, sentence_number")
    return [x[0] for x in cursor]    

def get_sentence_ids_of_story(conn, story_id):
    cursor = conn.cursor()    
    cursor.execute("SELECT id FROM sentences WHERE story_id = ? ORDER BY sentence_number", (story_id,))
    return [x[0] for x in cursor]

def get_sentence_id(conn, story_id=None, sentence_id=None, sentence_number=None):
    cursor = conn.cursor()

    if story_id and not sentence_id and not sentence_number:
        raise ValueError("Cannot specify story_id without sentence_id and without sentence_number")
    if sentence_number and not story_id and not sentence_id:
        raise ValueError("Cannot specify a sentence number without also specifying a story or a sentence ID")

    params = []
    clauses = []
    if story_id:
        clauses.append("story_id = ?")
        params.append(story_id)
    if sentence_number:
        clauses.append("sentence_number = ?")
        params.append(sentence_number)
    if sentence_id:
        clauses.append("sentences.id = ?")
        params.append(sentence_id)

    query = "SELECT id FROM sentences WHERE " + (" AND ".join(clauses))
    cursor.execute(query, params)
    row = cursor.fetchone()
    return row[0] if row is not None else None

WordData = namedtuple('WordData', ['word_id', 'word', 'synset', 'path'])

def get_path(conn, word_id, word, synset):
    cursor = conn.cursor()
    hashed_word = wordpaths.hash_thing(word)
    if synset is None:
        return WordData(word_id=word_id, word=word, synset=None, path=None)
    fields = synset.split('.')
    if len(fields) == 3:
        cursor.execute("SELECT path FROM synset_paths WHERE synset_name = ?", (synset,))
        row = cursor.fetchone()
        if row is None:
            sys.exit(f"Asked to get the path of non-existent (but plausible) synset: {synset} for word {word} [word_id={word_id}]")
        return WordData(word_id=word_id, word=word, synset=synset, path=row[0])
    # So it's a pseudo synset
    if wordpaths.is_enumerated_pseudo_synset(synset):
        # Look it up
        cursor.execute("SELECT path FROM synset_paths WHERE synset_name = ?", (word.lower(),))
        row = cursor.fetchone()
        if row is None:
            # a new thing that we don't recognise, from a closed set
            return WordData(word_id=word_id, word=word, synset=synset, path=None)
        return WordData(word_id=word_id, word=word, synset=synset, path=row[0])
    #print(word_id, synset)
    prefix = wordpaths.hashed_pseudo_synset_prefix[synset]
    return WordData(word_id=word_id, word=word, synset=synset, path=prefix + hashed_word)


def display_sentence(conn, sentence_id):
    cursor = conn.cursor()
    cursor.execute("select sentence from sentences where id = ?", [sentence_id])
    #print(cursor.fetchone()[0])

WordSeq = namedtuple('WordSet', ['words', 'has_incomplete'])
    
def get_words(conn, sentence_id):
    cursor = conn.cursor()
    cursor.execute("SELECT id, word, resolved_synset FROM words WHERE sentence_id = ? ORDER BY word_number", (sentence_id,))
    answer = []
    incomplete = False
    for w_id, w, resolved_synset in cursor:
        word = get_path(conn, w_id,  w, resolved_synset)
        if not word.path:
            incomplete = True
        answer.append(word)
    return WordSeq(words=answer, has_incomplete=incomplete)

def display_word_by_word(conn, sentence_id, show_paths=False, show_incomplete=False, only_incomplete=False):
    words = get_words(conn, sentence_id)
    if words.has_incomplete and not show_incomplete:
        return
    if only_incomplete and not words.has_incomplete:
        return
    for (i,w) in enumerate(words.words):
        if only_incomplete:
            if w.path is None:
                print(f"{w.word} [word id = {w.word_id}, position={i+1} in sentence={sentence_id}] = {w.synset}")
            continue
        print("--->", end=' ')
        if show_paths:
            if w.path:
                print(f"{w.word} [{w.path}]", end=' ')
            else:
                print(f"{w.word} [x]", end=' ')
            continue
        print(f"{w.word} ")
    print()

def main():
    parser = argparse.ArgumentParser(description="Display sentences from the database.")
    parser.add_argument("--database", required=True, help="Path to the SQLite database")
    parser.add_argument("--story-id", type=int, help="Story ID")
    parser.add_argument("--sentence-id", type=int, help="Sentence ID")
    parser.add_argument("--sentence-number", type=int, help="Sentence number")
    parser.add_argument("--word-by-word", action="store_true", help="Display sentence word by word")
    parser.add_argument("--show-paths", action="store_true", help="Show paths for each word")
    parser.add_argument("--show-incomplete", action="store_true", help="Show sentences with incomplete paths")
    parser.add_argument("--only-incomplete", action="store_true", help="Only show the words with incomplete paths")
    args = parser.parse_args()

    if args.sentence_number and not args.story_id:
        sys.exit("Error: --sentence-number requires --story-id to be set")

    if args.show_paths or args.show_incomplete or args.only_incomplete:
        args.word_by_word = True

    if args.only_incomplete:
        args.show_incomplete = True

    conn = get_db_connection(args.database)

    if not args.sentence_id and not args.sentence_number:
        if args.story_id:
            # Then we are getting a whole story. This is quite common and normal
            sentences = get_sentence_ids_of_story(conn, args.story_id)
        else:
            # Getting all stories
            sentences = get_all_sentences(conn)
        for sentence in sentences:
            if args.word_by_word:
                display_word_by_word(conn, sentence, args.show_paths, args.show_incomplete, args.only_incomplete)
            else:
                display_sentence(conn, sentence)
    else:
        sentence = get_sentence_id(conn, args.story_id, args.sentence_id, args.sentence_number)
        if sentence is None:
            sys.exit("Error: no sentences match the arguments given")
        if args.word_by_word:
            display_word_by_word(conn, sentence, args.show_paths, args.show_incomplete, args.only_incomplete)
        else:
            display_sentence(conn, sentence)

    conn.close()

if __name__ == "__main__":
    main()
