from psycopg2.extras import execute_values
from financial_data.utils.db_connection import get_db_connection

def save_institutions_to_db(institutions_df):
    """Save institutions data to the institutions table"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Convert DataFrame to list of tuples
    records = []
    for record in institutions_df.to_records(index=False):
        record_list = list(record)
        # Convert numpy.bool_ to Python bool for oauth field
        oauth_index = institutions_df.columns.get_loc('oauth')
        record_list[oauth_index] = bool(record_list[oauth_index])
        records.append(tuple(record_list))
    
    query = """
        INSERT INTO institutions (
            id, name, url, primary_color, logo, oauth, products, 
            status, last_status_change, success_rate, error_plaid_rate, 
            error_institution_rate, transactions_status, transactions_success_rate,
            liabilities_status, liabilities_success_rate, ingestion_timestamp
        )
        VALUES %s
    """
    
    try:
        execute_values(cur, query, records)
        conn.commit()
    except Exception as e:
        print(f"Error saving institutions to database: {e}")
        print(f"Failed record values: {records}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close() 