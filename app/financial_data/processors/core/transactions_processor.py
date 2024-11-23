from datetime import datetime
import pandas as pd

def process_transactions(transactions_data):
    if not transactions_data:
        return {
            'transactions': pd.DataFrame()
        }
    
    transaction_records = []
    
    for idx, transaction in enumerate(transactions_data):
        try:
            transaction_record = {
                'transaction_id': str(transaction.transaction_id),
                'account_id': str(transaction.account_id),
                'amount': float(transaction.amount),
                'date': pd.to_datetime(transaction.date).date(),
                'name': str(transaction.name)[:255],
                'merchant_name': str(transaction.merchant_name)[:255] if hasattr(transaction, 'merchant_name') and transaction.merchant_name else None,
                'category': getattr(transaction, 'mapped_category', None),
                'group_name': None,
                'payment_channel': str(transaction.payment_channel).lower() if hasattr(transaction, 'payment_channel') and transaction.payment_channel else None,
                'authorized_datetime': pd.to_datetime(transaction.authorized_datetime).to_pydatetime() if hasattr(transaction, 'authorized_datetime') and transaction.authorized_datetime else None,
                'pull_date': datetime.now().date()
            }
            transaction_records.append(transaction_record)
            
        except Exception as e:
            continue
    
    df = pd.DataFrame(transaction_records)
    return {
        'transactions': df
    }