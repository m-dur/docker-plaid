from functools import wraps
from flask import request, current_app
import time
import json
from financial_data.utils.db_connection import get_db_connection

def track_api_call(is_plaid=False):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            endpoint = request.endpoint
            method = request.method
            
            # Capture request payload
            try:
                request_payload = {
                    'args': dict(request.args),
                    'json': request.get_json(silent=True),
                    'form': dict(request.form)
                }
            except Exception:
                request_payload = {}
            
            try:
                # Execute the original function
                response = f(*args, **kwargs)
                status_code = response.status_code if hasattr(response, 'status_code') else 200
                error = None
                
                # Capture response payload if it's JSON
                try:
                    response_payload = response.get_json() if hasattr(response, 'get_json') else None
                except Exception:
                    response_payload = None
                    
            except Exception as e:
                status_code = 500
                error = str(e)
                response_payload = None
                raise
            finally:
                # Calculate response time
                response_time = time.time() - start_time
                
                # Log the API call
                conn = get_db_connection()
                cur = conn.cursor()
                
                try:
                    cur.execute("""
                        INSERT INTO api_calls 
                            (endpoint, method, is_plaid, called_at, 
                             caller_type, response_time, status_code, 
                             error, request_payload, response_payload)
                        VALUES 
                            (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, 
                             %s, %s, %s)
                    """, (
                        endpoint, 
                        method, 
                        is_plaid,
                        request.headers.get('X-Caller-Type', 'user'),
                        response_time,
                        status_code,
                        error,
                        json.dumps(request_payload),
                        json.dumps(response_payload) if response_payload else None
                    ))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
            
            return response
        return decorated_function
    return decorator

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
