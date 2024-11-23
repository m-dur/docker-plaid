from psycopg2.extras import execute_values
from financial_data.config.db_config import get_db_connection

def save_institutions_to_db(institutions_df):
    """Save institutions data to the institutions table"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    #print(f"Input DataFrame: {institutions_df.to_dict('records')}")
    #print(f"DataFrame dtypes: {institutions_df.dtypes}")
    
    # Convert DataFrame to list of tuples with explicit bool conversion
    records = []
    for record in institutions_df.to_records(index=False):
        record_list = list(record)
        # OAuth is at index 5 based on the SQL table structure
        record_list[5] = bool(record_list[5])  # Convert numpy.bool_ to Python bool
        records.append(tuple(record_list))
    
    #print(f"Converted records: {records}")
    #print(f"Record types: {[type(x) for x in records[0]]}")
    
    query = """
        INSERT INTO institutions (id, name, type, status, url, oauth, refresh_interval, billed_products)
        VALUES %s
        ON CONFLICT (id) 
        DO UPDATE SET 
            name = EXCLUDED.name,
            type = EXCLUDED.type,
            status = EXCLUDED.status,
            url = EXCLUDED.url,
            oauth = EXCLUDED.oauth,
            refresh_interval = EXCLUDED.refresh_interval,
            billed_products = EXCLUDED.billed_products
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