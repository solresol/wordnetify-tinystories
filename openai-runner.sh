#!/bin/bash

cd /tinystories/wordnetify-tinystories
. .venv/bin/activate

python3 generate_multisynset_batch.py --database sample.sqlite \
	 --congruent 3 --modulo 1000 \
	 --output-file .batchfiles/batch-$(date +%F-%T).jsonl --limit 40000 --progress-bar \
	 --batch-id-save-file .batchid.txt && \
python3 batchcheck.py --database sample.sqlite  --only-batch $(< .batchid.txt) --monitor && \
python3 batchfetch.py --database sample.sqlite --progress-bar --report-costs
