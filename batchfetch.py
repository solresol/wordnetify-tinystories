#!/usr/bin/env python3

import argparse
import os
import sys
import openai
import sqlite3
import time
import json

parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, help="Where the database is")
parser.add_argument("--openai-api-key", default=os.path.expanduser("~/.openai.key"))
parser.add_argument("--progress-bar", action='store_true', help="Show a progress bar for updating the database on each batch")
parser.add_argument("--report-costs", action="store_true", help="Report the cost of the runs fetched")
args = parser.parse_args()

api_key = open(args.openai_api_key).read().strip()
client = openai.OpenAI(api_key=api_key)

conn = sqlite3.connect(args.database)
cursor = conn.cursor()
update_cursor = conn.cursor()

cursor.execute("pragma busy_timeout = 30000;")
cursor.execute("pragma journal_mode = WAL;")
update_cursor.execute("pragma busy_timeout = 30000;")
update_cursor.execute("pragma journal_mode = WAL;")

cursor.execute("select id, openai_batch_id from batches where when_sent is not null and when_retrieved is null")

total_prompt_tokens = 0
total_completion_tokens = 0

update_cursor.execute("begin transaction")
work_to_be_done = False
for local_batch_id, openai_batch_id in cursor:
    openai_result = client.batches.retrieve(openai_batch_id)
    if openai_result.status != 'completed':
        continue
    file_response = client.files.content(openai_result.output_file_id)
    iterator = file_response.text.splitlines()
    if args.progress_bar:
        import tqdm
        iterator = tqdm.tqdm(iterator)
        if 'description' in openai_result.metadata:
            iterator.set_description(openai_result.metadata['description'])
    for row in iterator:
        record = json.loads(row)
        if record['response']['status_code'] != 200:
            continue
        arguments = json.loads(record['response']['body']['choices'][0]['message']['tool_calls'][0]['function']['arguments'])
        if 'synset' not in arguments:
            continue
        model = record['response']['body']['model'] + " (batch)"
        word_id = int(record['custom_id'])
        usage = record['response']['body']['usage']
        update_cursor.execute("update words set resolved_synset = ?, resolving_model=?, resolved_timestamp = current_timestamp where id = ?", [arguments['synset'], model, word_id])
        update_cursor.execute("insert into costs (word_id, prompt_tokens, completion_tokens) values (?,?,?)",
                              [word_id, usage['prompt_tokens'], usage['completion_tokens']])
        total_prompt_tokens += usage['prompt_tokens']
        total_completion_tokens += usage['completion_tokens']
    update_cursor.execute("update batches set when_retrieved = current_timestamp where id = ?", [local_batch_id])
conn.commit()

if args.report_costs:
    print(f"Prompt tokens:     {total_prompt_tokens}")
    print(f"Completion tokens: {total_completion_tokens}")
    prompt_pricing = 0.075 / 1000000
    completion_pricing = 0.3 / 1000000
    cost = prompt_pricing * total_prompt_tokens + completion_pricing * total_completion_tokens
    print(f"Cost (USD):        {cost:.2f}")
