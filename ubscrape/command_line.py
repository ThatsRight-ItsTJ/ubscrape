import os
import argparse

from .definitions import define_all_words, write_definition
from .words import write_all_words
from .db import clear_database, dump_database, get_connection, DB_FILE_NAME
from .constants import VERSION


def check_existing_database():
    """Check if database exists and report current state"""
    if os.path.exists(DB_FILE_NAME):
        con = get_connection()
        
        # Count total words and completed words
        total_words = con.execute('SELECT COUNT(*) FROM word').fetchone()[0]
        completed_words = con.execute('SELECT COUNT(*) FROM word WHERE complete = 1').fetchone()[0]
        incomplete_words = total_words - completed_words
        
        # Count words by letter to show progress
        letter_progress = con.execute('''
            SELECT letter, 
                   COUNT(*) as total, 
                   SUM(complete) as completed,
                   MAX(page_num) as last_page
            FROM word 
            GROUP BY letter 
            ORDER BY letter
        ''').fetchall()
        
        print(f'Found existing database with {total_words} words total')
        print(f'  - {completed_words} words defined')
        print(f'  - {incomplete_words} words still need definitions')
        print('\nProgress by letter:')
        
        for letter, total, completed, last_page in letter_progress:
            completion_rate = (completed / total * 100) if total > 0 else 0
            print(f'  {letter}: {completed}/{total} words ({completion_rate:.1f}%) - last page: {last_page}')
        
        print('\nScraping will resume from where it left off...\n')
        return True
    else:
        print('No existing database found. Starting fresh scrape...\n')
        return False


def report_progress():
    con = get_connection()

    count: int = con.execute(
        'SELECT COUNT(word) FROM word WHERE complete = 1').fetchone()[0]
    total: int = con.execute('SELECT COUNT(word) FROM word').fetchone()[0]

    seconds_remaining = (total - count) / 10
    hours_remaining = seconds_remaining / 60 / 60
    days_remaining = hours_remaining / 24

    print(f'{count} defined out of {total} total words.')
    if total:
        print(f'{(count / total * 100):.2f}% complete.')
        print(
            f'At roughly 10 words/second, it will take {hours_remaining:.1f} hours, or {days_remaining:.1f} days.')


def scrape():
    check_existing_database()
    write_all_words()
    define_all_words()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s",
                        "--scrape",
                        help="Continues scraping Urban Dictionary using the SQLite database as its starting point.",
                        action="store_true")

    parser.add_argument("-v",
                        "--version",
                        help="Shows version number.",
                        action="store_true")

    parser.add_argument('-d',
                        '--dump',
                        action='store_true',
                        help="Dumps the SQLite database to .json files.")

    parser.add_argument('-o',
                        '--out',
                        dest='dump',
                        help="Specifies the directory for --dump.")

    parser.add_argument("--define",
                        help="Look up a particular word and define it.")

    parser.add_argument("--define-all",
                        help="Define all words currently stored in SQLite that are not defined.",
                        action="store_true")

    parser.add_argument("-c",
                        "--clear",
                        help="Clears the existing SQLite database.",
                        action="store_true")

    parser.add_argument("--tsv",
                        action='store_true',
                        help="Dumps the SQLite database to .tsv files.")

    parser.add_argument("-r",
                        "--report",
                        help="Shows the progress of defining words.",
                        action="store_true")

    parser.add_argument("-f",
                        "--force",
                        help="Forces the SQLite database to be cleared.",
                        action="store_true")

    args = parser.parse_args()

    if args.version:
        print(f'Version {VERSION}')

    if args.report:
        report_progress()

    if args.scrape:
        scrape()
    elif args.dump:
        dump_database(args.dump)
    elif args.tsv:
        dump_database(args.dump, csv=True)
    elif args.define:
        result = write_definition((args.define,))
        if result:
            definition, thumbs_up = result
            print(f"Definition: {definition}")
            print(f"Thumbs up: {thumbs_up}")
        else:
            print("No definition found.")
    elif args.define_all:
        define_all_words()
    elif args.clear:
        if args.force:
            clear_database()
        else:
            print(
                "Use --clear [-c] with --force [-f] to COMPLETELY DELETE the SQLite database.")
    elif not args.report and not args.version:
        print('No arguments detected. Continuing to scrape.')
        check_existing_database()
        scrape()


if __name__ == "__main__":
    main()
