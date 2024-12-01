#!/bin/bash

cd /tinystories/wordnetify-tinystories
if [ ! -d ".venv" ]; then
    echo "Virtual environment directory '.venv' does not exist. Creating it..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create the virtual environment."
        exit 1
    fi
fi

source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate the virtual environment."
    exit 1
fi

echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

python3 generate_multisynset_batch.py --database TinyStories.sqlite \
	 --congruent 3 --modulo 1000 \
	 --output-file .batchfiles/batch-$(date +%F-%T).jsonl --limit 40000 --progress-bar \
	 --batch-id-save-file .batchid.txt && \
python3 batchcheck.py --database TinyStories.sqlite  --only-batch $(< .batchid.txt) --monitor && \
python3 batchfetch.py --database TinyStories.sqlite --progress-bar --report-costs
