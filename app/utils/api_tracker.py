from functools import wraps
from flask import request, current_app
import time
import json
from financial_data.utils.db_connection import get_db_connection


def track_plaid_call(product, operation):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            access_token = kwargs.get('access_token') or (args[0] if args else None)
            
            try:
                # Execute the Plaid API call
                response = f(*args, **kwargs)
                success = True
                error_code = None
                error_message = None
                
                # Extract rate limit info from response headers if available
                rate_limit = getattr(response, 'headers', {}).get('X-RateLimit-Remaining')
                
                # Count items retrieved (customize based on response type)
                items_retrieved = len(getattr(response, 'transactions', [])) if hasattr(response, 'transactions') else None
                
            except Exception as e:
                success = False
                error_code = getattr(e, 'code', None)
                error_message = str(e)
                rate_limit = None
                items_retrieved = None
                raise
            finally:
                response_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
                
                # Log the Plaid API call
                conn = get_db_connection()
                cur = conn.cursor()
                
                try:
                    # Get access_token_id and institution_id
                    if access_token:
                        cur.execute("""
                            SELECT token_id, institution_id 
                            FROM access_tokens 
                            WHERE access_token = %s
                        """, (access_token,))
                        result = cur.fetchone()
                        access_token_id = result[0] if result else None
                        institution_id = result[1] if result else None
                    else:
                        access_token_id = None
                        institution_id = None

                    cur.execute("""
                        INSERT INTO plaid_api_calls 
                            (access_token_id, product, operation, institution_id,
                             response_time_ms, success, error_code, error_message,
                             rate_limit_remaining, items_retrieved)
                        VALUES 
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        access_token_id,
                        product,
                        operation,
                        institution_id,
                        response_time,
                        success,
                        error_code,
                        error_message,
                        rate_limit,
                        items_retrieved
                    ))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
            
            return response
        return decorated_function
    return decorator
