# wordnetify-tinystories

Takes a TinyStories file and converts each word to a wordnet node.

# Usage

## Setup and Download

Set up a virtualenv and install dependencies.

`virtualenv .venv`

`. .venv/bin/activate`

`pip install -r requirements.txt`


Then install the NLTK data:

	nltk.download('punkt')
	nltk.download('punkt_tab')
	nltk.download('wordnet')
	nltk.download('punkt_tab')

Download `TinyStoriesV2-GPT4-train.txt` and `TinyStoriesV2-GPT4-valid.txt`

## Run wordnetify 

Run:

`./wordnetify.py --database tinystories.sqlite --progress --file TinyStoriesV2-GPT4-valid.txt`

Make a note of how long that took, because the next command will take 100x longer:

`./wordnetify.py --database tinystories.sqlite --progress --file TinyStoriesV2-GPT4-train.txt`

## Resolve synsets

### Option 1 for resolving synsets (don't use this)

Install [https://ollama.com/](ollama), start it (`ollama serve`) and download a model (e.g. `llama3`)

If you have a lot of time, run this:

`./resolve_multisynsets.py --progress --database tinystories.sqlite`

In reality, you will almost definitely need a cluster of machines to run this to finish in any
sensible length of time. If you have a cluster of 16 single CPU/gpu machines, then on the 3rd machine
you would run

`./resolve_multisynsets.py --database tinystories.sqlite --congruent 3 --modulo 16`

You can use a smaller model, e.g. `--model phi3`
	nltk.download('punkt_tab')

That might complete if you have a few months to run it.

### Option 2 (don't use this either)

`./resolve_multisynsets.py` can use groq. You'll need to give it a groq key.
It's faster, but not fast enough. (And not cheap enough.)

### Option 3

Set up an OpenAI API key. You can supply it on the command-line, or else it
will default to ~/.openai.key. Note that the `--output-file` argument is mandatory and should specify a valid file path where the batch file will be saved.

	./generate_multisynset_batch.py --database TinyStories.sqlite \
		--congruent 3 --modulo 1000 \
		--output-file /path/to/output/batch-$(date +%F-%T).jsonl \
		--limit 40000 --progress-bar \
		--batch-id-save-file .batchid.txt
		
That will take every thousandth story (which is about what we want). The output
file doesn't really matter, but it's nice to be able to keep them. 
OpenAI doesn't like to have more than 40,000 records in one job. Having the
ID of the batch is convenient.

	./batchcheck.py --database TinyStories.sqlite  \
		--only-batch $(< .batchid.txt) --monitor
		
That will keep track of it that batch, show how it is progressing, and stop
when it is complete.

	./batchfetch.py --database TinyStories.sqlite \
		--progress-bar --report-costs

This stores the results back in the database.

40,000 records takes about 100 minutes, and costs about $1.75.

## Create wordnet database with extras

`./make_wordnet_database.py --database TinyStories.sqlite`

- proper nouns and other parts of speech... at the moment, the path is a hash of the word.
  Perhaps a soundex of the word would be better, and then the hash?


# Next steps

Compile the ultrametric-trees programs, to convert the Tiny Stories sentences
into a giant dataframe of wordnet paths.
