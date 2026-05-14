import os
import json
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger("bronze_loader")


class BronzeLoader:

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )
        self.bucket = "bronze"

    def load_articles(self, articles: list[dict]) -> int:

        success_count = 0
        batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for article in articles:
            try:
                source = article.get("source", "unknown")
                date_str = batch_timestamp[:8]  # YYYYMMDD
                article_id = article.get("_article_id", "unknown")

                # Partitioned path: bronze/source=X/date=YYYY-MM-DD/id.json
                key = (
                    f"source={source}/"
                    f"date={date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}/"
                    f"{article_id}.json"
                )

                body = json.dumps(article, ensure_ascii=False, default=str)

                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=body.encode("utf-8"),
                    ContentType="application/json",
                )
                success_count += 1

            except Exception as error:
                logger.error(
                    {"url": article.get("url"), "error": str(error)},
                    "Error loading article into Bronze"
                )

        logger.info(
            {"loaded": success_count, "total": len(articles)},
            "Bronze load completed"
        )
        return success_count

    def load_batch_file(self, filepath: str) -> int:

        with open(filepath, "r", encoding="utf-8") as f:
            articles = json.load(f)

        # Save the full batch file as a backup
        batch_key = f"batches/{os.path.basename(filepath)}"
        with open(filepath, "rb") as f:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=batch_key,
                Body=f,
                ContentType="application/json",
            )

        return self.load_articles(articles)
