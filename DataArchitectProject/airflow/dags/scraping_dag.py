
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Add project folders to the Python path
sys.path.insert(0, "/opt/airflow/scrapers")
sys.path.insert(0, "/opt/airflow/pipelines")
sys.path.insert(0, "/opt/airflow/ingestion")

# --- DAG configuration ---
DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def task_scrape_articles(**context):
    from run_scrapers import run_scrapers

    articles = run_scrapers()
    # Push to XCom so downstream tasks can access the data
    context["ti"].xcom_push(key="articles", value=articles)
    context["ti"].xcom_push(key="article_count", value=len(articles))
    return len(articles)


def task_load_to_bronze(**context):
    from bronze_loader import BronzeLoader

    articles = context["ti"].xcom_pull(key="articles", task_ids="scrape_articles")
    if not articles:
        print("⚠️  No articles to load into Bronze")
        return 0

    loader = BronzeLoader()
    loaded = loader.load_articles(articles)
    return loaded


def task_publish_to_kafka(**context):
    from kafka_producer import publish_batch

    articles = context["ti"].xcom_pull(key="articles", task_ids="scrape_articles")
    if not articles:
        print("⚠️  No articles to publish to Kafka")
        return 0

    # Strip raw_html to reduce message size
    clean_articles = [
        {k: v for k, v in a.items() if k != "raw_html"}
        for a in articles
    ]
    published = publish_batch(clean_articles)
    return published


def task_log_summary(**context):
    count = context["ti"].xcom_pull(key="article_count", task_ids="scrape_articles")
    print(f"✅ Scraping completed: {count} articles collected")


# --- DAG definition ---
with DAG(
    dag_id="news_scraping_batch",
    default_args=DEFAULT_ARGS,
    description="Hourly batch news scraping → Bronze + Kafka",
    schedule_interval="0 * * * *",  # Every hour on the hour
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["scraping", "ingestion", "batch"],
) as dag:

    scrape = PythonOperator(
        task_id="scrape_articles",
        python_callable=task_scrape_articles,
    )

    load_bronze = PythonOperator(
        task_id="load_to_bronze",
        python_callable=task_load_to_bronze,
    )

    publish_kafka = PythonOperator(
        task_id="publish_to_kafka",
        python_callable=task_publish_to_kafka,
    )

    log = PythonOperator(
        task_id="log_summary",
        python_callable=task_log_summary,
    )

    # Flow: scrape → [bronze + kafka in parallel] → log
    scrape >> [load_bronze, publish_kafka] >> log
