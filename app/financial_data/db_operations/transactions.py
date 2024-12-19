from financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import execute_values

def save_transactions_to_db(transactions_df, conn=None, cur=None):
    """Save transactions data to the database"""
    should_close = False
    if conn is None or cur is None:
        conn = get_db_connection()
        cur = conn.cursor()
        should_close = True
    
    try:
        if 'transactions' in transactions_df and not transactions_df['transactions'].empty:
            # Get existing category mappings
            cur.execute("SELECT transaction_name, category FROM category_mappings")
            category_mappings = dict(cur.fetchall())
            
            # Get existing group mappings
            cur.execute("SELECT transaction_name, group_name FROM group_mappings")
            group_mappings = dict(cur.fetchall())
            
            # Update categories and groups based on mappings
            transactions_df['transactions']['category'] = transactions_df['transactions'].apply(
                lambda x: category_mappings.get(x['name'], x['category']),
                axis=1
            )
            
            transactions_df['transactions']['group_name'] = transactions_df['transactions'].apply(
                lambda x: group_mappings.get(x['name'], x['group_name']),
                axis=1
            )
            
            execute_values(cur, """
                INSERT INTO transactions 
                (transaction_id, account_id, amount, date, name, category,
                merchant_name, group_name, payment_channel, authorized_datetime, pull_date)
                VALUES %s
                ON CONFLICT (transaction_id) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    date = EXCLUDED.date,
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    group_name = EXCLUDED.group_name,
                    merchant_name = EXCLUDED.merchant_name,
                    payment_channel = EXCLUDED.payment_channel,
                    authorized_datetime = EXCLUDED.authorized_datetime,
                    pull_date = EXCLUDED.pull_date
                RETURNING transaction_id
            """, [tuple(x) for x in transactions_df['transactions'].values])
            
            saved = cur.fetchall()
            return len(saved)
            
        return 0
        
    except Exception as e:
        raise
    finally:
        if should_close:
            if cur:
                cur.close()
            if conn:
                conn.close() 