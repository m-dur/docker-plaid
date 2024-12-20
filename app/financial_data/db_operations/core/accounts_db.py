from psycopg2.extras import execute_values
from financial_data.utils.db_connection import get_db_connection
import numpy as np

def save_accounts_to_db(accounts_dfs, conn=None, cur=None):
    """Save accounts data to account_history table"""
    should_close = False
    if conn is None or cur is None:
        conn = get_db_connection()
        cur = conn.cursor()
        should_close = True
    
    try:
        # Combine all account information into one DataFrame
        base_accounts = accounts_dfs['base']
        
        # Ensure DataFrame columns match exactly with table columns
        columns = [
            'account_id', 'account_name', 'institution_id', 'type',
            'subtype', 'mask', 'verification_status', 'currency',
            'balance_current', 'balance_available', 'balance_limit',
            'last_statement_issue_date', 'last_statement_balance',
            'last_payment_amount', 'last_payment_date', 'last_statement_date',
            'minimum_payment_amount', 'next_payment_due_date',
            'apr_percentage', 'apr_type', 'balance_subject_to_apr',
            'interest_charge_amount', 'pull_date'
        ]
        
        for account_type in ['depository', 'credit']:
            if not accounts_dfs[account_type].empty:
                # Drop pull_date from type_df before merging to avoid duplicates
                type_df = accounts_dfs[account_type].drop(columns=['pull_date'])
                base_accounts = base_accounts.merge(
                    type_df,
                    on='account_id',
                    how='left'
                )
        
        # After merging account types
        for col in columns:
            if col not in base_accounts.columns:
                base_accounts[col] = None
        
        # Replace NaN values with None for all columns
        for col in base_accounts.columns:
            if base_accounts[col].dtype == 'object' or base_accounts[col].dtype == 'datetime64[ns]':
                base_accounts[col] = base_accounts[col].where(base_accounts[col].notna(), None)
            elif 'float' in str(base_accounts[col].dtype) or 'int' in str(base_accounts[col].dtype):
                base_accounts[col] = base_accounts[col].where(base_accounts[col].notna(), None)
        
        # Reorder DataFrame columns to match table columns
        base_accounts = base_accounts.reindex(columns=columns)
        
        # Add after line 15
        print("Debug - Available columns in base_accounts:")
        print(base_accounts.columns.tolist())
        
        # Insert into account_history
        execute_values(cur, """
            INSERT INTO account_history (
                {}
            ) VALUES %s
        """.format(','.join(columns)), [tuple(x) for x in base_accounts.values])
        
        # Add after line 53
        print("Debug - Final columns before insert:")
        print(base_accounts.columns.tolist())
        print("Debug - First row sample:")
        print(base_accounts.iloc[0])
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error saving to account_history: {e}")
        if should_close:
            conn.rollback()
        raise
    finally:
        if should_close:
            cur.close()
            conn.close()