import pytest
from scripts.plaid_integration import get_plaid_client, fetch_transactions
from datetime import datetime, timedelta

def test_get_plaid_client():
    client = get_plaid_client()
    assert client is not None

@pytest.mark.skip(reason="Requires valid Plaid credentials")
def test_fetch_transactions():
    access_token = "your_test_access_token"
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    transactions = fetch_transactions(access_token, start_date, end_date)
    assert isinstance(transactions, list)
    assert len(transactions) > 0