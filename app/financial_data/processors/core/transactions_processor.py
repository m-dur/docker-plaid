from datetime import datetime
import pandas as pd

def process_transactions(transactions_data):
    if not transactions_data:
        return {
            'transactions': pd.DataFrame()
        }
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get existing mappings
        cur.execute("SELECT transaction_name, category FROM category_mappings")
        category_mappings = dict(cur.fetchall())
        
        cur.execute("SELECT transaction_name, group_name FROM group_mappings")
        group_mappings = dict(cur.fetchall())
        
        transaction_records = []
        
        for idx, transaction in enumerate(transactions_data):
            try:
                # Use mappings if available
                transaction_name = str(transaction.name)
                mapped_category = category_mappings.get(transaction_name)
                mapped_group = group_mappings.get(transaction_name)
                
                transaction_record = {
                    'transaction_id': str(transaction.transaction_id),
                    'account_id': str(transaction.account_id),
                    'amount': float(transaction.amount),
                    'date': pd.to_datetime(transaction.date).date(),
                    'name': transaction_name[:255],
                    'merchant_name': str(transaction.merchant_name)[:255] if hasattr(transaction, 'merchant_name') and transaction.merchant_name else None,
                    'category': mapped_category or getattr(transaction, 'category', None),
                    'group_name': mapped_group or None,
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
    finally:
        cur.close()
        conn.close()