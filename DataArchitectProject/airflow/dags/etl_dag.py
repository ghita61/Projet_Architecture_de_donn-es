import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow/pipelines")
sys.path.insert(0, "/opt/airflow/governance")

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}


def get_processing_date(**context):
 
    from datetime import datetime as dt

    today = dt.now().strftime("%Y-%m-%d")
    context["ti"].xcom_push(key="processing_date", value=today)
    print(f"📅 Processing data for: {today}")
    return today


def task_bronze_to_silver(**context):
    from silver_transform import SilverTransformer

    date_str = context["ti"].xcom_pull(key="processing_date", task_ids="get_date")
    transformer = SilverTransformer()
    count = transformer.transform(date_str)
    print(f"🥈 Silver: {count} articles processed")
    return count


def task_silver_to_gold(**context):
    from gold_aggregate import GoldAggregator

    date_str = context["ti"].xcom_pull(key="processing_date", task_ids="get_date")
    aggregator = GoldAggregator()
    metrics = aggregator.aggregate(date_str)
    print(f"🥇 Gold: {metrics}")
    return metrics


def task_gold_to_warehouse(**context):
    from warehouse_loader import WarehouseLoader

    date_str = context["ti"].xcom_pull(key="processing_date", task_ids="get_date")
    loader = WarehouseLoader()
    loader.load_all(date_str)
    print(f"🏛️  Warehouse: data loaded for {date_str}")


def task_update_catalog(**context):
    from data_catalog import DataCatalog

    catalog = DataCatalog()
    catalog.publish_catalog()
    print("📚 Data catalog updated")


# --- DAG definition ---
with DAG(
    dag_id="news_etl_pipeline",
    default_args=DEFAULT_ARGS,
    description="ETL Pipeline: Bronze → Silver → Gold → PostgreSQL",
    schedule_interval="30 * * * *",  # 30 minutes after scraping
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "transformation", "medallion"],
) as dag:

    get_date = PythonOperator(
        task_id="get_date",
        python_callable=get_processing_date,
    )

    silver = PythonOperator(
        task_id="bronze_to_silver",
        python_callable=task_bronze_to_silver,
    )

    gold = PythonOperator(
        task_id="silver_to_gold",
        python_callable=task_silver_to_gold,
    )

    warehouse = PythonOperator(
        task_id="gold_to_warehouse",
        python_callable=task_gold_to_warehouse,
    )

    catalog = PythonOperator(
        task_id="update_catalog",
        python_callable=task_update_catalog,
    )

    # Sequential flow: date → silver → gold → warehouse → catalog
    get_date >> silver >> gold >> warehouse >> catalog
