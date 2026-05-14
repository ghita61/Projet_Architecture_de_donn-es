import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

from hespress_scraper import HespressScraper
from bbc_scraper import BBCScraper
from akhbarona_scraper import AkhbaronaScraper
from aljazeera_scraper import AlJazeeraScraper
from cnn_scraper import CNNScraper
from reuters_scraper import ReutersScraper

logger = logging.getLogger("runner")

# Registry of all available scrapers
SCRAPER_REGISTRY = {
    "hespress": HespressScraper,
    "bbc": BBCScraper,
    "akhbarona": AkhbaronaScraper,
    "aljazeera": AlJazeeraScraper,
    "cnn": CNNScraper,
    "reuters": ReutersScraper,
}


def run_scrapers(sources: list[str] | None = None) -> list[dict]:

    if sources is None:
        sources = list(SCRAPER_REGISTRY.keys())

    all_articles = []

    for source_name in sources:
        scraper_class = SCRAPER_REGISTRY.get(source_name)
        if scraper_class is None:
            logger.warning("Source not registered, skipping: %s", source_name)
            continue

        logger.info("Running scraper: %s", source_name)
        try:
            scraper = scraper_class()
            articles = scraper.scrape_all()
            all_articles.extend(articles)
            logger.info("Scraper completed: %s, %d articles", source_name, len(articles))
        except Exception as error:
            logger.error("Scraper error for %s: %s", source_name, str(error))

    return all_articles


def save_to_file(articles: list[dict], output_dir: str) -> str:

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"articles_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    # Strip raw_html before saving to file (it is stored separately in Bronze)
    articles_without_html = []
    for article in articles:
        clean_article = {
            key: value
            for key, value in article.items()
            if key != "raw_html"
        }
        articles_without_html.append(clean_article)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            articles_without_html,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    logger.info("Articles saved to %s, count: %d", filepath, len(articles))
    return filepath


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="News Article Scraper Runner")
    parser.add_argument(
        "--source",
        type=str,
        help="Name of the source to run (e.g. bbc, hespress). Omit to run all.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./output",
        help="Output directory for JSON files (default: ./output)",
    )
    args = parser.parse_args()

    sources = [args.source] if args.source else None
    articles = run_scrapers(sources)

    if articles:
        filepath = save_to_file(articles, args.output)
        print(f"\n✅ {len(articles)} articles saved to: {filepath}")
    else:
        print("\n⚠️  No articles were collected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
