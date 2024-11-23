from psycopg2.extras import DictCursor
from decimal import Decimal
from datetime import datetime, date
import json
from financial_data.config.db_config import get_db_connection
from flask import jsonify
import psycopg2

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def execute_query(query):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute(query)
        results = cur.fetchall()
        
        # Get column names from cursor description
        columns = [desc[0] for desc in cur.description] if cur.description else []
        
        # Convert results to list of dicts with proper serialization
        data = []
        for row in results:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, Decimal):
                    value = str(value)
                elif isinstance(value, (datetime, date)):
                    value = value.isoformat()
                row_dict[col] = value
            data.append(row_dict)
            
        return data
        
    except Exception as e:
        raise e
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close() 