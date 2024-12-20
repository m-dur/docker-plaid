from datetime import datetime
import pandas as pd
from financial_data.utils.db_connection import get_db_connection

def process_accounts(accounts, bank_balances, credit_cards, additional_fields=None):
    base_data = []
    for account in accounts:
        # Get matching credit card data
        credit_data = next((c for c in credit_cards if c.account_id == account.account_id), None) if credit_cards else None
        
        account_data = {
            'account_id': account.account_id,
            'account_name': account.name,
            'institution_id': additional_fields['institution_id'] if additional_fields else None,
            'type': str(account.type),
            'subtype': str(account.subtype),
            'mask': account.mask,
            'verification_status': None,
            'currency': account.balances.iso_currency_code,
            'balance_current': float(account.balances.current) if account.balances.current else None,
            'balance_available': float(account.balances.available) if account.balances.available else None,
            'balance_limit': float(account.balances.limit) if account.balances.limit else None,
            'last_statement_issue_date': credit_data.last_statement_issue_date if credit_data else None,
            'last_statement_balance': float(credit_data.last_statement_balance) if credit_data and credit_data.last_statement_balance else None,
            'last_payment_amount': float(credit_data.last_payment_amount) if credit_data and credit_data.last_payment_amount else None,
            'last_payment_date': credit_data.last_payment_date if credit_data else None,
            'last_statement_date': credit_data.last_statement_issue_date if credit_data else None,
            'minimum_payment_amount': float(credit_data.minimum_payment_amount) if credit_data and credit_data.minimum_payment_amount else None,
            'next_payment_due_date': credit_data.next_payment_due_date if credit_data else None,
            'apr_percentage': float(credit_data.aprs[0].apr_percentage) if credit_data and credit_data.aprs else None,
            'apr_type': credit_data.aprs[0].apr_type if credit_data and credit_data.aprs else None,
            'balance_subject_to_apr': float(credit_data.aprs[0].balance_subject_to_apr) if credit_data and credit_data.aprs and credit_data.aprs[0].balance_subject_to_apr else None,
            'interest_charge_amount': float(credit_data.aprs[0].interest_charge_amount) if credit_data and credit_data.aprs and credit_data.aprs[0].interest_charge_amount else None,
            'pull_date': datetime.now().date()
        }
        base_data.append(account_data)
    
    return {
        'base': pd.DataFrame(base_data),
        'depository': pd.DataFrame(),
        'credit': pd.DataFrame()
    }
