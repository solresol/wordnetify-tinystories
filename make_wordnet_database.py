#!/usr/bin/env python3

import nltk
from nltk.corpus import wordnet as wn
import sqlite3
import argparse
import sys
import hashlib

def get_hypernym_path(synset):
    if synset.name() == 'entity.n.01':
        return [synset]

    hypernyms = sorted(synset.hypernyms())
    if not hypernyms:
        return [synset]

    shortest_path = None
    for hypernym in hypernyms:
        hypernym_path = get_hypernym_path(hypernym)
        if not hypernym_path:
            continue
        if not shortest_path:
            shortest_path = hypernym_path
            continue
        shortest_path = shortest_path if len(shortest_path) < len(hypernym_path) else hypernym_path

    return hypernym_path + [synset]

def hash_synset(synset):
    return hash_thing(synset.name())

def hash_thing(thing):
    return str(int(hashlib.sha256(thing.encode('utf-8')).hexdigest(),16) % (2**32))

def get_path_string(synset):
    # 1 = noun
    # 1.2 = pronoun
    # 2 = adjective
    # 3 = verb
    # 4 = adverb
    # 5 = punctuation

    # Adjectives, we're kind of weak on. We just hash them.
    if synset.pos() in ['a', 's']:
        return f'2.{hash_synset(synset)}'

    if synset.pos() in ['r']:
        return f'4.{hash_synset(synset)}'

    if synset.pos() in ['n', 'v']:
        path = get_hypernym_path(synset)
        if not path:
            sys.exit(f"No path for {synset}")

        if synset.pos() == 'n':
            path_indices = ['1']  # Start with '1' for the nouns
        else:
            path_indices = ['3']
        path_indices.append(hash_synset(path[0]))
        for i in range(len(path) - 1):
            parent = path[i]
            child = path[i+1]
            hyponyms = sorted(parent.hyponyms(), key=lambda s: s.name())
            try:
                index = hyponyms.index(child) + 1
            except ValueError:
                # bug in wordnet: wn.synset('inhibit.v.04').hypernyms()[0].hyponyms() doesn't show inhibit.v.01
                if child.name() == 'inhibit.v.04':
                    index = 2
                else:
                    raise
            path_indices.append(str(index))

        return '.'.join(path_indices)

