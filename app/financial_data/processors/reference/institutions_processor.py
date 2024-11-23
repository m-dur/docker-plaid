from datetime import datetime
import pandas as pd

def process_institutions(items):
    """Process institution data into institutions table format"""
    records = []
    
    for item in items:
        record = {
            'id': str(item['institution_id']),
            'name': str(item['name']),
            'type': ','.join(item.get('products', [])) if item.get('products') else None,
            'status': item.get('status', 'active'),
            'url': item.get('url'),
            'oauth': bool(item.get('oauth', False)),
            'refresh_interval': item.get('refresh_interval'),
            'billed_products': None  # We don't have this info from the simplified response
        }
        records.append(record)
    
    return pd.DataFrame(records) 