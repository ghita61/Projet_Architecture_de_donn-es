
import os
import re
import json
import logging
from io import BytesIO

import boto3
import pandas as pd
from langdetect import detect, LangDetectException

logger = logging.getLogger("silver_transform")


class SilverTransformer:

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )

    def transform(self, date_str: str) -> int:
        # Step 1: read Bronze data
        articles = self._read_bronze(date_str)
        if not articles:
            logger.warning({"date": date_str}, "No Bronze data to transform")
            return 0

        df = pd.DataFrame(articles)

        # Step 2: strip residual HTML tags
        df["content"] = df["content"].apply(self._strip_html)
        df["title"] = df["title"].apply(self._strip_html)

        # Step 3: normalise text
        df["content"] = df["content"].apply(self._normalize_text)
        df["title"] = df["title"].apply(self._normalize_text)

        # Step 4: detect language
        df["_language"] = df["content"].apply(self._detect_language)

        # Step 5: deduplicate by URL
        initial_count = len(df)
        df = df.drop_duplicates(subset=["url"], keep="first")
        duplicates_removed = initial_count - len(df)
        if duplicates_removed > 0:
            logger.info({"removed": duplicates_removed}, "Duplicates removed")

        # Step 6: drop raw_html — no longer needed in Silver
        if "raw_html" in df.columns:
            df = df.drop(columns=["raw_html"])

        # Step 7: add traceability metadata
        df["_silver_processed_at"] = pd.Timestamp.utcnow().isoformat()

        # Step 8: save as Parquet in Silver
        self._write_silver(df, date_str)

        logger.info(
            {"date": date_str, "count": len(df)},
            "Silver transformation completed"
        )
        return len(df)

    def _read_bronze(self, date_str: str) -> list[dict]:
        articles = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        # Search across all sources for the given date
        for page in paginator.paginate(Bucket="bronze", Prefix=f"source="):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if f"date={date_str}" in key and key.endswith(".json"):
                    try:
                        response = self.s3_client.get_object(Bucket="bronze", Key=key)
                        article = json.loads(response["Body"].read().decode("utf-8"))
                        article["_bronze_path"] = key
                        articles.append(article)
                    except Exception as error:
                        logger.error({"key": key, "error": str(error)}, "Error reading Bronze")

        return articles

    def _write_silver(self, df: pd.DataFrame, date_str: str):
        buffer = BytesIO()
        df.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)

        key = f"date={date_str}/articles.parquet"
        self.s3_client.put_object(
            Bucket="silver",
            Key=key,
            Body=buffer.getvalue(),
            ContentType="application/octet-stream",
        )
        logger.info({"key": key}, "Silver Parquet saved")

    @staticmethod
    def _strip_html(text: str) -> str:
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"&\w+;", " ", clean)
        return clean.strip()

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        normalized = re.sub(r"[ \t]+", " ", text)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text or len(text) < 20:
            return "unknown"
        try:
            return detect(text)
        except LangDetectException:
            return "unknown"
