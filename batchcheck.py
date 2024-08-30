#!/usr/bin/env python3

import argparse
import os
import sys
import openai
import sqlite3
import time

parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True, help="Where the database is")
parser.add_argument("--openai-api-key", default=os.path.expanduser("~/.openai.key"))
parser.add_argument("--only-batch", type=int, help="The batch ID to look at")
parser.add_argument("--monitor", action="store_true", help="Monitor in a loop until the status is 'completed'. Only makes sense with --only-batch")
args = parser.parse_args()

api_key = open(args.openai_api_key).read().strip()
client = openai.OpenAI(api_key=api_key)

conn = sqlite3.connect(args.database)
cursor = conn.cursor()
update_cursor = conn.cursor()
update_cursor.execute("create table if not exists batchprogress (batch_id int references batches(id), when_checked datetime default current_timestamp, number_completed int, number_failed int)")

query = "select batches.id, openai_batch_id, count(word_id) from batches join batchwords on (batch_id = batches.id) where when_sent is not null and when_retrieved is null "
if args.only_batch:
    query += f"and batches.id = {int(args.only_batch)} "
query += "group by batches.id, openai_batch_id"

if args.monitor:
    import tqdm
    progress = None

while True:
    cursor.execute(query)
    work_to_be_done = False

    for local_batch_id, openai_batch_id, number_of_words in cursor:
        openai_result = client.batches.retrieve(openai_batch_id)
        if openai_result.status == 'completed':
            work_to_be_done = True
        if openai_result.status in ['in_progress','completed']:
            update_cursor.execute("insert into batchprogress (batch_id, number_completed, number_failed) values (?,?,?)",
                                  [local_batch_id,
                                   openai_result.request_counts.completed,
                                   openai_result.request_counts.failed])
            conn.commit()
        if args.monitor:
            if progress is None:
                # To be smarter, I should keep track of the number of words that were already done
                # at the start
                progress = tqdm.tqdm(total=number_of_words)
            progress.set_description(openai_result.status)
            if openai_result.status in ['in_progress', 'completed']:
                progress.update(openai_result.request_counts.completed - progress.n)
            if openai_result.status == 'completed':
                break
            time.sleep(15)
            continue
        print(f"""## {openai_result.metadata.get('description')}
      Num words: {number_of_words}
       Local ID: {local_batch_id}
       Returned: {openai_result.metadata.get('local_batch_id')}
       Database: {openai_result.metadata.get('database')}
             Vs: {args.database}
       Batch ID: {openai_batch_id}
        Created: {time.asctime(time.localtime(openai_result.created_at))}
         Status: {openai_result.status}""")
        if openai_result.errors:
            print("      Errors: ")
            for err in openai_result.errors.data:
                 print(f"         - {err.code} on line {err.line}: {err.message}")
        if openai_result.request_counts:
            print(f"       Progress: {openai_result.request_counts.completed}/{openai_result.request_counts.total}")
            print(f"       Failures: {openai_result.request_counts.failed}")
        print()
        #print(openai_result)
    if not args.monitor:
        break
    if work_to_be_done:
        break
if work_to_be_done:
    sys.exit(0)
else:
    sys.exit(1)
