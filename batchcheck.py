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
args = parser.parse_args()

api_key = open(args.openai_api_key).read().strip()
client = openai.OpenAI(api_key=api_key)

conn = sqlite3.connect(args.database)
cursor = conn.cursor()
cursor.execute("select batches.id, openai_batch_id, count(word_id) from batches join batchwords on (batch_id = batches.id) where when_sent is not null and when_retrieved is null group by batches.id, openai_batch_id")
work_to_be_done = False
for local_batch_id, openai_batch_id, number_of_words in cursor:
    openai_result = client.batches.retrieve(openai_batch_id)
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
    print()
    if openai_result.status == 'completed':
        work_to_be_done = True

if work_to_be_done:
    sys.exit(0)
else:
    sys.exit(1)
