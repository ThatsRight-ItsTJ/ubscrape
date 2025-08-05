import multiprocessing as mp
from typing import List, Tuple, Optional

from bs4 import BeautifulSoup
import requests

from .constants import BASE_URL
from .db import initialize_db

CON = initialize_db()


def define_word(word: str) -> Optional[Tuple[str, int]]:
    """
    Get the definition with the most thumbs up for a given word.
    Returns a tuple of (definition, thumbs_up_count) or None if no definitions found.
    """
    if not word:
        raise ValueError('Must pass a word.')

    url = f'{BASE_URL}/define.php'

    req = requests.get(url, params={'term': word})

    soup = BeautifulSoup(req.text, features="html.parser")

    # Find all definition containers
    definition_containers = soup.find_all('div', {'class': 'definition'})
    
    if not definition_containers:
        return None
    
    best_definition = None
    max_thumbs_up = -1
    
    for container in definition_containers:
        # Get the definition text
        meaning_tag = container.find('div', {'class': 'meaning'})
        if not meaning_tag:
            continue
            
        definition_text = meaning_tag.get_text(strip=True)
        if not definition_text:
            continue
        
        # Get thumbs up count
        thumbs_up_element = container.find('a', {'class': 'up'})
        thumbs_up_count = 0
        
        if thumbs_up_element:
            # Extract the number from the thumbs up element
            thumbs_up_text = thumbs_up_element.get_text(strip=True)
            try:
                thumbs_up_count = int(thumbs_up_text)
            except (ValueError, TypeError):
                thumbs_up_count = 0
        
        # Keep track of the definition with the most thumbs up
        if thumbs_up_count > max_thumbs_up:
            max_thumbs_up = thumbs_up_count
            best_definition = definition_text
    
    if best_definition is not None:
        return (best_definition, max_thumbs_up)
    
    return None


def write_definition(word_t: Tuple[str]) -> Optional[Tuple[str, int]]:
    # word will always be a tuple when this function is called from define_all_words().
    # so in `cli.py`, we make word a tuple to match the type signature.
    word = word_t[0]

    # Note: this code will always make a network request.
    # If offline support for definitions was required, it
    # could check the local db for any definitions.
    result = define_word(word)
    
    if result is None:
        # Mark word as complete even if no definition found
        CON.execute('UPDATE word SET complete = 1 WHERE word = ?', word_t)
        CON.commit()
        return None
    
    definition, thumbs_up = result

    CON.executemany(
        'INSERT INTO definition(definition, word_id, thumbs_up) VALUES (?, ?, ?)', 
        [(definition, word, thumbs_up)])
    CON.execute('UPDATE word SET complete = 1 WHERE word = ?', word_t)
    CON.commit()

    return result


def define_all_words():
    pool = mp.Pool(mp.cpu_count())

    words = CON.execute(
        'SELECT word FROM word WHERE complete = 0').fetchall()

    pool.map(write_definition, words, chunksize=200)
