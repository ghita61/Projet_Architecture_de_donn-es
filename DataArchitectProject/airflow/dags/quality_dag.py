import os
import sys
import json
from datetime import datetime, timedelta
from io import BytesIO

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow/quality")
sys.path.insert(0, "/opt/airflow/pipelines")

DEFAULT_ARGS = {
    "owner": "data-quality",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def task_run_quality_checks(**context):
    import boto3
    import pandas as pd
    from data_checks import DataQualityChecker

    date_str = context["ds"]
    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
    )

    # Read Silver articles
    key = f"date={date_str}/articles.parquet"
    try:
        response = s3.get_object(Bucket="silver", Key=key)
        df = pd.read_parquet(BytesIO(response["Body"].read()))
    except Exception as error:
        print(f"⚠️  No Silver data for {date_str}: {error}")
        return {}

    # Run quality checks
    articles = df.to_dict("records")
    checker = DataQualityChecker()
    summary = checker.check_batch(articles)

    context["ti"].xcom_push(key="quality_summary", value=summary)
    print(f"🔍 Quality: {summary['valid_articles']}/{summary['total_articles']} valid")
    print(f"   Average score: {summary['average_quality_score']}")
    return summary


def task_save_quality_report(**context):
    from quality_report import QualityReporter

    date_str = context["ds"]
    summary = context["ti"].xcom_pull(
        key="quality_summary", task_ids="run_quality_checks"
    )

    if not summary:
        print("⚠️  No quality report to save")
        return

    reporter = QualityReporter()
    report = reporter.save_report(summary, date_str)
    print(f"📊 Report saved for {date_str}")
    return report


def task_quarantine_bad_records(**context):

    import boto3

    summary = context["ti"].xcom_pull(
        key="quality_summary", task_ids="run_quality_checks"
    )

    if not summary:
        return

    quarantine_urls = summary.get("quarantine_candidates", [])
    if not quarantine_urls:
        print("✅ No articles to quarantine")
        return

    print(f"⚠️  {len(quarantine_urls)} articles sent to quarantine")

    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio_admin"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "anaskaelar"),
    )

    date_str = context["ds"]
    quarantine_log = {
        "date": date_str,
        "quarantined_urls": quarantine_urls,
        "count": len(quarantine_urls),
    }

    s3.put_object(
        Bucket="quarantine",
        Key=f"date={date_str}/quarantine_log.json",
        Body=json.dumps(quarantine_log, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


# --- DAG definition ---
with DAG(
    dag_id="news_data_quality",
    default_args=DEFAULT_ARGS,
    description="Quality checks: completeness, coherence, validity",
    schedule_interval="45 * * * *",  # 45 minutes after scraping
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["quality", "governance", "validation"],
) as dag:

    checks = PythonOperator(
        task_id="run_quality_checks",
        python_callable=task_run_quality_checks,
    )

    report = PythonOperator(
        task_id="save_quality_report",
        python_callable=task_save_quality_report,
    )

    quarantine = PythonOperator(
        task_id="quarantine_bad_records",
        python_callable=task_quarantine_bad_records,
    )

    # Flow: checks → [report + quarantine in parallel]
    checks >> [report, quarantine]
