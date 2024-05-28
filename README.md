# wordnetify-tinystories

Takes a TinyStories file and converts each word to a wordnet node.

# Usage

Set up a virtualenv and install dependencies.

`virtualenv .venv`

`. .venv/bin/activate`

`pip install -r requirements.txt`

Download `TinyStoriesV2-GPT4-train.txt` and `TinyStoriesV2-GPT4-valid.txt`

Run:

`./wordnetify.py --database tinystories.sqlite --progress --file TinyStoriesV2-GPT4-valid.txt`

Make a note of how long that took, because the next command will take 100x longer:

`./wordnetify.py --database tinystories.sqlite --progress --file TinyStoriesV2-GPT4-train.txt`


Install [https://ollama.com/](ollama), start it (`ollama serve`) and download a model (e.g. `llama3`)

If you have a lot of time, run this:

`./resolve_multisynsets.py --progress --database tinystories.sqlite`

In reality, you will almost definitely need a cluster of machines to run this to finish in any
sensible length of time. If you have a cluster of 16 single CPU/gpu machines, then on the 3rd machine
you would run

`./resolve_multisynsets.py --database tinystories.sqlite --congruent 3 --modulo 16`

You can use a smaller model, e.g. `--model phi3`
