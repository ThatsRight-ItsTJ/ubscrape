import multiprocessing as mp
import json
from typing import List, Tuple

import requests

from .constants import BASE_URL
from .db import initialize_db

CON = initialize_db()


def define_word(word: str) -> str:
    if not word:
        raise ValueError('Must pass a word.')

    # Use the Urban Dictionary API instead of scraping HTML
    api_url = 'http://api.urbandictionary.com/v0/define'
    
    try:
        response = requests.get(api_url, params={'term': word})
        response.raise_for_status()
        
        data = response.json()
        definitions_list = data.get('list', [])
        
        if not definitions_list:
            return ""
        
        # Find the definition with the most thumbs up
        most_thumbs = -1
        best_definition = ""
        
        for definition in definitions_list:
            thumbs_up = definition.get('thumbs_up', 0)
            if thumbs_up > most_thumbs:
                most_thumbs = thumbs_up
                best_definition = definition.get('definition', '')
        
        return best_definition
        
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"Error fetching definition for '{word}': {e}")
        return ""

def write_definition(word_t: Tuple[str]) -> str:
    # word will always be a tuple when this function is called from define_all_words().
    # so in `cli.py`, we make word a tuple to match the type signature.
    word = word_t[0]

    # Note: this code will always make a network request.
    # If offline support for definitions was required, it
    # could check the local db for any definitions.
    definition: str = define_word(word)
    
    if definition:
        # Insert the single best definition
        CON.execute(
            'INSERT INTO definition(definition, word_id) VALUES (?, ?)', 
            (definition, word))
        CON.execute('UPDATE word SET complete = 1 WHERE word = ?', word_t)
        CON.commit()
    else:
        # Mark as complete even if no definition found to avoid retrying
        CON.execute('UPDATE word SET complete = 1 WHERE word = ?', word_t)
        CON.commit()



def define_all_words():
    pool = mp.Pool(mp.cpu_count())

    words = CON.execute(
        'SELECT word FROM word WHERE complete = 0').fetchall()

    pool.map(write_definition, words, chunksize=200)
