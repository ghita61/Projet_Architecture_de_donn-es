
import os
import json
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger("data_catalog")

# Dataset catalog definition
CATALOG = {
    "bronze": {
        "description": "Raw articles without transformation, exactly as scraped",
        "format": "JSON",
        "location": "minio://bronze/source=<source>/date=<YYYY-MM-DD>/",
        "schema": {
            "title": "str — Article title",
            "author": "str|null — Article author",
            "published_date": "str — ISO 8601 date",
            "category": "str|null — Category/section",
            "content": "str — Full article text",
            "source": "str — Source name",
            "url": "str — Original URL",
            "scraped_at": "str — UTC collection timestamp",
            "raw_html": "str — Full original HTML",
            "_article_id": "str — SHA256 hash of the URL",
        },
        "owner": "scraping-team",
        "update_frequency": "Every hour (batch) + real-time (streaming)",
    },
    "silver": {
        "description": "Clean, normalised articles with detected language",
        "format": "Parquet",
        "location": "minio://silver/date=<YYYY-MM-DD>/articles.parquet",
        "transformations": [
            "Removal of residual HTML",
            "Text normalisation (whitespace, encoding)",
            "Language detection (langdetect)",
            "Deduplication by URL",
            "Removal of raw_html",
        ],
        "owner": "data-engineering",
        "update_frequency": "After each Bronze load",
    },
    "gold": {
        "description": "Aggregated analytical tables for dashboards",
        "format": "Parquet",
        "location": "minio://gold/<table>/date=<YYYY-MM-DD>/",
        "tables": {
            "daily_stats": "Articles per day, source, category, and country",
            "top_keywords": "Most frequent keywords per day",
            "source_stats": "Cumulative statistics per source",
        },
        "owner": "analytics-team",
        "update_frequency": "After each Silver transformation",
    },
}


class DataCatalog:

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )

    def publish_catalog(self):
        catalog_doc = {
            "project": "Big Data News Analytics Platform",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "datasets": CATALOG,
        }
        body = json.dumps(catalog_doc, ensure_ascii=False, indent=2)
        self.s3.put_object(
            Bucket="bronze",
            Key="_metadata/data_catalog.json",
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Data catalog published")

    def get_dataset_info(self, layer: str) -> dict:
        return CATALOG.get(layer, {})
