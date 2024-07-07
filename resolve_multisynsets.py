#!/usr/bin/env python3

import argparse
import json
import sqlite3
import ollama
import time
import signal

import sys
parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, help="Where the database is")
parser.add_argument("--congruent", type=int, help="Only process rows with ids that are congruent to this number")
parser.add_argument("--modulo", type=int, help="Only process rows with ids that are congruent to --congruent modulo this number")
parser.add_argument("--limit", type=int, help="Stop after processing this many rows")
parser.add_argument("--progress-bar", action="store_true", help="Show a progress bar")
parser.add_argument("--model", default="phi3", help="Which ollama model to use")
parser.add_argument("--show-conversation", action="store_true", help="Show the prompt and output from the language model")
args = parser.parse_args()

conn = sqlite3.connect(args.database)
cursor = conn.cursor()
cursor.execute("pragma busy_timeout = 30000;")
cursor.execute("pragma journal_mode = WAL;")

if (args.congruent is not None and args.modulo is None) or (args.congruent is None and args.modulo is not None):
    sys.exit("Must specify both --congruent and --modulo or neither")

query = "select id, sentence_id, word_number, word from words where resolved_synset is null"

if args.congruent is not None and args.modulo is not None:
    cursor.execute(f"create index if not exists unresolved_words_{args.congruent}_mod_{args.modulo} on words(id) where resolved_synset is null and id % {args.modulo} = {args.congruent}")
    query += f" and id % {args.modulo} = {args.congruent}"
else:
    cursor.execute(f"create index if not exists unresolved_words on words(resolved_synset) where resolved_synset is null")

if args.limit is not None:
    query += f" limit {args.limit}"

cursor.execute(query)
iterator = []
for row in cursor:
    iterator.append(row)

if args.progress_bar:
    import tqdm
    if args.limit:
        iterator = tqdm.tqdm(iterator, total=args.limit)
    else:
        iterator = tqdm.tqdm(iterator)


def get_sentence(sentence_id):
    sentence_cursor = conn.cursor()
    # if synset_cursor pragmas are redundant, then these are too
    sentence_cursor.execute("pragma busy_timeout = 30000;")
    sentence_cursor.execute("pragma journal_mode = WAL;")
    sentence_cursor.execute("select sentence from sentences where sentences.id = ?", [sentence_id])
    row = sentence_cursor.fetchone()
    if row is None:
        sys.exit(f"Impossible condition: missing sentence #{sentence_id}")
    sentence = row[0]
    sentence_cursor.close()

def get_synsets(word_id):
    synset_cursor = conn.cursor()
    # I don't know if this is necessary
    synset_cursor.execute("pragma busy_timeout = 30000;")
    synset_cursor.execute("pragma journal_mode = WAL;")
    synset_cursor.execute("select synsets.id, description, examples from synsets join word_synsets on (synsets.id = synset_id) and word_id = ?", [word_id])
    answer = []
    for row in synset_cursor:
        answer.append(row)
    return answer

need_to_stop_now = False

def handle_interruption(signum, frame):
    global need_to_stop_now
    need_to_stop_now = True

signal.signal(signal.SIGTERM, handle_interruption)

for (word_id, sentence_id, word_number, word) in iterator:
    starting_moment = time.time()
    sentence = get_sentence(sentence_id)

    prompt = f"""Consider this sentence:
    {sentence}
The word `{word}` (which is word #{word_number+1}) can have multiple meanings. Which of the following meanings is it being used for in this sentence?

"""
    for (synset_id, description, examples) in get_synsets(word_id):
        prompt += f" ({synset_id}) -- {description}"
        if examples is not None and examples.strip() != '':
            prompt += f"\n       Example use: {examples}"
        prompt += "\n\n"
    prompt += """ (other) -- none of those synsets match the word's meaning here


Answer in JSON format, with a key of "synset", e.g.

{
    "synset": "foo.n.01"
}

    or

{
    "synset": "(other)"
}
    """

    if args.show_conversation:
        sys.stderr.write("-" * 70 + "\n")
        sys.stderr.write(time.asctime())
        sys.stderr.write(prompt)
        sys.stderr.write("\n")
    response = ollama.chat(model=args.model, messages=[
        {
            'role': 'user',
            'content': prompt
        }
        ],format='json', stream=True)
    so_far = ""
    for chunk in response:
        if args.show_conversation:
            sys.stderr.write(chunk['message']['content'])
            sys.stderr.flush()
        so_far += chunk['message']['content']
        try:
            answer = json.loads(so_far)
            # if that worked...
            break
        except:
            pass
    compute_time = time.time() - starting_moment

    if 'synset' in answer:
        update_cursor = conn.cursor()
        update_cursor.execute("update words set resolved_synset = ?, resolving_model=?, resolved_timestamp = current_timestamp, resolution_compute_time=? where id = ?", [answer['synset'], args.model, compute_time, word_id])
        conn.commit()
        update_cursor.close()
    if need_to_stop_now:
        sys.exit(0)
