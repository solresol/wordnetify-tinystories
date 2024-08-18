#!/bin/bash

CONGRUENT=0
while ./resolve_multisynsets.py  --database TinyStories.sqlite --cong $CONGRUENT --modu 1000 --probe
do
    ./resolve_multisynsets.py  --database TinyStories.sqlite --cong $CONGRUENT --modu 1000 --progress-bar --use-groq
done
      
