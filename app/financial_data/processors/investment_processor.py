from datetime import datetime
import pandas as pd
import json

def process_investments(holdings, securities, investment_accounts):
    """Process investment data into DataFrame format"""
    #print("\n=== Processing Investments ===")
    #print(f"Number of holdings to process: {len(holdings)}")
    
    if not holdings:
        return pd.DataFrame()
    
    records = []
    for holding in holdings:
        #print(f"\nProcessing holding: {holding.account_id}")
        
        # Get the security details for this holding
        security = next((s for s in securities if s.security_id == holding.security_id), None)
        
        # Get the account details
        account = next((a for a in investment_accounts if a.account_id == holding.account_id), None)
        
        record = {
            'account_id': holding.account_id,
            'account_name': getattr(account, 'name', None),
            'account_type': str(getattr(account, 'type', None)),
            'account_subtype': str(getattr(account, 'subtype', None)),
            'security_id': holding.security_id,
            'security_name': getattr(security, 'name', None),
            'security_type': getattr(security, 'type', None),
            'ticker_symbol': getattr(security, 'ticker_symbol', None),
            'isin': getattr(security, 'isin', None),
            'cusip': getattr(security, 'cusip', None),
            'quantity': float(getattr(holding, 'quantity', 0)) if getattr(holding, 'quantity', None) is not None else None,
            'price': float(getattr(holding, 'price', 0)) if getattr(holding, 'price', None) is not None else None,
            'value': float(getattr(holding, 'value', 0)) if getattr(holding, 'value', None) is not None else None,
            'cost_basis': float(getattr(holding, 'cost_basis', 0)) if getattr(holding, 'cost_basis', None) is not None else None,
            'currency_code': getattr(holding, 'iso_currency_code', None),
            'pull_date': datetime.now().date()
        }
        records.append(record)
    
    df = pd.DataFrame(records)
    
    #print("\nProcessed DataFrame:")
    #print(df.dtypes)
    #print("\nSample data:")
    #print(df.head())
    
    return df
