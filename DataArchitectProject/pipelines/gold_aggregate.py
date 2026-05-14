import os
import re
import logging
from io import BytesIO
from collections import Counter

import boto3
import pandas as pd

logger = logging.getLogger("gold_aggregate")

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "have", "has", "had",
    "will", "would", "could", "should", "may", "might", "can", "to", "of",
    "in", "for", "on", "with", "at", "by", "from", "and", "but", "or",
    "not", "that", "this", "it", "he", "she", "they", "we", "you", "who",
    "which", "what", "when", "where", "how", "if", "then", "there",
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en",
    "est", "sont", "que", "qui", "dans", "pour", "sur", "avec", "par",
    "في", "من", "على", "إلى", "عن", "مع", "هذا", "هذه", "أن", "كان",
}

SOURCE_COUNTRY = {
    "hespress": "Morocco", "akhbarona": "Morocco",
    "aljazeera": "Qatar", "bbc": "UK",
    "cnn": "USA", "reuters": "UK",
}


class GoldAggregator:

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )

    def aggregate(self, date_str: str) -> dict:

        df = self._read_silver(date_str)
        if df is None or df.empty:
            logger.warning({"date": date_str}, "No Silver data found")
            return {}

        daily = self._daily_stats(df, date_str)
        kw = self._top_keywords(df, date_str)
        src = self._source_stats(df)

        self._write_gold(daily, f"daily_stats/date={date_str}/stats.parquet")
        self._write_gold(kw, f"top_keywords/date={date_str}/keywords.parquet")
        self._write_gold(src, f"source_stats/date={date_str}/sources.parquet")

        return {"date": date_str, "articles": len(df), "keywords": len(kw)}

    def _read_silver(self, date_str):
        try:
            resp = self.s3.get_object(Bucket="silver", Key=f"date={date_str}/articles.parquet")
            return pd.read_parquet(BytesIO(resp["Body"].read()))
        except Exception as e:
            logger.error({"error": str(e)}, "Error reading Silver")
            return None

    def _daily_stats(self, df, date_str):
        stats = df.groupby(["source", "category"]).size().reset_index(name="article_count")
        stats["stat_date"] = date_str
        stats["country"] = stats["source"].map(SOURCE_COUNTRY).fillna("Unknown")
        return stats

    def _top_keywords(self, df, date_str, top_n=50):
        words = []
        for content in df["content"].dropna():
            tokens = re.findall(r"\b\w{4,}\b", content.lower())
            words.extend(t for t in tokens if t not in STOP_WORDS)
        kw_df = pd.DataFrame(Counter(words).most_common(top_n), columns=["keyword", "frequency"])
        kw_df["stat_date"] = date_str
        return kw_df

    def _source_stats(self, df):
        stats = df.groupby("source").agg(total_articles=("url", "count")).reset_index()
        stats["country"] = stats["source"].map(SOURCE_COUNTRY).fillna("Unknown")
        return stats

    def _write_gold(self, df, key):
        if df is None or df.empty:
            return
        buf = BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        buf.seek(0)
        self.s3.put_object(Bucket="gold", Key=key, Body=buf.getvalue())
        logger.info({"key": key}, "Gold file saved")
