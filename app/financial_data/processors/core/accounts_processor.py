from datetime import datetime
import pandas as pd

def process_accounts(accounts, bank_balances, credit_cards=None, item_info=None):
    """Process core account data into accounts table format"""
    base_records = []
    depository_records = []
    credit_records = []
    loan_records = []
    investment_records = []
    account_types_seen = set()  # Track unique combinations of type+subtype
    account_types_records = []
    
    # Process credit cards first to create lookup dictionary
    credit_card_data = {}
    if credit_cards:
        for card in credit_cards:
            try:
                credit_card_data[card.account_id] = {
                    'last_statement_balance': float(card.last_statement_balance) if card.last_statement_balance is not None else None,
                    'minimum_payment_amount': float(card.minimum_payment_amount) if card.minimum_payment_amount is not None else None,
                    'last_statement_date': pd.to_datetime(card.last_statement_issue_date).date() if card.last_statement_issue_date else None,
                    'next_payment_due_date': pd.to_datetime(card.next_payment_due_date).date() if card.next_payment_due_date else None,
                    'apr_percentage': float(card.aprs[0].apr_percentage) if card.aprs and card.aprs[0].apr_percentage is not None else None,
                    'apr_type': str(card.aprs[0].apr_type)[:50] if card.aprs and card.aprs[0].apr_type else None,
                    'balance_subject_to_apr': float(card.aprs[0].balance_subject_to_apr) if card.aprs and card.aprs[0].balance_subject_to_apr is not None else None,
                    'interest_charge_amount': float(card.aprs[0].interest_charge_amount) if card.aprs and card.aprs[0].interest_charge_amount is not None else None
                }
            except Exception as e:
                print(f"Error processing credit card {card.account_id}: {e}")
    
    #print("\nDebug - Account Types Processing:")
    for account in accounts:
        # Get balance info
        balance_info = next((bal for bal in bank_balances if bal.account_id == account.account_id), None)
        
        # Track account type and subtype
        account_type = str(account.type).lower() if hasattr(account, 'type') else None
        sub_type = str(account.subtype).lower() if hasattr(account, 'subtype') else None
        
        if account_type:
            # Create unique key for type+subtype combination
            type_key = f"{account_type}:{sub_type if sub_type else 'NULL'}"
            
            if type_key not in account_types_seen:
                # Add main type if we haven't seen this combination before
                account_types_records.append({
                    'account_type': account_type,
                    'subtype': sub_type,
                    'status': 'active'
                })
                account_types_seen.add(type_key)
                #print(f"Debug - Found account type: {account_type}, subtype: {sub_type}")
        
        # Temporary store type info for later lookup
        base_record = {
            'account_id': str(account.account_id),
            'account_name': str(account.name)[:255],
            'last_updated_datetime': datetime.now(),
            'category': None,  # Replace account_type
            'group_name': None,  # Replace subtype
            'institution_id': item_info.get('institution_id') if item_info else None,
            'mask': str(getattr(account, 'mask', ''))[:20],
            'verification_status': str(getattr(account, 'verification_status', ''))[:50],
            'currency': str(getattr(account.balances, 'iso_currency_code', 'USD'))[:3],
            'pull_date': datetime.now().date()
        }
        base_records.append(base_record)

        # Continue with existing balance record processing
        if balance_info:
            account_type = str(account.type).lower()
            if account_type == 'depository':
                depository_record = {
                    'account_id': str(account.account_id),
                    'balance_current': float(balance_info.balances.current) if balance_info.balances.current is not None else None,
                    'balance_available': float(balance_info.balances.available) if balance_info.balances.available is not None else None,
                    'pull_date': datetime.now().date()
                }
                depository_records.append(depository_record)
                
            elif account_type == 'credit':
                #print("\nDebug - Processing Credit Account:")
                #print(f"Account ID: {account.account_id}")
                
                credit_record = {
                    'account_id': str(account.account_id),
                    'balance_current': float(balance_info.balances.current) if balance_info.balances.current is not None else None,
                    'balance_available': float(balance_info.balances.available) if balance_info.balances.available is not None else None,
                    'balance_limit': float(balance_info.balances.limit) if balance_info.balances.limit is not None else None,
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
                
                # Merge with liabilities data if available
                if account.account_id in credit_card_data:
                    liability_data = credit_card_data[account.account_id]
                    credit_record.update({
                        'last_statement_balance': liability_data.get('last_statement_balance'),
                        'last_statement_date': liability_data.get('last_statement_date') if pd.notna(liability_data.get('last_statement_date')) else None,
                        'minimum_payment_amount': liability_data.get('minimum_payment_amount'),
                        'next_payment_due_date': liability_data.get('next_payment_due_date') if pd.notna(liability_data.get('next_payment_due_date')) else None,
                        'apr_percentage': liability_data.get('apr_percentage'),
                        'apr_type': liability_data.get('apr_type'),
                        'balance_subject_to_apr': liability_data.get('balance_subject_to_apr'),
                        'interest_charge_amount': liability_data.get('interest_charge_amount')
                    })
                
                credit_records.append(credit_record)
                
            elif account_type == 'loan':
                loan_record = {
                    'account_id': str(account.account_id),
                    'balance_current': float(balance_info.balances.current) if balance_info.balances.current is not None else None,
                    'original_loan_amount': None,
                    'interest_rate': None,
                    'pull_date': datetime.now().date()
                }
                loan_records.append(loan_record)
            
            elif account_type == 'investment':
                investment_record = {
                    'account_id': str(account.account_id),
                    'balance_current': float(balance_info.balances.current) if balance_info.balances.current is not None else None,
                    'pull_date': datetime.now().date()
                }
                investment_records.append(investment_record)

    # Convert to DataFrames with explicit column ordering
    dfs = {
        'base': pd.DataFrame(base_records),
        'depository': pd.DataFrame(depository_records, columns=['account_id', 'balance_current', 'balance_available', 'pull_date']),
        'credit': pd.DataFrame(credit_records, columns=[
            'account_id', 'balance_current', 'balance_available', 'balance_limit',
            'last_statement_balance', 'last_statement_date', 'minimum_payment_amount',
            'next_payment_due_date', 'apr_percentage', 'apr_type',
            'balance_subject_to_apr', 'interest_charge_amount', 'pull_date'
        ]),
        'loan': pd.DataFrame(loan_records),
        'investment': pd.DataFrame(investment_records),
        'account_types': pd.DataFrame(account_types_records, columns=['account_type', 'subtype', 'status'])
    }
    
    # Debug print
    #print("\nDebug - Account Types Summary:")
    #print(f"Total unique account types/subtypes found: {len(account_types_records)}")
    #print("Account types DataFrame:")
    #print(dfs['account_types'])
    
    return dfs
