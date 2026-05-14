import logging
from datetime import datetime, timezone

logger = logging.getLogger("lineage")


class LineageTracker:

    @staticmethod
    def stamp_bronze(article: dict, bronze_path: str) -> dict:
        article["_bronze_path"] = bronze_path
        article["_bronze_loaded_at"] = datetime.now(timezone.utc).isoformat()
        return article

    @staticmethod
    def stamp_silver(article: dict, silver_path: str) -> dict:
        article["_silver_path"] = silver_path
        article["_silver_processed_at"] = datetime.now(timezone.utc).isoformat()
        return article

    @staticmethod
    def stamp_gold(article: dict, gold_path: str) -> dict:
        article["_gold_path"] = gold_path
        article["_gold_aggregated_at"] = datetime.now(timezone.utc).isoformat()
        return article

    @staticmethod
    def get_lineage(article: dict) -> dict:
        lineage_fields = {
            k: v for k, v in article.items() if k.startswith("_")
        }
        return lineage_fields
