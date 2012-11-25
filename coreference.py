import os
from pprint import pprint as pp
import sys, nltk, re
import xml.sax.saxutils as saxutils

'''
Coreference Resolution
Created on Oct 25, 2012

# REQUIRED NLTK PACKAGES:
# punkt
# maxent_treebank_pos_tagger

@author: John Wells
@author: Joel Hough

'''
class Memoize:
    def __init__(self, f):
        self.f = f
        self.memo = {}
    def __call__(self, *args):
        if not args in self.memo:
            self.memo[args] = self.f(*args)
        return self.memo[args]

sentence_tokenizer = nltk.data.load('tokenizers/punkt/english.pickle')
word_tokenizer = nltk.tokenize.punkt.PunktWordTokenizer()
lemmatizer = nltk.WordNetLemmatizer()
tagger = nltk.RegexpTagger([(r'.*coref_tag_beg_.*', 'CRB'), 
                            (r'.*coref_tag_end_.*', 'CRE'),
                            (r'\$[0-9]+(.[0-9]+)?', 'NN')], backoff=nltk.data.load('taggers/maxent_treebank_pos_tagger/english.pickle'))
names = nltk.corpus.names
coref_tag_re = r'(?is)<COREF ID="(\w+)">(.*?)</COREF>'
coref_token_re = r'(?is)coref_tag_beg_(\w+)_(.*?)coref_tag_end_\1_'
chunker_grammar = r"""
NP:
{<CRB>(<.*>+?)<CRE>}
{<DT|PP\$>?<JJ>*<NN.*>+} # chunk determiner/possessive, adjectives and nouns
{<WP.*>}
{<PRP.*>}
"""
chunker = nltk.RegexpParser(chunker_grammar)

def chunk(sentence):
    return chunker.parse(sentence)

@Memoize
def lemmatize(word):
    return lemmatizer.lemmatize(word)

def pos_tag(text):
    return tagger.tag(text)

def word_tokenize(text):
    return word_tokenizer.tokenize(text)

def sentence_tokenize(text, no_break_zones=[]):
    spans = sentence_tokenizer.span_tokenize(text)
    return sentence_tokenizer._realign_boundaries(text[slice(start, end)] for start, end in adjust_spans(spans, no_break_zones))

def adjust_spans(spans, no_break_zones):
    def valid_break(pos):
        #print list(no_break_zones)
        for start, end in no_break_zones:
            if pos >= start and pos <= end:
                return False
        return True
    
    new_start = -1
    for start, end in spans:
        if new_start == -1:
            new_start = start
        if valid_break(end):
            yield (new_start, end)
            new_start = -1

def get_anaphora(text):
    """
    Get a list of information about anaphora in the given text
    @param text: text with anaphors marked with coref_tag_* tokens.
    """
    return [{'ID':m.groups()[0],
             'value':m.groups()[1],
             'position': m.start()} for m in re.finditer(coref_token_re, text)]

def pronoun_matcher(potential_antecedent, anaphor):
    sentence = anaphor['sentence']
#    print potential_antecedent['value'], sentence
    global names
#    t = chunker.parse(sentences)
    a = [(a[0]) for a in anaphor['value'] if 'PRP' in a[1]]
    if a: # If there exists a pronoun.
        for u in reversed(sentence):
            try:
                if u.node == 'NP': #If we have an NP, check gender/number agreement.
                    # Male pronoun agreement. Returns first agreement found.
                    if a[0] in ['he', 'his', 'him']:
                        male = [n for n in names.words('male.txt') if n in ''.join([_u[0] for _u in u])]
                        if male:
                            return ' '.join([_u[0] for _u in u.leaves() if 'NNP' in _u])
                    # Female pronoun agreement. Returns first agreement found.
                    elif a[0] in ['she', 'hers', 'her']:
                        female = [n for n in names.words('female.txt') if n in ''.join([_u[0] for _u in u])]
                        if female:
                            return ' '.join([_u[0] for _u in u.leaves() if 'NNP' in _u])
                    elif a[0] in ['it', 'its', 'itself']:
                        neuter = [_u[0] for _u in u.leaves() if 'NNP' not in _u]
                        if neuter:
                            return ' '.join(neuter)               
            except AttributeError:
                continue

def is_appositive(potential_antecedent, anaphor):
    
    try:
        sentence = anaphor['sentence']
        #If the chunk prior to the anaphor location is a NP, verify that it also contains a comma.
        #        print anaphor
        if sentence[-1].node == 'NP': # Probably should check the anaphor to ensure that is in fact a NP as well.
            appos = [ap for ap in sentence[-1].leaves() if ',' in ap[0]]
            if appos:
                return True
        else:
            return False
    except AttributeError:
        return False
    except KeyError:
        return False

