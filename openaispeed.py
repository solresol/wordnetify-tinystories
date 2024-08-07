#!/usr/bin/env python3

import sqlite3
import argparse
import pandas

parser = argparse.ArgumentParser()
parser.add_argument("--database", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

conn = sqlite3.connect(args.database)
cursor = conn.cursor()

batch_ids = pandas.read_sql("select distinct batch_id from batchprogress", conn)
rates = None
for batch_id in batch_ids.batch_id:
    this_batch = pandas.read_sql(f"select when_checked, number_completed + number_failed as processed from batchprogress where batch_id = {batch_id}", conn)
    this_batch.when_checked = pandas.to_datetime(this_batch.when_checked)
    this_batch['previous_processed'] = this_batch.processed.shift()
    this_batch['previous_timestamp'] = this_batch.when_checked.shift()
    this_batch['duration'] = (this_batch.when_checked - this_batch.previous_timestamp).dt.seconds
    this_batch['delta'] = this_batch.processed - this_batch.previous_processed
    this_batch['rate'] = this_batch.delta / this_batch.duration
    this_batch.set_index('when_checked', inplace=True)
    resampled_series = this_batch['rate'].resample('5T').mean()
    if rates is None:
        rates = resampled_series
    else:
        rates = pandas.concat([rates, resampled_series])

rates.to_csv(args.output)
      
