import time
import logging
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Low-cardinality logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s"
)


class BaseScraper(ABC):
    # Required schema: fields every article must have
    REQUIRED_FIELDS = ["title", "content", "url", "source"]

    def __init__(
        self,
        source_name: str,
        base_url: str,
        rate_limit_seconds: float = 2.0,
        max_retries: int = 3,
        timeout: int = 15,
    ):
        self.source_name = source_name
        self.base_url = base_url
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = logging.getLogger(source_name)

        # Reusable HTTP session with realistic browser headers
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8,fr;q=0.7",
        })

    # -------------------------------------------------------
    # Abstract methods — each concrete scraper implements these
    # -------------------------------------------------------

    @abstractmethod
    def get_article_urls(self) -> list[str]:
        pass

    @abstractmethod
    def parse_article(self, url: str, soup: BeautifulSoup) -> Optional[dict]:
        pass

    # -------------------------------------------------------
    # Main scraping engine
    # -------------------------------------------------------

    def scrape_all(self) -> list[dict]:
        """
        Runs the full cycle: fetch URLs → parse each one → validate.
        Returns the list of valid articles.
        """
        self.logger.info("Starting scraping")
        articles = []

        # Step 1: get list of URLs
        try:
            urls = self.get_article_urls()
            self.logger.info("URLs found: %d", len(urls))
        except Exception as error:
            self.logger.error("Error fetching URLs: %s", str(error))
            return articles

        # Step 2: parse each article
        for url in urls:
            article = self._scrape_single_article(url)
            if article is not None:
                articles.append(article)

            # Rate limiting: be respectful to the server
            time.sleep(self.rate_limit_seconds)

        self.logger.info("Scraping completed: %d/%d articles", len(articles), len(urls))
        return articles

    def _scrape_single_article(self, url: str) -> Optional[dict]:
        """
        Downloads and parses a single article with retries.
        """
        html = self._fetch_with_retries(url)
        if html is None:
            return None

        try:
            soup = BeautifulSoup(html, "lxml")
            article = self.parse_article(url, soup)

            if article is None:
                self.logger.warning("Parse returned None: %s", url)
                return None

            # Attach automatic metadata fields
            article["source"] = self.source_name
            article["url"] = url
            article["scraped_at"] = datetime.now(timezone.utc).isoformat()
            article["raw_html"] = html
            article["_article_id"] = self._generate_article_id(url)

            # Validate schema
            if self._validate_article(article):
                return article

            return None

        except Exception as error:
            self.logger.error("Error parsing article %s: %s", url, str(error))
            return None

    # -------------------------------------------------------
    # HTTP with retries
    # -------------------------------------------------------

    def _fetch_with_retries(self, url: str) -> Optional[str]:
        """
        Downloads a URL with retries and exponential backoff.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                return response.text

            except requests.RequestException as error:
                wait_time = 2 ** attempt
                self.logger.warning(
                    "Retrying download %s attempt %d: %s", url, attempt, str(error)
                )
                if attempt < self.max_retries:
                    time.sleep(wait_time)

        self.logger.error("Download failed after all retries: %s", url)
        return None

    # -------------------------------------------------------
    # Schema validation
    # -------------------------------------------------------

    def _validate_article(self, article: dict) -> bool:
        """
        Checks that the article has all required fields
        and that the content is not empty.
        """
        for field in self.REQUIRED_FIELDS:
            value = article.get(field)
            if not value or (isinstance(value, str) and len(value.strip()) == 0):
                self.logger.warning(
                    "Invalid article, missing field '%s': %s",
                    field,
                    article.get("url")
                )
                return False

        return True

    # -------------------------------------------------------
    # Utilities
    # -------------------------------------------------------

    @staticmethod
    def _generate_article_id(url: str) -> str:
        """
        Generates a unique ID for each article based on its URL.
        Allows duplicate detection across multiple runs.
        """
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Basic text cleanup: removes extra whitespace and newlines.
        """
        if not text:
            return ""
        # Normalize whitespace
        lines = text.strip().splitlines()
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        return "\n".join(cleaned_lines)

    def make_absolute_url(self, relative_url: str) -> str:
        """
        Converts a relative URL to absolute using the site's base URL.
        """
        if relative_url.startswith("http"):
            return relative_url
        # Avoid double slashes when joining base and path
        base = self.base_url.rstrip("/")
        path = relative_url.lstrip("/")
        return f"{base}/{path}"