def traverse_wordnet(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS synset_paths
                 (path TEXT PRIMARY KEY,
                  synset_name TEXT UNIQUE,
                  definition TEXT)''')

    for synset in wn.all_synsets():
        path = get_path_string(synset)
        if path:
            c.execute("INSERT OR REPLACE INTO synset_paths (path, synset_name, definition) VALUES (?, ?, ?)",
                      (path, synset.name(), synset.definition()))
        else:
            print(f"No path for {synset}")
            input()

    conn.commit()
    conn.close()

def add_misc(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    personal_pronouns = [ 'i', 'me', 'you', 'he', 'him', 'she', 'her',
                          'it', 'we', 'us', 'they', 'them' ]
    possessive_pronouns = [ 'my', 'mine', 'your', 'yours', 'his',
                            'her', 'hers', 'its', 'our', 'ours', 'their', 'theirs' ]
    reflexive_pronouns = [ 'myself', 'yourself', 'yourselves',
                           'himself', 'herself', 'itself', 'ourselves', 'themselves',
                           'themself' ]
    demonstrative_pronouns = [ 'this', 'that', 'these', 'those' ]
    interrogative_and_relative_pronouns = [ 'who', 'whom', 'whose',
                                            'which', 'what',
                                            # 'that'
                                           ]
    terminal_punctuation = ['.', '?', '!']
    pausing_and_separating_punctuation = [',', ';', ':', '-',  '--']
    quotation_and_parenthetical_punctuation = ['"', "'", '(', ')', '[', ']', '...']
    linking_punctuation = ['/']
    specialized_punctuation = ['...', '&', '*', '^', '•']

    conjunctions = ['and', 'or', 'but', 'nor', 'for', 'yet', 'so', 'either', 'neither', 'whether', 'both']
    # I have no structure for prepositions.
    prepositions = ['in', 'on', 'at', 'by', 'with', 'about', 'against', 'between', 'into', 'through', 'during',
                    'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'behind',
                    'near', 'far', 'inside', 'outside', 'onto', 'off', 'across', 'along', 'toward', 'throughout',
                    'per', 'beyond', 'via',
                    'under', 'over', 'for', 'of', 'among', 'around', 'beside', 'besides', 'despite',
                    'except', 'like', 'unlike', 'since', 'until', 'till', 'within', 'without',
                    'underneath', 'beneath', 'versus', 'amid', 'amidst', 'amongst',
                    'as', 'but', 'concerning', 'considering', 'depending', 'excluding', 'following',
                    'including', 'notwithstanding', 'pending', 'regarding', 'save', 'touching', 'upon',
                    'whereas', 'vs']
    articles = ['the', 'a', 'an']


    for i,p in enumerate(personal_pronouns):
        c.execute("insert or replace into synset_paths (path, synset_name) values ('1.2.1' || ?, ?)", [i+1, p])
    for i,p in enumerate(possessive_pronouns):
        c.execute("insert or replace into synset_paths (path, synset_name) values  ('1.2.2' || ?, ?)", [i+1, p])
    for i,p in enumerate(reflexive_pronouns):
        # I'm not quite happy with this: I think these should live under "adjectives" (2.*) some of the time.
        c.execute("insert or replace into synset_paths (path, synset_name) values  ('1.2.3' || ?, ?)", [i+1, p])

    for i,p in enumerate(demonstrative_pronouns):
        # I'm not quite happy with this either: I think these should live under "nouns" (1.*) some of the time.
        c.execute("insert or replace into synset_paths (path, synset_name)  values ('2.1.1' || ?, ?)", [i+1, p])

    for i,p in enumerate(interrogative_and_relative_pronouns):
        c.execute("insert or replace into synset_paths (path, synset_name) values  ('1.2.4' || ?, ?)", [i+1, p])

    for i,p in enumerate(terminal_punctuation):
        c.execute("insert or replace into synset_paths (path, synset_name)  values ('5.1.1' || ?, ?)", [i+1, p])
    for i,p in enumerate(pausing_and_separating_punctuation):
        c.execute("insert or replace into synset_paths (path, synset_name) values  ('5.2' || ?, ?)", [i+1, p])
    for i,p in enumerate(quotation_and_parenthetical_punctuation):
        c.execute("insert or replace into synset_paths (path, synset_name)  values ('5.3' || ?, ?)", [i+1, p])
    for i,p in enumerate(linking_punctuation):
        c.execute("insert or replace into synset_paths (path, synset_name)  values ('5.4' || ?, ?)", [i+1, p])
    for i,p in enumerate(specialized_punctuation):
        c.execute("insert or replace into synset_paths (path, synset_name)  values ('5.5' || ?, ?)", [i+1, p])

    # Adding conjunctions
    for i, conj in enumerate(conjunctions):
        c.execute("insert or replace into synset_paths (path, synset_name) values ('5.1.2.' || ?, ?)", [i+1, conj])

    # Adding prepositions using hash function
    for prep in prepositions:
        hash_val = hash_thing(prep)
        c.execute("insert or replace into synset_paths (path, synset_name) values ('6.' || ?, ?)", [hash_val, prep])

    # Adding articles
    for i, article in enumerate(articles):
        c.execute("insert or replace into synset_paths (path, synset_name) values ('7.' || ?, ?)", [i+1, article])

    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traverse WordNet and store paths in SQLite.")
    parser.add_argument("--database", required=True, help="Path to output SQLite database")
    args = parser.parse_args()

    nltk.download('wordnet', quiet=True)
    traverse_wordnet(args.database)
    add_misc(args.database)
    print("WordNet traversal completed.")
