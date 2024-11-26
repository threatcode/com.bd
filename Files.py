import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
import asyncio
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BDKeywordScraper")

# Constants
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
BASE_URL = "https://www.google.com/search?q={keyword}+filetype:txt&start={page}"
HEADERS = {"User-Agent": USER_AGENT}
IGNORE_LINKS = []  # To avoid duplicates


def is_valid_bd_domain(url: str) -> bool:
    """
    Check if the URL is a valid `.com.bd` domain and exclude Google redirects or irrelevant links.
    """
    return re.search(r"https?://(www\.)?[^/]+\.com\.bd", url, re.IGNORECASE) is not None


async def fetch_urls(session: ClientSession, keyword: str, start_page: int):
    """
    Fetch search results from Google for the given keyword and page number.
    """
    url = BASE_URL.format(keyword=keyword, page=start_page)
    try:
        async with session.get(url, headers=HEADERS) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), "html.parser")
                links = []
                for link in soup.find_all("a", href=True):
                    match = re.search(r"url\?q=(http[s]?://.+?)&", link["href"])
                    if match:
                        target_url = match.group(1)
                        if is_valid_bd_domain(target_url) and target_url not in IGNORE_LINKS:
                            links.append(target_url)
                            IGNORE_LINKS.append(target_url)
                            logger.info(f"Valid .com.bd URL: {target_url}")
                        else:
                            logger.debug(f"Ignored URL: {target_url}")
                return links
            else:
                logger.warning(f"Failed to fetch {url} with status code {response.status}")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
    return []


async def scrape_com_bd_keywords(keywords: list, pages_per_keyword: int = 2):
    """
    Scrape .com.bd URLs for a list of keywords.
    """
    async with aiohttp.ClientSession() as session:
        for keyword in keywords:
            logger.info(f"Scraping for keyword: {keyword}")
            for page in range(0, pages_per_keyword * 10, 10):  # Google paginates in steps of 10
                urls = await fetch_urls(session, keyword, page)
                if urls:
                    logger.info(f"Found {len(urls)} URLs on page {page // 10 + 1} for '{keyword}'")


if __name__ == "__main__":
    # Define your keywords
    keywords = ["example.com.bd", "shop.com.bd", "teashop.com.bd"]

    # Start the scraping
    asyncio.run(scrape_com_bd_keywords(keywords))
