from functools import wraps
import logging

def handle_db_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Database error in {func.__name__}: {str(e)}")
            raise
    return wrapper

def handle_processing_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Processing error in {func.__name__}: {str(e)}")
            raise
    return wrapper