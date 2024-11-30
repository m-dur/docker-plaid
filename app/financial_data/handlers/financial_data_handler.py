from datetime import datetime, timedelta
import pandas as pd
from ..processors.core.accounts_processor import process_accounts
from ..processors.reference.institutions_processor import process_institutions
from ..db_operations.core.accounts_db import save_accounts_to_db
from ..db_operations.reference.institutions_db import save_institutions_to_db
from plaid_service import (
    get_accounts, get_bank_balances, get_item, 
    get_institution_info, get_transactions_sync, get_saved_cursor, get_liabilities,
    save_cursor, create_plaid_client, delete_cursor
)
from ..processors.core.transactions_processor import process_transactions
from ..db_operations.core.transactions_db import save_transactions_to_db
from ..db_operations.query_operations import execute_query
from config import Config
from financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import execute_values
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialDataHandler:
    def __init__(self):
        pass

    def fetch_and_process_financial_data(self, access_token, conn=None, cur=None, item_info=None):
        print("\n=== Financial Data Processing Debug ===")
        
        should_close = False
        if conn is None or cur is None:
            conn = get_db_connection()
            cur = conn.cursor()
            should_close = True
            cur.execute("BEGIN")  # Start transaction
        
        # Initialize results dictionary
        results = {
            'success': False,
            'transactions': {
                'db_saved': False,
                'count': 0,
                'added': 0,
                'modified': 0,
                'removed': 0
            }
        }
        
        try:
            # Check if transactions table is empty for this institution
            if item_info:
                institution_id = item_info.get('institution_id')
            else:
                item_info = get_item(access_token)
                institution_id = item_info['institution_id']
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM transactions t
                JOIN accounts a ON t.account_id = a.account_id
                WHERE a.institution_id = %s
            """, (institution_id,))
            transaction_count = cur.fetchone()[0]
            
            # If no transactions exist for this institution, delete the cursor to force full sync
            if transaction_count == 0:
                print(f"No transactions found for institution {institution_id} - forcing full sync")
                delete_cursor(institution_id)
                current_cursor = None
            else:
                current_cursor = get_saved_cursor(institution_id)
                print(f"Current cursor before sync: {current_cursor}")
            
            # 2. Get and save institution info
            if not item_info:
                item_info = get_item(access_token)
            
            institution_info = get_institution_info(access_token)
            institution_df = process_institutions([{
                'institution_id': institution_info['institution_id'],
                'name': institution_info['name'],
                'products': institution_info.get('products', []),
                'oauth': institution_info.get('oauth', False),
                'status': institution_info.get('status', 'active'),
                'url': institution_info.get('url'),
                'refresh_interval': institution_info.get('refresh_interval')
            }])
            
            # Save institution using the same connection
            records = []
            for record in institution_df.to_records(index=False):
                record_list = list(record)
                record_list[5] = bool(record_list[5])
                records.append(tuple(record_list))
            
            execute_values(cur, """
                INSERT INTO institutions (
                    id, 
                    name, 
                    type,
                    status,
                    url,
                    oauth,
                    refresh_interval,
                    billed_products
                )
                VALUES %s
                ON CONFLICT (id) DO UPDATE SET 
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    status = EXCLUDED.status,
                    url = EXCLUDED.url,
                    oauth = EXCLUDED.oauth,
                    refresh_interval = EXCLUDED.refresh_interval,
                    billed_products = EXCLUDED.billed_products,
                    last_refresh = CURRENT_TIMESTAMP
            """, records)
            
            # 3. Process accounts
            accounts = get_accounts(access_token)
            bank_balances = get_bank_balances(access_token)
            student_loans, credit_cards = get_liabilities(access_token)
            
            accounts_dfs = process_accounts(accounts, bank_balances, credit_cards, {
                'institution_id': institution_info['institution_id']
            })
            
            # Save accounts using the same connection
            save_accounts_to_db(accounts_dfs, conn, cur)
            
            # 4. Process transactions
            # Only get current cursor if this isn't a new account
            if item_info and item_info.get('is_new_account'):
                print("New account detected - starting fresh transaction sync")
                transactions_response = get_transactions_sync(access_token, None, institution_id)
            else:
                # Get current cursor before sync for existing accounts
                current_cursor = get_saved_cursor(institution_id)
                print(f"Current cursor before sync: {current_cursor}")
                transactions_response = get_transactions_sync(access_token, current_cursor, institution_id)
            
            print(f"\nTransaction processing results:")
            print(f"- Added: {len(transactions_response.added)}")
            print(f"- Modified: {len(transactions_response.modified)}")
            print(f"- Removed: {len(transactions_response.removed)}")
            
            if transactions_response.added or transactions_response.modified:
                # Use the direct process_transactions method instead
                if self.process_transactions(transactions_response, access_token):
                    results['transactions']['db_saved'] = True
                    results['transactions']['count'] = len(transactions_response.added) + len(transactions_response.modified)
                    results['transactions']['added'] = len(transactions_response.added)
                    results['transactions']['modified'] = len(transactions_response.modified)
                    results['transactions']['removed'] = len(transactions_response.removed)
            
            # Save the new cursor
            if transactions_response.next_cursor:
                save_cursor(transactions_response.next_cursor, institution_id)
            
            # Commit all changes
            conn.commit()
            
            results['success'] = True
            return results
            
        except Exception as e:
            if should_close:
                cur.execute("ROLLBACK")  # Rollback all changes
                
                # Clean up any partial data
                try:
                    if item_info:
                        institution_id = item_info.get('institution_id')
                    else:
                        item_info = get_item(access_token)
                        institution_id = item_info['institution_id']
                    
                    current_pull_date = datetime.now().date()
                    
                    # Delete only data from current refresh cycle
                    cur.execute("BEGIN")
                    
                    # Delete transactions from current pull cycle
                    cur.execute("""
                        DELETE FROM transactions 
                        WHERE account_id IN (
                            SELECT account_id FROM accounts 
                            WHERE institution_id = %s
                        ) AND pull_date = %s
                    """, (institution_id, current_pull_date))
                    
                    # Delete account-specific data from current pull cycle
                    for table in ['depository_accounts', 'credit_accounts', 'loan_accounts', 'investment_accounts']:
                        cur.execute(f"""
                            DELETE FROM {table} 
                            WHERE account_id IN (
                                SELECT account_id FROM accounts 
                                WHERE institution_id = %s AND pull_date = %s
                            )
                        """, (institution_id, current_pull_date))
                    
                    # Delete accounts from current pull cycle
                    cur.execute("""
                        DELETE FROM accounts 
                        WHERE institution_id = %s AND pull_date = %s
                    """, (institution_id, current_pull_date))
                    
                    # For institutions table, only delete if this is the first pull
                    cur.execute("""
                        DELETE FROM institutions 
                        WHERE id = %s 
                        AND NOT EXISTS (
                            SELECT 1 FROM accounts 
                            WHERE institution_id = %s AND pull_date < %s
                        )
                    """, (institution_id, institution_id, current_pull_date))
                    
                    cur.execute("COMMIT")
                    
                except Exception as cleanup_error:
                    logger.error(f"Error during cleanup: {cleanup_error}")
                    cur.execute("ROLLBACK")
                
            raise e
        finally:
            if should_close and conn:
                conn.close()

    def process_transaction_updates(self, access_token):
        """Handle only transaction updates from webhook"""
        results = {
            'transactions': {
                'db_saved': False,
                'count': 0,
                'added': 0,
                'modified': 0,
                'removed': 0
            }
        }
        
        try:
            # Check if transactions table is empty
            row_count = execute_query("SELECT COUNT(*) FROM transactions")[0]
            
            # If no transactions exist, delete the cursor to force full sync
            if row_count == 0:
                delete_cursor()
            
            # Get transactions using sync endpoint with saved cursor
            cursor = get_saved_cursor()
            transactions_response = get_transactions_sync(access_token, cursor)
            
            # Process added and modified transactions
            all_transactions = []
            if transactions_response.added:
                all_transactions.extend(transactions_response.added)
            if transactions_response.modified:
                all_transactions.extend(transactions_response.modified)
                
            if all_transactions:
                transactions_df = process_transactions(all_transactions)
                saved_transactions = save_transactions_to_db(transactions_df)
                
                # Update transaction results
                results['transactions']['db_saved'] = True
                results['transactions']['count'] = saved_transactions
                results['transactions']['added'] = len(transactions_response.added)
                results['transactions']['modified'] = len(transactions_response.modified)
                results['transactions']['removed'] = len(transactions_response.removed)
            
            # Save the new cursor
            if transactions_response.next_cursor:
                save_cursor(transactions_response.next_cursor)
            
            return results
            
        except Exception as e:
            print(f"Error processing transaction updates: {e}")
            raise

    def process_transactions(self, transactions_response, access_token):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            values = []  # Initialize values list
            
            # Get all existing category mappings
            cur.execute("SELECT transaction_name, category FROM category_mappings")
            category_mappings = dict(cur.fetchall())
            
            # Get all existing group mappings
            cur.execute("SELECT transaction_name, group_name FROM group_mappings")
            group_mappings = dict(cur.fetchall())
            
            # Process both added and modified transactions
            all_transactions = []
            if transactions_response.added:
                all_transactions.extend(transactions_response.added)
            if transactions_response.modified:
                all_transactions.extend(transactions_response.modified)
            
            # Process transactions with mapped categories
            for transaction in all_transactions:
                # Check if we have a saved category for this transaction name
                saved_category = category_mappings.get(transaction.name)
                saved_group = group_mappings.get(transaction.name)
                
                values.append((
                    transaction.transaction_id,
                    transaction.account_id,
                    transaction.amount,
                    transaction.date,
                    transaction.name,
                    saved_category,  # Use saved category from mappings
                    transaction.merchant_name,
                    saved_group,    # Use saved group from mappings
                    transaction.payment_channel,
                    transaction.authorized_datetime,
                    datetime.now().date()
                ))
            
            if values:  # Only try to save if we have transactions
                execute_values(cur, """
                    INSERT INTO transactions (
                        transaction_id, account_id, amount, date, name,
                        category, merchant_name, group_name, payment_channel,
                        authorized_datetime, pull_date
                    ) VALUES %s
                    ON CONFLICT (transaction_id) DO UPDATE SET
                        amount = EXCLUDED.amount,
                        category = EXCLUDED.category,
                        merchant_name = EXCLUDED.merchant_name,
                        group_name = EXCLUDED.group_name,
                        payment_channel = EXCLUDED.payment_channel,
                        authorized_datetime = EXCLUDED.authorized_datetime,
                        pull_date = EXCLUDED.pull_date
                """, values)
                
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error processing transactions: {str(e)}")
            return False
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
