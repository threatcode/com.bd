import os
import csv
import asyncio
import re
import string
import logging
from user_agent import generate_user_agent
from aiohttp import ClientSession
from bs4 import BeautifulSoup

# Constants
WORDS = []
IGNORE_WORDS = []
IGNORE_LINKS = []
PROCESSED = []

FORMATS = ["txt"]
MAX_WORDS = 50
SAVE_INTERVAL = 10  # Save interval for WordList.txt

KEYS = {
    "WordList.txt": WORDS,
    "IgnoreWords.txt": IGNORE_WORDS,
}

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("INDEXER")

# Load initial word lists
for key, storage in KEYS.items():
    if os.path.exists(key):
        with open(key, "r") as f:
            storage.extend(f.read().splitlines())

def save_wordlist():
    """
    Save the WORDS list to WordList.txt.
    """
    with open("WordList.txt", "w") as f:
        f.write("\n".join(sorted(set(WORDS))))


def generate_com_bd_keywords(base_keywords):
    """
    Generate .com.bd-related keywords from a base list.
    """
    generated_keywords = []
    for base in base_keywords:
        generated_keywords.append(base + ".com.bd")
        generated_keywords.append("www." + base + ".com.bd")
    return generated_keywords


def judge_content(text: str) -> bool:
    """
    Ensure the content matches `.com.bd` and is valid.
    """
    return ".com.bd" in text.lower()


async def fetch_com_bd_words(base_keywords):
    """
    Generate new `.com.bd` words based on existing base keywords.
    """
    new_keywords = generate_com_bd_keywords(base_keywords)
    for keyword in new_keywords:
        if keyword not in WORDS and keyword not in IGNORE_WORDS:
            WORDS.append(keyword)
            logger.info(f"Generated keyword: {keyword}")


async def fetch_files(word: str):
    """
    Fetch .com.bd-related files.
    """
    if len(PROCESSED) >= MAX_WORDS:
        raise Exception("Maximum word limit reached.")
    if word in IGNORE_WORDS:
        return
    logger.info(f"--> Fetching for word: {word}")
    IGNORE_WORDS.append(word)

    folder = word[0].upper()
    os.makedirs(folder, exist_ok=True)

    async with ClientSession() as session:

        async def fetch_by_format(filetype):
            """
            Fetch results for a specific file type.
            """
            search_url = f"https://google.com/search?q={word}+filetype:{filetype}"
            try:
                async with session.get(
                    search_url,
                    headers={"User-Agent": generate_user_agent()},
                ) as response:
                    soup = BeautifulSoup(await response.text(), "html.parser")
                    for link in soup.find_all("a", href=True):
                        url = link["href"]
                        if judge_content(url):
                            if url not in IGNORE_LINKS:
                                IGNORE_LINKS.append(url)
                                logger.info(f"Found URL: {url}")
            except Exception as e:
                logger.error(f"Error fetching {word}: {e}")

        tasks = [fetch_by_format(ft) for ft in FORMATS]
        await asyncio.gather(*tasks)

    PROCESSED.append(word)
    if word in WORDS:
        WORDS.remove(word)


async def main():
    """
    Main function to coordinate tasks.
    """
    logger.info("> Starting program...")
    base_keywords = ["example", "shop", "business"]  # Define base keywords
    await fetch_com_bd_words(base_keywords)

    while WORDS:
        tasks = [fetch_files(word) for word in WORDS[:3]]
        await asyncio.gather(*tasks)
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
    finally:
        save_wordlist()
