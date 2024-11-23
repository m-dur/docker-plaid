from psycopg2.extras import execute_values
from financial_data.config.db_config import get_db_connection
import numpy as np

def save_accounts_to_db(accounts_dfs, conn=None, cur=None):
    """Save accounts data to the appropriate tables"""
    should_close = False
    if conn is None or cur is None:
        conn = get_db_connection()
        cur = conn.cursor()
        should_close = True
    
    saved_counts = {
        'base': 0,
        'depository': 0,
        'credit': 0,
        'loan': 0,
        'investment': 0,
        'account_types': 0
    }
    
    try:
        # First save account types and get their IDs
        if 'account_types' in accounts_dfs and not accounts_dfs['account_types'].empty:
            #pprint("\nDebug - Saving account types:")
            account_types_query = """
                INSERT INTO account_types (account_type, subtype, status)
                VALUES %s
                ON CONFLICT (account_type, subtype) 
                DO UPDATE SET 
                    status = EXCLUDED.status
                RETURNING id, account_type, subtype;
            """
            execute_values(cur, account_types_query, [tuple(x) for x in accounts_dfs['account_types'].values])
            type_mappings = cur.fetchall()
            
            # Create lookup dictionary
            type_id_lookup = {(t[1], t[2]): t[0] for t in type_mappings}
            
            # Update base records with account_type_ids
            base_df = accounts_dfs['base'].copy()
            
            # Add account_type_id column
            base_df['account_type_id'] = base_df.apply(
                lambda x: type_id_lookup.get((x['_account_type'], x['_subtype'])), 
                axis=1
            )
            
            # Select only the columns we need in the correct order
            base_df = base_df[[
                'account_id',
                'account_name',
                'last_updated_datetime',
                'account_type_id',
                'institution_id',
                'mask',
                'verification_status',
                'currency',
                'pull_date'
            ]]
            
            # Save base accounts
            base_query = """
                INSERT INTO accounts (
                    account_id, account_name, last_updated_datetime, account_type_id,
                    institution_id, mask, verification_status, currency, pull_date
                ) VALUES %s
                ON CONFLICT (account_id) 
                DO UPDATE SET 
                    account_name = EXCLUDED.account_name,
                    last_updated_datetime = EXCLUDED.last_updated_datetime,
                    account_type_id = EXCLUDED.account_type_id,
                    institution_id = EXCLUDED.institution_id,
                    mask = EXCLUDED.mask,
                    verification_status = EXCLUDED.verification_status,
                    currency = EXCLUDED.currency,
                    pull_date = EXCLUDED.pull_date
            """
            execute_values(cur, base_query, [tuple(x) for x in base_df.values])
            saved_counts['base'] = len(base_df)

        # Save depository accounts
        if not accounts_dfs['depository'].empty:
            depository_query = """
                INSERT INTO depository_accounts (
                    account_id, balance_current, balance_available, pull_date
                ) VALUES %s
                ON CONFLICT (account_id) 
                DO UPDATE SET 
                    balance_current = EXCLUDED.balance_current,
                    balance_available = EXCLUDED.balance_available,
                    pull_date = EXCLUDED.pull_date
            """
            execute_values(cur, depository_query, [tuple(x) for x in accounts_dfs['depository'].values])
            saved_counts['depository'] = len(accounts_dfs['depository'])

        # Save credit accounts
        if not accounts_dfs['credit'].empty:
            #print("\nDebug - Saving Credit Accounts:")
            #print("Columns in DataFrame:")
            #print(accounts_dfs['credit'].columns.tolist())
            
            # Ensure all required columns exist with correct order
            credit_columns = [
                'account_id', 'balance_current', 'balance_available', 'balance_limit',
                'last_statement_balance', 'last_statement_date', 'minimum_payment_amount',
                'next_payment_due_date', 'apr_percentage', 'apr_type',
                'balance_subject_to_apr', 'interest_charge_amount', 'pull_date'
            ]
            
            # Create DataFrame with all required columns, filling missing ones with None
            credit_df = accounts_dfs['credit'].reindex(columns=credit_columns)
            
            credit_query = """
                INSERT INTO credit_accounts (
                    account_id, balance_current, balance_available, balance_limit,
                    last_statement_balance, last_statement_date, minimum_payment_amount,
                    next_payment_due_date, apr_percentage, apr_type,
                    balance_subject_to_apr, interest_charge_amount, pull_date
                ) VALUES %s
                ON CONFLICT (account_id) 
                DO UPDATE SET 
                    balance_current = EXCLUDED.balance_current,
                    balance_available = EXCLUDED.balance_available,
                    balance_limit = EXCLUDED.balance_limit,
                    last_statement_balance = EXCLUDED.last_statement_balance,
                    last_statement_date = EXCLUDED.last_statement_date,
                    minimum_payment_amount = EXCLUDED.minimum_payment_amount,
                    next_payment_due_date = EXCLUDED.next_payment_due_date,
                    apr_percentage = EXCLUDED.apr_percentage,
                    apr_type = EXCLUDED.apr_type,
                    balance_subject_to_apr = EXCLUDED.balance_subject_to_apr,
                    interest_charge_amount = EXCLUDED.interest_charge_amount,
                    pull_date = EXCLUDED.pull_date
            """
            
            execute_values(cur, credit_query, [tuple(x) for x in credit_df.values])
            saved_counts['credit'] = len(accounts_dfs['credit'])

        # Save loan accounts
        if not accounts_dfs['loan'].empty:
            loan_query = """
                INSERT INTO loan_accounts (
                    account_id, balance_current, original_loan_amount, interest_rate, pull_date
                ) VALUES %s
                ON CONFLICT (account_id) 
                DO UPDATE SET 
                    balance_current = EXCLUDED.balance_current,
                    original_loan_amount = EXCLUDED.original_loan_amount,
                    interest_rate = EXCLUDED.interest_rate,
                    pull_date = EXCLUDED.pull_date
            """
            execute_values(cur, loan_query, [tuple(x) for x in accounts_dfs['loan'].values])
            saved_counts['loan'] = len(accounts_dfs['loan'])

        # Save investment accounts
        if not accounts_dfs['investment'].empty:
            investment_query = """
                INSERT INTO investment_accounts (
                    account_id, balance_current, pull_date
                ) VALUES %s
                ON CONFLICT (account_id) 
                DO UPDATE SET 
                    balance_current = EXCLUDED.balance_current,
                    pull_date = EXCLUDED.pull_date
            """
            execute_values(cur, investment_query, [tuple(x) for x in accounts_dfs['investment'].values])
            saved_counts['investment'] = len(accounts_dfs['investment'])

        # Verify data was saved
        cur.execute("SELECT COUNT(*) FROM accounts")
        account_count = cur.fetchone()[0]
        print(f"Verified {account_count} accounts in database")
        
        conn.commit()
        return saved_counts
        
    except Exception as e:
        print(f"Error saving accounts: {e}")
        if should_close:
            conn.rollback()
        raise
    finally:
        if should_close:
            cur.close()
            conn.close() 