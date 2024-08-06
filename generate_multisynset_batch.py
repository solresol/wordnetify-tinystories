#!/usr/bin/env python3

import argparse
import json
import sqlite3
import time
import signal
import os
import openai

import sys
parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, help="Where the database is")
parser.add_argument("--congruent", type=int, help="Only process rows with ids that are congruent to this number")
parser.add_argument("--modulo", type=int, help="Only process rows with ids that are congruent to --congruent modulo this number")
parser.add_argument("--limit", type=int, help="Stop after processing this many rows")
parser.add_argument("--progress-bar", action="store_true", help="Show a progress bar")
parser.add_argument("--output-file", required=True, help="Where to put the batch file")
parser.add_argument("--dry-run", action="store_true", help="Don't send the batch to OpenAI")
parser.add_argument("--verbose", action="store_true", help="Lots of debugging messages")
parser.add_argument("--openai-api-key", default=os.path.expanduser("~/.openai.key"))
args = parser.parse_args()

conn = sqlite3.connect(args.database)
cursor = conn.cursor()
update_cursor = conn.cursor()
cursor.execute("pragma busy_timeout = 30000;")
cursor.execute("pragma journal_mode = WAL;")
update_cursor.execute("pragma busy_timeout = 30000;")
update_cursor.execute("pragma journal_mode = WAL;")

update_cursor.execute("create table if not exists batches (id integer primary key autoincrement, openai_batch_id text, when_created datetime default current_timestamp, when_sent datetime, when_retrieved datetime)")
update_cursor.execute("create index if not exists batches_to_retrieve on batches(openai_batch_id) where when_sent is not null and when_retrieved is null")
cursor.execute("create table if not exists batchwords (batch_id integer references batches(id), word_id integer references words(id))")
update_cursor.execute("create index if not exists batches_by_word_id on batchwords(word_id)")
update_cursor.execute("create index if not exists batches_by_batch_id on batchwords(batch_id)")


update_cursor.execute("begin transaction;")
update_cursor.execute("insert into batches default values")
batch_id = update_cursor.lastrowid


if (args.congruent is not None and args.modulo is None) or (args.congruent is None and args.modulo is not None):
    sys.exit("Must specify both --congruent and --modulo or neither")

pronouns_and_punctuation = ['i', 'me', 'my', 'mine',
                'you', 'your', 'u',
                'he', 'him', 'his',
                'she', 'her',
                'it', 'its',
                'we', 'us', 'our',
                'they', 'them', 'their', '!', '.', '?']
quoted_pronouns_and_punctuation = [f"'{x}'" for x in pronouns_and_punctuation]
pronoun_exclusion_clause = f"lower(word) not in (" + (', '.join(quoted_pronouns_and_punctuation)) + ')'

query = "select distinct story_id, words.id, sentence_id, word_number, word from words join sentences on (sentence_id = sentences.id) left join batchwords on (words.id = batchwords.word_id) left join batches on (batch_id = batches.id) where resolved_synset is null and synset_count > 1 and " + pronoun_exclusion_clause + " and (batch_id is null)"

if args.congruent is not None and args.modulo is not None:
    query += f" and story_id % {args.modulo} = {args.congruent}"
    cursor.execute(f"create index if not exists sentences_by_story_{args.congruent}_mod_{args.modulo} on sentences(id) where story_id % {args.modulo} = {args.congruent}")
else:
    cursor.execute(f"create index if not exists unresolved_words on words(resolved_synset) where resolved_synset is null and synset_count > 1")

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
    sentence_cursor.execute("select sentence from sentences where id = ?", [sentence_id])
    row = sentence_cursor.fetchone()
    if row is None:
        sys.exit(f"Impossible condition: missing sentence #{sentence_id}")
    sentence = row[0]
    sentence_cursor.close()
    return sentence

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

tools = [ { "type": "function",
            "function": {
                "name": "specify_synset",
                "description": "Specify which synset is being used",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "synset": {
                            "type": "string",
                            "description": "Which synset the word corresponds to, or '(other)' if none of the supplied synsets are appropriate",
                        }
                    },
                    "required": ["synset"],
                },
            },
        }
    ]

output_file = open(args.output_file, 'w')

for (story_id, word_id, sentence_id, word_number, word) in iterator:
    if args.progress_bar:
      iterator.set_description(f"Story {story_id}")
    if word.lower() in pronouns_and_punctuation:
       # Shouldn't happen
       continue
    sentence = get_sentence(sentence_id)

    prompt = f"""Consider this sentence:
    {sentence}
The word `{word}` (which is word #{word_number+1}) can have multiple meanings. Which of the following meanings is it being used for in this sentence?

"""
    alternatives = 0
    for (synset_id, description, examples) in get_synsets(word_id):
        alternatives += 1
        prompt += f" ({synset_id}) -- {description}"
        if examples is not None and examples.strip() != '':
            prompt += f"\n       Example use: {examples}"
        prompt += "\n\n"
    if alternatives == 0:
       continue
    prompt += """ (other) -- none of those synsets match the word's meaning here
"""

    messages = [{'role': 'user', 'content': prompt}]
    batch_text = {
        "custom_id": str(word_id),
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": "specify_synset"}}
        }
    }
    output_file.write(json.dumps(batch_text) + "\n")
    if args.verbose:
        print(word_id, word, sentence)
    update_cursor.execute("insert into batchwords (batch_id, word_id) values (?,?)", [batch_id, word_id])

output_file.close()
if args.dry_run:
    conn.rollback()
    sys.exit(0)

api_key = open(args.openai_api_key).read().strip()
client = openai.OpenAI(api_key=api_key)

batch_input_file = client.files.create(
  file=open(args.output_file, "rb"),
  purpose="batch"
)

batch_input_file_id = batch_input_file.id

result = client.batches.create(
    input_file_id=batch_input_file_id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
    metadata={
        "description": f"{args.database} batch {batch_id} (wordnetify)",
        "database": f"{args.database}",
        "local_batch_id": f"{batch_id}"
    }
)

update_cursor.execute("update batches set openai_batch_id = ?, when_sent = current_timestamp where id = ?",
         [result.id, batch_id])
if update_cursor.rowcount != 1:
    sys.exit(f"Unexpectedly updated {update_cursor.rowcount} rows when we set the openai_batch id to {result.id} for batch {batch_id}")

conn.commit()
