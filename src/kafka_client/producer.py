"""
Producer Kafka
"""
import requests
import json
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime
from kafka import KafkaProducer

# API params
PATH_LAST_PROCESSED = "./data/last_processed.json"
MAX_LIMIT = 100
MAX_OFFSET = 10000

URL_API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso0/records?limit={}"
URL_API = URL_API.format(MAX_LIMIT)

def create_producer():
    """Create KafkaProducer

    Returns:
        KafkaProducer
    """
    return KafkaProducer(
        bootstrap_servers=['kafka:9094'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )

def fetch_data_from_api(**kwargs):
    """Fetch data from api

    Returns:
        json: raw data
    """
    try:
        response = requests.get(URL_API)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

def send_data_to_kafka(**kwargs):
    """Send data to kafka

    Args:
        data (json): raw data
    """
    ti = kwargs['ti']
    data = ti.xcom_pull(task_ids='fetch_data_from_api_task')
    if data:
        producer = create_producer()
        for item in data.get("results", []):
            key = item.get("reference_fiche", "")
            value = item
            producer.send("test", key=key, value=value)
        producer.flush()

default_args = {
    'owenr': 'tranhuy3',
    'start_date': datetime(2024, 6, 2),
}

with DAG(
    'fetch_and_send_kafka_dag',
    default_args=default_args,
    description='Fetch data from API and send to Kafka',
    schedule_interval='@daily',
    catchup=False,
) as dag:
    # Task để fetch data từ API
    fetch_data_from_api_task = PythonOperator(
        task_id='fetch_data_from_api_task',
        python_callable=fetch_data_from_api,
        provide_context=True,
    )

    # Task để gửi data tới Kafka
    send_data_to_kafka_task = PythonOperator(
        task_id='send_data_to_kafka_task',
        python_callable=send_data_to_kafka,
        provide_context=True,
    )

    # Thiết lập thứ tự chạy các task
    fetch_data_from_api_task >> send_data_to_kafka_task
