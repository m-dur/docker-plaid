import pandas as pd
from datetime import datetime

def process_item(item_response, institution_response, access_token):
    """Process item and institution data into DataFrame format"""
    record = {
        'item_id': item_response.item.item_id,
        'institution_id': item_response.item.institution_id,
        'institution_name': institution_response.institution.name if institution_response else None,
        'access_token': access_token,
        'available_products': [str(p) for p in item_response.item.available_products] if item_response.item.available_products else [],
        'billed_products': [str(p) for p in item_response.item.billed_products] if item_response.item.billed_products else [],
        'error_code': item_response.item.error.error_code if hasattr(item_response.item, 'error') and item_response.item.error else None,
        'error_message': item_response.item.error.error_message if hasattr(item_response.item, 'error') and item_response.item.error else None,
        'pull_date': datetime.now().date()
    }
    
    return pd.DataFrame([record])
