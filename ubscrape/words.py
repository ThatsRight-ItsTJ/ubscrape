# internal to python
import re
from urllib.parse import unquote
from string import ascii_uppercase
from sqlite3 import IntegrityError
from typing import List, Tuple

# external
import requests
from bs4 import BeautifulSoup


from .constants import BASE_URL
from .db import initialize_db

CON = initialize_db()


def write_words_for_letter(prefix: str):
    if not prefix:
        raise ValueError(f'Prefix {prefix} needs to be at least one letter.')

    def make_url():
        if page_num > 1:
            return f'{BASE_URL}/browse.php?character={letter}&page={page_num}'
        return f'{BASE_URL}/browse.php?character={letter}'

    letter = prefix.upper()

    # Check if we have any existing data for this letter
    existing_page = CON.execute(
        'SELECT max(page_num) FROM word WHERE letter = ?', (letter,)).fetchone()[0]

    if not existing_page:
        page_num = 1
        print(f'Starting fresh scraping for letter {letter}')
    else:
        # Resume from the last page we were working on
        page_num = existing_page
        print(f'Resuming scraping for letter {letter} from page {page_num}')

    url = make_url()
    req = requests.get(url)

    while req.url != 'https://www.urbandictionary.com/' and req.status_code == 200:
        soup = BeautifulSoup(req.text, features="html.parser")
        a_tags = soup.find_all('a', href=re.compile(r'/define.php'))

        # If no definition links found, we've reached the end
        if not a_tags:
            print(f'No more words found for letter {letter}. Finished at page {page_num - 1}.')
            break

        pattern = re.compile(
            r'\/define\.php\?term=(.*)')

        links = [l['href'] for l in a_tags]

        encoded_words: List[str] = [pattern.search(l).group(1)
                                    for l in links if pattern.search(l)]

        words: List[str] = [unquote(w) for w in encoded_words]

        formatted_words: List[Tuple[str, int, int, str]] = [
            (w, 0, page_num, letter) for w in words]

        try:
            CON.executemany(
                'INSERT INTO word(word, complete, page_num, letter) VALUES (?, ?, ?, ?)',
                formatted_words)
            CON.commit()
        except IntegrityError:
            # IntegrityError normally occurs when we try to
            # insert words that are already in the database.
            pass

        print(
            f'Working on page {page_num} for {letter}. Total {140 * (page_num - 1) + len(words)} {letter} words.')

        page_num += 1
        url = make_url()
        req = requests.get(url)
        
        # Additional safety check - if we get redirected or error, stop
        if req.status_code != 200:
            print(f'Received status code {req.status_code} for letter {letter} page {page_num}. Stopping.')
            break


def write_all_words():
    for letter in ascii_uppercase + '*':
        write_words_for_letter(letter)
