#!/usr/bin/env python3

import argparse
import json
import requests
import ollama
import time
import backoff

import sys
parser = argparse.ArgumentParser()
parser.add_argument("--server", required=True, help="Where the server is running")
parser.add_argument("--congruent", type=int, help="Only process rows with ids that are congruent to this number")
parser.add_argument("--modulo", type=int, help="Only process rows with ids that are congruent to --congruent modulo this number")
parser.add_argument("--limit", type=int, help="Stop after processing this many rows")
parser.add_argument("--progress-bar", action="store_true", help="Show a progress bar")
parser.add_argument("--model", default="llama3", help="Which ollama model to use")
parser.add_argument("--show-conversation", action="store_true", help="Show the prompt and output from the language model")
parser.add_argument("--mild-logging", action="store_true", help="Show a few logs, just so that we know something is happening.")

args = parser.parse_args()

def get_server(target):
    if ':' in args.server:
        return f'http://[{args.server}]:5000/{target}'
    else:
        return f'http://{args.server}:5000/{target}'

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300)
def get_unresolved_words():
    params = {}
    if args.congruent is not None and args.modulo is not None:
        params['congruent'] = args.congruent
        params['modulo'] = args.modulo
    if args.limit is not None:
        params['limit'] = args.limit
    more_words = True
    while more_words:
        more_words = False
        r = requests.get(get_server('unresolved'), params=params)
        if r.status_code != 200:
             sys.exit(f"{r.status_code} error from {args.server}: {r.text}")
        for word in r.json():
             more_words = True
             yield word


@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300)
def get_sentence(sentence_id):
    r = requests.get(get_server('sentence'), params={'sentence_id': sentence_id})
    if r.status_code != 200:
        sys.exit(f"{r.status_code} error from {args.server}: {r.text}")
    return r.json()['sentence']

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300)
def get_synsets(word_id):
    r = requests.get(get_server('synsets'), params={'word_id': word_id})
    if r.status_code != 200:
        sys.exit(f"{r.status_code} error from {args.server}: {r.text}")
    return r.json()

@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_time=300)
def update(word_id, synset_id, compute_time, model):
    r = requests.post(get_server('update'),
                      json={'word_id': word_id,
                            'resolved_synset': synset_id,
                            'compute_time': compute_time,
                            'model': model })


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

    if args.mild_logging:
        sys.stderr.write(f"{time.asctime()} {word} (##{word_number+1}) {sentence}")

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
    if 'synset' in answer:
        update(word_id, answer['synset'], compute_time, args.model)
        if args.mild_logging:
            sys.stderr.write(f": {answer['synset']}\n")
    elif args.mild_logging:
        sys.stderr.write(f": got an answer that doesn't make sense: {answer}\n")


if args.mild_logging:
    sys.stderr.write(f"{time.asctime()} No more words to process.\n")