def linguistic_form(anaphor):
    """
    Returns the form of the potential anaphor NP_j.
    @param anaphor: Targeted potential anaphor of known antecedent. 
    @return form: [proper_name, definite_description, indefinite_NP, pronoun]
    """ 
    pass

def hobbs_algorithm():
    """
    1. Begin at the NP mode immediately dominating the pronoun.
    2. Go up the tree to the first NP or S node encountered. Call this node X and call the path used to reach it P.
    3. Traverse all branches below node X to the left of path p in a left-to-right BFS fashion. Propose as the antecedent any encountered NP node that has an NP or S node between it and X.
    4. If node X is the highest S node in the sentence, traverse the surface parse trees of previous sentences in the text in order of recency, most recent first. 
        Each tree is traversed in a left-to-right BFS and when an NP node is encountered it is proposed as antecedent. 
        If X is not the highest S node in the sentence, continue to step 5.
    5. From node X, go up the tree to the first NP or S node encountered. Call this new node X and the path traversed to reach it P.
    6. If X is an NP node and if the path P to X did not pass through the Nominal node that X immediately dominates, propose X as the antecedent.
    7. Traverse all branches below node X to the left of path P in a left to right BFS. Propose any NP node encountered as the antecedent.
    8. If X is an S node, traverse all branches of node X to the right of path P in a left-to-right BFS, but do not go below any NP or S node encountered. Propose any NP node encountered as the antecedent.
    9. Go to step 4.
    """
    pass

def centering_algorithm():
    """
    Reference: Centering theory, entity-based coherence. Page 706.
    
    RULES: 
        1. If any element of Cf(Un) is realized by a pronoun in utterance Un+1 then Cb(Un+1) must be realized as a pronoun also.
        2. Transition states are ordered. Continue is preferred to Retain is preferred to Smooth-Shift is preferred to Rough-Shift.
        
    Algorithm:
        1. Generate possible (Cb,Cf) combinations for each possible set of reference assignments.
        2. Filter by constraints. For example, syntactic coreference constraints, selectional restrictions, centering rules, and constraints.
        3. Rank by transition orderings.
    """
    pass
   
def each_with_tail(seq):
    i = 0
    l = list(seq)
    while (l[i:]):
        i += 1
        yield (l[i - 1], l[i:])

def any_word_matches_p(anaphor, potential_antecedent):
    return any(word for word in anaphor['value'].split() if lemmatize(word.lower()) in map(lambda w: lemmatize(w.lower()), potential_antecedent['value'].split()))

def sentence_distance(anaphor, potential_antecedent):
    return anaphor['position'][0] - potential_antecedent['position'][0]

def distance(anaphor, potential_antecedent):
    a_sent, a_phrase = anaphor['position']
    b_sent, b_phrase = potential_antecedent['position']
    return (a_sent - b_sent, a_phrase - b_phrase)

def features(anaphor, potential_antecedent):
    return {
        'REF': potential_antecedent['ID'],
        'word_match': any_word_matches_p(anaphor, potential_antecedent),
        'sentence_distance': sentence_distance(anaphor, potential_antecedent),
        'distance': distance(anaphor, potential_antecedent),
        'is_appositive' : is_appositive(potential_antecedent, anaphor),
#        'pronoun' : pronoun_matcher(potential_antecedent, anaphor)
        }

def coreferent_pairs_features(corefs):
    refs = dict()
    for coref, potential_antecedents in each_with_tail(sorted(corefs, key=lambda a:a['position'], reverse=True)):
        if not coref['is_anaphor']:
            continue
        refs[coref['ID']] = [features(coref, potential_antecedent) for potential_antecedent in potential_antecedents]
    return refs

def feature_resolver(corefs):
    features = coreferent_pairs_features(corefs)
    for id in features:
        matches = filter(lambda f: f['word_match'], features[id])
        if matches:
            yield {'ID': id, 'REF': min(matches, key=lambda f: f['distance'])['REF']}

def update_refs(text, refs):
    """
    Given a list of Tagged Anaphora and antecedents, and an original input file, create a tagged output file.
    """
    new_text = text
    for ref in refs:
        new_text = new_text.replace('<COREF ID="{0[ID]}">'.format(ref), '<COREF ID="{0[ID]}" REF="{0[REF]}">'.format(ref))

    return new_text

def replace_coref_tags_with_tokens(text):
    return re.sub(coref_tag_re, r' coref_tag_beg_\1_ \2 coref_tag_end_\1_ ', text)

def replace_coref_tokens_with_tags(text):
    return re.sub(coref_token_re, r'<COREF ID="\1">\2</COREF>', text)

def no_break_zones(text):
    return [match.span() for match in re.finditer(coref_token_re, text)]

def coref_abbrs(text):
    return [word 
            for match in re.finditer(coref_token_re, text)
            for word in word_tokenize(match.groups()[1])
            if word[-1] == '.']

def read_text(file):
    return open(file, 'r').read()

