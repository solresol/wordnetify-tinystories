#!/usr/bin/env python3

import argparse
import json
import sqlite3
import time
import os

import sys
parser = argparse.ArgumentParser()
if 'DATABASE' in os.environ:
    database=os.environ['DATABASE']
else:
    parser.add_argument("--database", required=True, help="Where the database is")
    args = parser.parse_args()
    database = args.database

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/unresolved', methods=['GET'])
def unresolved():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("pragma busy_timeout = 30000;")
    cursor.execute("pragma journal_mode = WAL;")
    congruent = request.args.get('congruent', default=None, type=int)
    modulo = request.args.get('modulo', default=None, type=int)
    limit = request.args.get('limit', default=None, type=int)
    query = "select id, sentence_id, word_number, word from words where resolved_synset is null"
    if congruent is not None and modulo is not None:
        cursor.execute(f"create index if not exists unresolved_words_{congruent}_mod_{modulo} on words(id) where resolved_synset is null and id % {modulo} = {congruent}")
        query += f" and id % {modulo} = {congruent}"
    else:
        cursor.execute(f"create index if not exists unresolved_words on words(resolved_synset) where resolved_synset is null")
    if limit is not None:
        query += f" limit {limit}"

    cursor.execute(query)
    answer = []
    # next two lines should probably fetchall
    for (word_id, sentence_id, word_number, word) in cursor:
        answer.append({'word_id': word_id,
                       'sentence_id': sentence_id,
                       'word_number': word_number,
                       'word': word})
    cursor.close()
    conn.close()
    return jsonify(answer)

@app.route('/sentence', methods=['GET'])
def sentence():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("pragma busy_timeout = 30000;")
    cursor.execute("pragma journal_mode = WAL;")
    sentence_id = request.args.get('sentence_id', default=None, type=int)
    
    if sentence_id is None:
        return jsonify({'error': 'Sentence ID is required'}), 400
    cursor.execute("select sentence from sentences where sentences.id = ?", [sentence_id])
    row = cursor.fetchone()
    if row is None:
        return jsonify({'error': 'Sentence ID not found'}), 404
    sentence = row[0]
    result = {'sentence': sentence }
    cursor.close()
    conn.close()
    return jsonify(result)

@app.route('/synsets', methods=['GET'])
def synsets():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("pragma busy_timeout = 30000;")
    cursor.execute("pragma journal_mode = WAL;")
    word_id = request.args.get('word_id', default=None, type=int)
    
    if word_id is None:
        return jsonify({'error': 'Word ID is required'}), 400

    cursor.execute("select synsets.id, description, examples from synsets join word_synsets on (synsets.id = synset_id) and word_id = ?", [word_id])
    answer = []
    for (synset_id, description, example) in cursor:
        answer.append({'synset_id': synset_id,
                       'description': description})
        if example is not None:
            answer[-1]['example'] = example
    cursor.close()
    conn.close()
    return jsonify(answer)

@app.route('/update', methods=['POST'])
def update():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("pragma busy_timeout = 30000;")
    cursor.execute("pragma journal_mode = WAL;")
    data = request.json
    
    if 'word_id' not in data or 'resolved_synset' not in data or 'compute_time' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    word_id = data['word_id']
    resolved_synset = data['resolved_synset']
    compute_time = data['compute_time']
    model = data['model']

    cursor.execute("update words set resolved_synset = ?, resolving_model=?, resolved_timestamp = current_timestamp, resolution_compute_time=? where id = ?", [resolved_synset, model, compute_time, word_id])
    conn.commit()
    
    result = {'message': 'done'}
    cursor.close()
    conn.close()
    return jsonify(result)

if __name__ == '__main__':
    import os
    if 'MASTER_ADDR' in os.environ:
       app.run(host=os.environ['MASTER_ADDR'])
    else:
       app.run(host='0.0.0.0')


