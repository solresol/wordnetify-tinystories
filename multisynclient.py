#!/usr/bin/env python3

import argparse
import json
import requests
import ollama
import time

import sys
parser = argparse.ArgumentParser()
parser.add_argument("--server", required=True, help="Where the server is running")
parser.add_argument("--congruent", type=int, help="Only process rows with ids that are congruent to this number")
parser.add_argument("--modulo", type=int, help="Only process rows with ids that are congruent to --congruent modulo this number")
parser.add_argument("--limit", type=int, help="Stop after processing this many rows")
parser.add_argument("--progress-bar", action="store_true", help="Show a progress bar")
parser.add_argument("--model", default="llama3", help="Which ollama model to use")
parser.add_argument("--show-conversation", action="store_true", help="Show the prompt and output from the language model")
args = parser.parse_args()

def get_unresolved_words():
    url = f'http://{args.server}:5000/unresolved'
    params = {}
    if args.congruent is not None and args.modulo is not None:
        params['congruent'] = args.congruent
        params['modulo'] = args.modulo
    if args.limit is not None:
        params['limit'] = args.limit
    r = requests.get(url, params=params)
    if r.status_code != 200:
        sys.exit(f"{r.status_code} error from {args.server}: {r.text}")
    for word in r.json():
        yield word


def get_sentence(sentence_id):
    r = requests.get(f'http://{args.server}:5000/sentence', params={'sentence_id': sentence_id})
    if r.status_code != 200:
        sys.exit(f"{r.status_code} error from {args.server}: {r.text}")
    return r.json()['sentence']

def get_synsets(word_id):
    r = requests.get(f'http://{args.server}:5000/synsets', params={'word_id': word_id})
    if r.status_code != 200:
        sys.exit(f"{r.status_code} error from {args.server}: {r.text}")    
    return r.json()


if args.progress_bar:
    import tqdm
    if args.limit:
        iterator = tqdm.tqdm(get_unresolved_words(), total=args.limit)
    else:
        iterator = tqdm.tqdm(get_unresolved_words())
else:
    iterator = get_unresolved_words()


for word_obj in iterator:
    word_id = word_obj['word_id']
    sentence_id = word_obj['sentence_id']
    word_number = word_obj['word_number']
    word = word_obj['word']
    sentence = get_sentence(sentence_id)
    if sentence is None:
        sys.exit(f"Failed to get sentence #{sentence_id}")

    prompt = f"""Consider this sentence:
    {sentence}
The word `{word}` (which is word #{word_number+1}) can have multiple meanings. Which of the following meanings is it being used for in this sentence?

"""
    for synset in get_synsets(word_id):
        synset_id = synset['synset_id']
        description = synset['description']
        prompt += f" ({synset_id}) -- {description}"
        if 'example' in synset and synset['example'].strip() != '':
            prompt += f"\n       Example use: {synset['example']}"
        prompt += "\n\n"
    prompt += """ (other) -- none of those synsets match the word's meaning here


Answer in JSON format, with a key of "synset", e.g.

{
    "synset": "foo.n.01"
}
    """

    if args.show_conversation:
        sys.stderr.write("-" * 70 + "\n")
        sys.stderr.write(time.asctime())
        sys.stderr.write(prompt)
        sys.stderr.write("\n")
    starting_moment = time.time()
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

    r = requests.post(f'http://{args.server}:5000/update',
                      json={'word_id': word_id,
                            'resolved_synset': answer['synset'],
                            'compute_time': compute_time,
                            'model': args.model })