def filename(file):
    return os.path.splitext(os.path.basename(file))[0]

def teach_abbreviations_to_tokenizer(abbrs):
    global sentence_tokenizer
    sentence_tokenizer._params.abbrev_types |= set(abbrs)

def get_text_from_files(files):
    to_resolve = []
    for file in files:
        name = filename(file)
        text = read_text(file)
        to_resolve.append((name, text))
    return to_resolve

class Gensym:
    i = 0
    def reset(self):
        self.i = 0

    def __call__(self):
        self.i += 1
        return 'X{0}'.format(self.i)

def resolve_files(files, response_dir_path):
    gensym = Gensym()
    def write_response(name, text):
        output_path = os.path.join(response_dir_path, name + '.response')
        open(output_path, 'w').write(text)

    def untagged_phrase(tagged_tokens):
        return ' '.join(word for word, tag in tagged_tokens)

    def tag_as_new_coref(noun_phrase):
        def surround_with_coref_tokens(tokens, ident):
            tokens.insert(0, ('coref_tag_beg_{0}_'.format(ident), 'CRB'))
            tokens.append(('coref_tag_end_{0}_'.format(ident), 'CRE'))
            
        def move_last_period_out_of_coref_tag(tokens):
            tag = tokens[-1]
            last_word = tokens[-2]
            if last_word[0][-1] == '.':
                tokens[-2] = (last_word[0][:-1], last_word[1])
                tokens[-1] = (tag[0] + '.', tag[1])

        surround_with_coref_tokens(noun_phrase, gensym())
        #move_last_period_out_of_coref_tag(noun_phrase)

    def is_anaphor(tokens):
        word, tag = tokens[0]
        return tag == 'CRB'

    def coref_from_noun_phrase(noun_phrase):
        def phrase_without_coref_tokens(noun_phrase):
            return noun_phrase[1:-1]

        def get_id(tokens):
            word, tag = tokens[0]
            return re.match(r'coref_tag_beg_(\w+)_', word).group(1)

        tagged_value = phrase_without_coref_tokens(noun_phrase)

        return {
            'ID': get_id(noun_phrase),
            'value': untagged_phrase(tagged_value),
            'tagged_value': tagged_value
            }
    
    def add_coref_data(coref, data):
        coref.update(data)

    documents_to_resolve = []
    for name, text in get_text_from_files(files):
        detagged_text = text
        detagged_text = re.sub(r'(?is)</?TXT>', '', detagged_text)
        detagged_text = replace_coref_tags_with_tokens(detagged_text)
        detagged_text = saxutils.unescape(detagged_text)
        documents_to_resolve.append((name, detagged_text))

    for _, text in documents_to_resolve:
        teach_abbreviations_to_tokenizer(coref_abbrs(text))
        
    for document_name, text in documents_to_resolve:
        gensym.reset()
        corefs = []
        np_tagged_sentences = []
        sentences = sentence_tokenize(text, no_break_zones(text))
        for i_sentence, sentence in enumerate(sentences):
            #            print sentence
            tokenized_sentence = word_tokenize(sentence)
            tagged_sentence = pos_tag(tokenized_sentence)
            #if 'we' in tokenized_sentence:
            #    print tagged_sentence
            chunked_sentence = chunk(tagged_sentence)
            
            for i_noun_phrase, noun_phrase in enumerate(chunked_sentence.subtrees(filter=lambda s: s.node == 'NP')):
                #                print noun_phrase
                was_an_anaphor = is_anaphor(noun_phrase)
                if not was_an_anaphor:
                    tag_as_new_coref(noun_phrase)
                    
                coref = coref_from_noun_phrase(noun_phrase)
                
                add_coref_data(coref, {
                    'is_anaphor': was_an_anaphor,
                    'position': (i_sentence, i_noun_phrase),
                    'tokenized_sentence': tokenized_sentence,
                    'tagged_sentence': tagged_sentence,
                    'chunked_sentence': chunked_sentence,
                    'sentence': sentence
                })
                corefs.append(coref)
            np_tagged_sentences.append(untagged_phrase(chunked_sentence.leaves()))

        tagged_text = "\n".join(np_tagged_sentences)
        tagged_text = saxutils.escape(tagged_text)
        tagged_text = replace_coref_tokens_with_tags(tagged_text)
        tagged_text = '<TXT>' + tagged_text + '</TXT>\n'
        refs = feature_resolver(corefs)
        resolved_text = update_refs(tagged_text, refs)
        
        write_response(document_name, resolved_text)
        
#===============================================================================
# Main
#===============================================================================
def main():
    listfile_path = sys.argv[1]
    response_dir_path = sys.argv[2]

    files = [l.strip() for l in open(listfile_path, 'r').readlines()]

    resolve_files(files, response_dir_path)

if __name__ == '__main__':
    main()
    #cProfile.run('main()')



