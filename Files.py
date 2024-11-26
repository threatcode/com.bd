import os
import csv
import asyncio
import random
import re
import string
import logging
from user_agent import generate_user_agent
from aiohttp import ClientSession, ClientError
from bs4 import BeautifulSoup

# Constants
WORDS = []
IGNORE_WORDS = []
IGNORE_LINKS = []
PROCESSED = []

FORMATS = ["sql", "txt"]
RANDOM_WORDS_COUNT = 35
MAX_WORDS = 50
SAVE_INTERVAL = 10  # Interval to save the word list (in seconds)

KEYS = {
    "WordList.txt": WORDS,
    "IgnoreWords.txt": IGNORE_WORDS,
}

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("INDEXER")

# Compatibility for Windows
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load initial words
for key, storage in KEYS.items():
    if os.path.exists(key):
        with open(key, "r") as f:
            storage.extend(f.read().splitlines())
        if key == "WordList.txt":
            os.remove(key)


def save_wordlist():
    """
    Save the current WORDS list to WordList.txt, avoiding duplicates.
    """
    if WORDS:
        with open("WordList.txt", "w") as f:
            f.write("\n".join(sorted(set(WORDS))))


async def auto_save_wordlist():
    """
    Periodically save the WORDS list to WordList.txt.
    """
    while True:
        save_wordlist()
        await asyncio.sleep(SAVE_INTERVAL)


def judge_content(text: str) -> bool:
    """
    Check if text contains reversed banned keywords.
    """
    banned_keywords = ["xes", "nrop", "soedivx"]
    return not any(word[::-1] in text.lower() for word in banned_keywords)


async def get_random_words_from_api():
    """
    Fetch random words from an API.
    """
    api_url = "https://random-word-api.vercel.app/api?words"
    async with ClientSession() as session:
        for _ in range(RANDOM_WORDS_COUNT):
            try:
                async with session.get(api_url) as response:
                    response.raise_for_status()
                    word = (await response.json())[0]
                if word not in WORDS and word not in IGNORE_WORDS:
                    WORDS.append(word)
                    logger.info(f"Added random word: {word}")
            except ClientError as e:
                logger.error(f"Failed to fetch random words: {e}")


def save_files(content, path=""):
    """
    Save content into CSV files by file type.
    """
    os.makedirs(path, exist_ok=True)
    for filetype, entries in content.items():
        with open(f"{path}/{filetype.upper()}_files.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(entries)


async def fetch_files(word: str):
    """
    Fetch files for a given word from Google search results.
    """
    if len(PROCESSED) >= MAX_WORDS:
        raise Exception("Maximum word limit reached.")
    if word in IGNORE_WORDS:
        return
    logger.info(f"--> Fetching for word: {word}")
    IGNORE_WORDS.append(word)
    content = {}
    folder = word[0].upper()
    os.makedirs(folder, exist_ok=True)

    async with ClientSession() as session:

        async def fetch_by_format(filetype):
            """
            Fetch results for a specific file type.
            """
            search_url = f"https://google.com/search?q={word}+filetype:{filetype}"
            results = []
            start = 0

            while len(results) < 10:
                try:
                    async with session.get(
                        search_url + f"&start={start}",
                        headers={"User-Agent": generate_user_agent()},
                    ) as response:
                        response.raise_for_status()
                        soup = BeautifulSoup(await response.text(), "html.parser")
                        results = soup.find_all("div", class_=re.compile("egMi0"))
                except ClientError as e:
                    logger.error(f"Failed to fetch results: {e}")
                    break

                for result in results:
                    try:
                        name = result.find("div", class_=re.compile("vvjwJb")).text
                        link = result.find("a", href=re.compile("/url?"))
                        link = (
                            link["href"]
                            .split("url=")[1]
                            .split("&")[0]
                            .strip()
                        )
                        if judge_content(link) and judge_content(name) and link not in IGNORE_LINKS:
                            content.setdefault(filetype, []).append([name, link])
                            IGNORE_LINKS.append(link)
                            logger.info(f"--> Found link: {link}")
                    except Exception as e:
                        logger.error(f"Error processing result: {e}")
                start += 10

        tasks = [fetch_by_format(ft) for ft in FORMATS]
        await asyncio.gather(*tasks)

    PROCESSED.append(word)
    if word in WORDS:
        WORDS.remove(word)
    if content:
        subfolder = os.path.join(folder, word[1:])
        save_files(content, path=subfolder)


async def main():
    """
    Main async function to coordinate tasks.
    """
    logger.info("> Starting program...")
    await get_random_words_from_api()

    semaphore = asyncio.Semaphore(3)  # Limit simultaneous tasks

    async def worker(word):
        async with semaphore:
            await fetch_files(word)

    auto_save_task = asyncio.create_task(auto_save_wordlist())

    try:
        while WORDS:
            tasks = [worker(word) for word in WORDS[:3]]
            await asyncio.gather(*tasks)
            await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Exception: {e}")
    finally:
        auto_save_task.cancel()
        save_wordlist()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
    finally:
        save_wordlist()
