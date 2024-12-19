from datetime import datetime
import pandas as pd

def process_institutions(items):
    """Process institution data into institutions table format"""
    records = []
    
    for item in items:
        # Get status breakdown if available
        status_breakdown = (item.get('status', {})
                          .get('item_logins', {})
                          .get('breakdown', {}))
        
        # Get transactions status if available
        transactions_status = (item.get('status', {})
                             .get('transactions_updates', {}))
        
        # Get liabilities status if available
        liabilities_status = (item.get('status', {})
                            .get('liabilities_updates', {}))

        record = {
            'id': str(item['institution_id']),
            'name': str(item['name']),
            'url': item.get('url'),
            'primary_color': item.get('primary_color'),
            'logo': item.get('logo'),
            'oauth': bool(item.get('oauth', False)),
            'products': item.get('products', []),
            'status': (item.get('status', {})
                      .get('item_logins', {})
                      .get('status')),
            'last_status_change': (item.get('status', {})
                                 .get('item_logins', {})
                                 .get('last_status_change')),
            'success_rate': status_breakdown.get('success'),
            'error_plaid_rate': status_breakdown.get('error_plaid'),
            'error_institution_rate': status_breakdown.get('error_institution'),
            'transactions_status': transactions_status.get('status'),
            'transactions_success_rate': (transactions_status.get('breakdown', {})
                                       .get('success')),
            'liabilities_status': liabilities_status.get('status'),
            'liabilities_success_rate': (liabilities_status.get('breakdown', {})
                                      .get('success')),
            'ingestion_timestamp': datetime.utcnow()
        }
        records.append(record)
    
    return pd.DataFrame(records) 