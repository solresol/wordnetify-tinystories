#!/usr/bin/env python3

import argparse
import nltk

def read_file_in_chunks(file_path, delimiter="<|endoftext|>"):
    """Read a file and yield chunks of text separated by a specific delimiter."""
    chunk = []
    with open(file_path, 'r') as file:
        for line in file:
            if line.strip() == delimiter:
                yield ''.join(chunk)
                chunk = []
            else:
                chunk.append(line)
        if chunk:
            yield ''.join(chunk)



def main():
    parser = argparse.ArgumentParser(description="Read a file in chunks separated by a delimiter.")
    parser.add_argument("file", type=str, help="The path to the file to be read.")
    parser.add_argument("--delimiter", type=str, default="<|endoftext|>", help="The delimiter to separate chunks. Default is newline.")

    args = parser.parse_args()

    non_wordnet = {}
    lookup_required = []
    total_words_seen = 0
    easy_cases = 0
    for chunk in read_file_in_chunks(args.file, args.delimiter):
        for sentence in nltk.sent_tokenize(chunk):
            this_sentence_parses = 0
            this_sentence_nonwordnet = 0
            for i, word in enumerate(nltk.word_tokenize(sentence)):
                total_words_seen += 1
                synsets =  nltk.corpus.wordnet.synsets(word)
                if len(synsets) == 1:
                    #print(f"{synsets[0]} (WordNet entry found)")
                    easy_cases += 1
                    pass
                elif len(synsets) > 2:
                    lookup_required.append((i,word,sentence))
                    this_sentence_parses += 1                    
                else:
                    non_wordnet[word] = 1 if word not in non_wordnet else non_wordnet[word]+1
                    this_sentence_nonwordnet += 1
            #print(f"\r{sentence[:60]}               {this_sentence_parses=} {this_sentence_nonwordnet=}    ", end='', flush=True)
            
            print(f"\r  {total_words_seen=} {len(lookup_required)=} {len(lookup_required)/total_words_seen=:.3f}   {len(non_wordnet)=} {easy_cases/total_words_seen=:.3f}  ", end='', flush=True)

if __name__ == "__main__":
    main()
