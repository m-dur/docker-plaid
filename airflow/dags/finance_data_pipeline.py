from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from datetime import datetime, timedelta
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from main import fetch_plaid_transactions
from dependencies import SessionLocal

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email': ['your_email@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'finance_data_pipeline',
    default_args=default_args,
    description='A simple finance data pipeline',
    schedule_interval=timedelta(days=1),
)

def _fetch_plaid_transactions(**kwargs):
    db = SessionLocal()
    try:
        fetch_plaid_transactions(db=db)
    finally:
        db.close()

t1 = PythonOperator(
    task_id='fetch_plaid_transactions',
    python_callable=_fetch_plaid_transactions,
    dag=dag,
)

t2 = BashOperator(
    task_id='run_dbt',
    bash_command='cd /path/to/your/dbt/project && dbt run',
    dag=dag,
)

t1 >> t2