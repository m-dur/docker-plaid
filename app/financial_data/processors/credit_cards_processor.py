from datetime import datetime
import pandas as pd


def process_credit_cards(accounts, bank_balances, credit_cards):
    """Process credit card data into DataFrame format"""
    credit_card_accounts = [a for a in accounts if a.type == 'credit' or 'credit' in a.name.lower()]
    
    records = []
    for a in credit_card_accounts:
        record = {
            'account_id': str(a.account_id),
            'balance_current': None,
            'balance_available': None,
            'balance_limit': None,
            'last_statement_balance': None,
            'last_statement_date': None,
            'minimum_payment_amount': None,
            'next_payment_due_date': None,
            'apr_percentage': None,
            'apr_type': None,
            'balance_subject_to_apr': None,
            'interest_charge_amount': None,
            'pull_date': datetime.now().date()
        }
        
        # Process account balances
        for bal in bank_balances:
            if bal.account_id == a.account_id:
                record['balance_current'] = float(bal.balances.current) if bal.balances.current is not None else None
                record['balance_available'] = float(bal.balances.available) if bal.balances.available is not None else None
                record['balance_limit'] = float(bal.balances.limit) if bal.balances.limit is not None else None
                break
        
        # Process liability-specific values
        for l in credit_cards:
            if l.account_id == a.account_id:
                try:
                    record['last_statement_balance'] = float(l.last_statement_balance) if l.last_statement_balance is not None else None
                    record['minimum_payment_amount'] = float(l.minimum_payment_amount) if l.minimum_payment_amount is not None else None
                    
                    # Handle dates
                    record['last_statement_date'] = pd.to_datetime(l.last_statement_issue_date).date() if l.last_statement_issue_date else None
                    record['next_payment_due_date'] = pd.to_datetime(l.next_payment_due_date).date() if l.next_payment_due_date else None
                    
                    # Handle APR information
                    if hasattr(l, 'aprs') and l.aprs and len(l.aprs) > 0:
                        apr = l.aprs[0]  # Get first APR entry
                        record['apr_percentage'] = float(apr.apr_percentage) if apr.apr_percentage is not None else None
                        record['apr_type'] = str(apr.apr_type)[:50] if apr.apr_type else None
                        record['balance_subject_to_apr'] = float(apr.balance_subject_to_apr) if apr.balance_subject_to_apr is not None else None
                        record['interest_charge_amount'] = float(apr.interest_charge_amount) if apr.interest_charge_amount is not None else None
                except Exception as e:
                    print(f"Error processing credit card data: {e}")
                break
        
        records.append(record)
    
    return pd.DataFrame(records) if records else pd.DataFrame()