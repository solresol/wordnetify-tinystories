import nltk
from nltk.corpus import wordnet as wn
import sqlite3
import argparse

def get_hypernym_path(synset):
    if synset.name() == 'entity.n.01':
        return [synset]
    
    hypernyms = synset.hypernyms()
    if not hypernyms:
        return []
    
    hypernym_path = get_hypernym_path(hypernyms[0])
    if not hypernym_path:
        return []
    
    return hypernym_path + [synset]

def get_path_string(synset):
    path = get_hypernym_path(synset)
    if not path:
        return None
    
    path_indices = ['1']  # Start with '1' for the root entity
    for i in range(len(path) - 1):
        parent = path[i]
        child = path[i+1]
        hyponyms = sorted(parent.hyponyms(), key=lambda s: s.name())
        index = hyponyms.index(child) + 1
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

    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traverse WordNet and store paths in SQLite.")
    parser.add_argument("--sqlite", default="wordnet.db", help="Path to output SQLite database")
    args = parser.parse_args()

    nltk.download('wordnet', quiet=True)
    traverse_wordnet(args.sqlite)
    print("WordNet traversal completed.")
