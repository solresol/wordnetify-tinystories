import hashlib

def get_hypernym_path(synset):
    if synset.name() == 'entity.n.01':
        return [synset]

    hypernyms = sorted(synset.hypernyms())
    if not hypernyms:
        return [synset]

    shortest_path = None
    for hypernym in hypernyms:
        hypernym_path = get_hypernym_path(hypernym)
        if not hypernym_path:
            continue
        if not shortest_path:
            shortest_path = hypernym_path
            continue
        shortest_path = shortest_path if len(shortest_path) < len(hypernym_path) else hypernym_path

    return hypernym_path + [synset]

def hash_synset(synset):
    return hash_thing(synset.name())

def hash_thing(thing):
    return str(int(hashlib.sha256(thing.encode('utf-8')).hexdigest(),16) % (2**32))

# This takes a synset as an argument
def get_path_string(synset):
    # 1 = noun
    # 1.2 = pronoun
    # 1.3 = proper noun
    # 2 = adjective
    # 3 = verb
    # 4 = adverb
    # 5 = punctuation

    # Adjectives, we're kind of weak on. We just hash them.
    if synset.pos() in ['a', 's']:
        return f'2.{hash_synset(synset)}'

    if synset.pos() in ['r']:
        return f'4.{hash_synset(synset)}'

    if synset.pos() in ['n', 'v']:
        path = get_hypernym_path(synset)
        if not path:
            sys.exit(f"No path for {synset}")

        if synset.pos() == 'n':
            path_indices = ['1']  # Start with '1' for the nouns
        else:
            path_indices = ['3']
        path_indices.append(hash_synset(path[0]))
        for i in range(len(path) - 1):
            parent = path[i]
            child = path[i+1]
            hyponyms = sorted(parent.hyponyms(), key=lambda s: s.name())
            try:
                index = hyponyms.index(child) + 1
            except ValueError:
                # bug in wordnet: wn.synset('inhibit.v.04').hypernyms()[0].hyponyms() doesn't show inhibit.v.01
                if child.name() == 'inhibit.v.04':
                    index = 2
                else:
                    raise
            path_indices.append(str(index))

        return '.'.join(path_indices)




def is_enumerated_pseudo_synset(pseudo_synset):
    return pseudo_synset in {
        "(pronoun.other)",
        "(punctuation.other)",
        "(conjunction.other)",
        "(article.other)"
        }

hashed_pseudo_synset_prefix = {
    '(noun.other)': '1.',
    '(verb.other)': '3.',
    '(propernoun.other)': '1.3.',
    '(preposition.other)': '6.',
    '(adjective.other)': '2.',
    '(adverb.other)': '4.',
    '(other.other)': '8.'
}
