#!/bin/bash

cd /tinystories/wordnetify-tinystories
. .venv/bin/activate

output_file=".batchfiles/batch-$(date +%F-%T).jsonl"

python3 generate_multisynset_batch.py --database TinyStories.sqlite \
	 --congruent 3 --modulo 1000 \
	 --output-file $output_file --limit 40000 --progress-bar \
	 --batch-id-save-file .batchid.txt && \
python3 batchcheck.py --database TinyStories.sqlite  --only-batch $(< .batchid.txt) --monitor && \
python3 batchfetch.py --database TinyStories.sqlite --progress-bar --report-costs
