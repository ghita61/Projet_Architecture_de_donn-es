import os
import json
import logging

logger = logging.getLogger("kafka_producer")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_ARTICLES", "raw-articles")


def publish_article(article: dict) -> bool:

    try:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"),
        )

        producer.send(KAFKA_TOPIC, value=article)
        producer.flush()
        logger.info({"url": article.get("url")}, "Article published to Kafka")
        return True

    except Exception as error:
        logger.error({"error": str(error)}, "Error publishing to Kafka")
        return False


def publish_batch(articles: list[dict]) -> int:

    try:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode("utf-8"),
        )

        producer.send(KAFKA_TOPIC, value=article)
        producer.flush()
        logger.info({"url": article.get("url")}, "Article published to Kafka")
        return True

    except Exception as error:
        logger.error({"error": str(error)}, "Error publishing to Kafka")
        return False


def publish_batch(articles: list[dict]) -> int:

    success_count = 0
    for article in articles:
        if publish_article(article):
            success_count += 1

    logger.info(
        {"published": success_count, "total": len(articles)},
        "Batch published to Kafka"
    )
    return success_count
