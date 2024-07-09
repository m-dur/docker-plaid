from plaid import Client
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from datetime import datetime, timedelta
import os

def get_plaid_client():
    return Client(
        client_id=os.getenv('PLAID_CLIENT_ID'),
        secret=os.getenv('PLAID_SECRET'),
        environment='sandbox'
    )

def fetch_transactions(access_token, start_date, end_date):
    client = get_plaid_client()
    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date,
        end_date=end_date,
        options=TransactionsGetRequestOptions(
            count=500,
            offset=0
        )
    )
    response = client.transactions_get(request)
    return response['transactions']