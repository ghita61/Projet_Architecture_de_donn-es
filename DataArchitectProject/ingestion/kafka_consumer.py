import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("kafka_consumer")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_ARTICLES", "raw-articles")
KAFKA_GROUP_ID = "bronze-writer-group"


def consume_and_store():

    try:
        from kafka import KafkaConsumer
        import boto3

        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            group_id=KAFKA_GROUP_ID,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

        s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
        )

        logger.info("Kafka consumer started, waiting for messages...")

        for message in consumer:
            article = message.value
            _store_in_bronze(s3_client, article)

    except Exception as error:
        logger.error({"error": str(error)}, "Error in Kafka consumer")
        raise


def _store_in_bronze(s3_client, article: dict):
    source = article.get("source", "unknown")
    scraped_at = article.get("scraped_at", datetime.now(timezone.utc).isoformat())
    article_id = article.get("_article_id", "unknown")

    date_str = scraped_at[:10]  # YYYY-MM-DD

    key = f"source={source}/date={date_str}/{article_id}.json"
    body = json.dumps(article, ensure_ascii=False, default=str)

    try:
        s3_client.put_object(
            Bucket="bronze",
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info({"key": key}, "Article stored in Bronze")
    except Exception as error:
        logger.error({"key": key, "error": str(error)}, "Error storing article in Bronze")


if __name__ == "__main__":
    consume_and_store()
