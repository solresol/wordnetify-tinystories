#!/bin/bash

cd /tinystories/wordnetify-tinystories
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip install -r requirements.txt

python3 generate_multisynset_batch.py --database TinyStories.sqlite \
	 --congruent 3 --modulo 1000 \
	 --output-file .batchfiles/batch-$(date +%F-%T).jsonl --limit 40000 --progress-bar \
	 --batch-id-save-file .batchid.txt && \
python3 batchcheck.py --database TinyStories.sqlite  --only-batch $(< .batchid.txt) --monitor && \
python3 batchfetch.py --database TinyStories.sqlite --progress-bar --report-costs
mkdir -p .batchfiles
python3 wordnetify.py --database TinyStories.sqlite --initialize-db
