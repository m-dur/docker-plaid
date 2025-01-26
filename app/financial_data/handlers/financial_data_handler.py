from datetime import datetime, timedelta
import pandas as pd
from ..processors.core.accounts_processor import process_accounts
from ..processors.reference.institutions_processor import process_institutions
from ..db_operations.core.accounts_db import save_accounts_to_db
from ..db_operations.reference.institutions_db import save_institutions_to_db
from app.plaid_service import (
    get_accounts, get_item, 
    get_institution_info, get_transactions_sync, get_saved_cursor, get_liabilities,
    save_cursor, create_plaid_client, delete_cursor, get_initial_transactions, get_item_details
)
from ..processors.core.transactions_processor import process_transactions
from ..db_operations.core.transactions_db import save_transactions_to_db
from ..db_operations.query_operations import execute_query
from app.config import Config
from app.financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import execute_values
import logging
from plaid.model.transactions_get_request import TransactionsGetRequest
import time
import plaid
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialDataHandler:
    def __init__(self):
        pass

    def serialize_item_details(self, item_dict):
        """Convert datetime objects to ISO format strings in item details"""
        def serialize_value(v):
            if isinstance(v, datetime):
                return v.isoformat() if v else None
            elif isinstance(v, dict):
                return {k: serialize_value(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [serialize_value(i) for i in v]
            return v
        
        # Handle None case
        if item_dict is None:
            return None
        
        return serialize_value(item_dict)

    def fetch_and_process_financial_data(self, access_token, conn=None, cur=None, item_info=None):
        print("\n=== Financial Data Processing Debug ===")
        
        # Initialize results dictionary at the start
        results = {
            'success': False,
            'error': None,
            'transactions': {
                'db_saved': False,
                'count': 0,
                'added': 0,
                'modified': 0,
                'removed': 0
            }
        }
        
        should_close = False
        if conn is None or cur is None:
            conn = get_db_connection()
            cur = conn.cursor()
            should_close = True
        
        try:
            # Get item details first
            print("\n=== Item Details ===")
            item_response = get_item_details(access_token)
            
            # Convert datetime objects to strings before JSON serialization
            if item_response:
                item_dict = item_response.to_dict()
                
                # Serialize all datetime objects in the response
                item_dict = self.serialize_item_details(item_dict)
                print(json.dumps(item_dict, indent=2))
            else:
                print("No item response received")
            
            if not item_response or not hasattr(item_response, 'item'):
                raise Exception("Failed to get item details")
            
            item = item_response.item
            status = item_response.status
            
            # Get institution info
            institution_info = get_institution_info(access_token)
            if not institution_info:
                raise Exception("Failed to get institution info")
            
            # Convert datetime strings to proper format
            created_at = item.created_at if hasattr(item, 'created_at') else None
            consent_expiration_time = item.consent_expiration_time if hasattr(item, 'consent_expiration_time') else None
            
            # Get transaction status timestamps
            last_successful_update = status.get('transactions', {}).get('last_successful_update') if status else None
            last_failed_update = status.get('transactions', {}).get('last_failed_update') if status else None
            last_webhook = status.get('last_webhook') if status else None
            
            # Convert all enum types to lists of strings
            available_products = [str(p) for p in item.available_products] if item.available_products else []
            billed_products = [str(p) for p in item.billed_products] if item.billed_products else []
            products = [str(p) for p in item.products] if item.products else []
            consented_products = [str(p) for p in item.consented_products] if item.consented_products else []
            consented_data_scopes = [str(s) for s in item.consented_data_scopes] if item.consented_data_scopes else []
            consented_use_cases = [str(u) for u in item.consented_use_cases] if item.consented_use_cases else []
            
            # Extract error information, converting enum to string if present
            if item.error:
                error_dict = item.error.to_dict() if hasattr(item.error, 'to_dict') else {
                    'error_type': item.error.error_type,
                    'error_code': item.error.error_code,
                    'error_message': item.error.error_message
                }
                error_type = str(error_dict.get('error_type'))
                error_code = str(error_dict.get('error_code'))
                error_message = error_dict.get('error_message')
            else:
                error_type = None
                error_code = None
                error_message = None

            # Insert/Update items table
            try:
                item_details = {
                    'item_id': item.item_id,
                    'institution_id': item.institution_id,
                    'institution_name': item.institution_name,
                    'available_products': available_products,
                    'billed_products': billed_products,
                    'products': products,
                    'consented_products': consented_products,
                    'consented_data_scopes': consented_data_scopes,
                    'consented_use_cases': consented_use_cases,
                    'consent_expiration_time': consent_expiration_time.isoformat() if consent_expiration_time else None,
                    'created_at': created_at.isoformat() if created_at else None,
                    'update_type': item.update_type,
                    'webhook': item.webhook,
                    'error_type': error_type,
                    'error_code': error_code,
                    'error_message': error_message,
                    'transactions_last_successful_update': last_successful_update.isoformat() if last_successful_update else None,
                    'transactions_last_failed_update': last_failed_update.isoformat() if last_failed_update else None,
                    'last_webhook_received_at': last_webhook.isoformat() if last_webhook else None
                }
                item_details = self.serialize_item_details(item_details)
                cur.execute("""
                    INSERT INTO items (
                        item_id,
                        institution_id,
                        institution_name,
                        available_products,
                        billed_products,
                        products,
                        consented_products,
                        consented_data_scopes,
                        consented_use_cases,
                        consent_expiration_time,
                        created_at,
                        update_type,
                        webhook,
                        error_type,
                        error_code,
                        error_message,
                        transactions_last_successful_update,
                        transactions_last_failed_update,
                        last_webhook_received_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (item_id) DO UPDATE SET
                        institution_id = EXCLUDED.institution_id,
                        institution_name = EXCLUDED.institution_name,
                        available_products = EXCLUDED.available_products,
                        billed_products = EXCLUDED.billed_products,
                        products = EXCLUDED.products,
                        consented_products = EXCLUDED.consented_products,
                        consented_data_scopes = EXCLUDED.consented_data_scopes,
                        consented_use_cases = EXCLUDED.consented_use_cases,
                        consent_expiration_time = EXCLUDED.consent_expiration_time,
                        created_at = EXCLUDED.created_at,
                        update_type = EXCLUDED.update_type,
                        webhook = EXCLUDED.webhook,
                        error_type = EXCLUDED.error_type,
                        error_code = EXCLUDED.error_code,
                        error_message = EXCLUDED.error_message,
                        transactions_last_successful_update = EXCLUDED.transactions_last_successful_update,
                        transactions_last_failed_update = EXCLUDED.transactions_last_failed_update,
                        last_webhook_received_at = EXCLUDED.last_webhook_received_at,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    item_details['item_id'],
                    item_details['institution_id'],
                    item_details['institution_name'],
                    item_details['available_products'],
                    item_details['billed_products'],
                    item_details['products'],
                    item_details['consented_products'],
                    item_details['consented_data_scopes'],
                    item_details['consented_use_cases'],
                    item_details['consent_expiration_time'],
                    item_details['created_at'],
                    item_details['update_type'],
                    item_details['webhook'],
                    item_details['error_type'],
                    item_details['error_code'],
                    item_details['error_message'],
                    item_details['transactions_last_successful_update'],
                    item_details['transactions_last_failed_update'],
                    item_details['last_webhook_received_at']
                ))
                conn.commit()
                print("✓ Successfully inserted/updated item details")
            except Exception as e:
                conn.rollback()
                logger.error(f"Database error: {str(e)}")
                raise
            
            # Continue with rest of processing
            if not item_info:
                try:
                    item_info = get_item(access_token)
                except Exception as e:
                    logger.error(f"Error getting item info: {e}")
                    results['error'] = str(e)
                    return results
            
            print("\n=== Financial Data Processing Debug ===")
            
            # 1. Get institution info first
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
            
            # Save and commit institution BEFORE any transaction operations
            records = []
            for record in institution_df.to_records(index=False):
                record_list = list(record)
                record_list[5] = bool(record_list[5])
                records.append(tuple(record_list))
            
            execute_values(cur, """
                INSERT INTO institutions (
                    id, name, type, status, url, oauth, refresh_interval, billed_products
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
            
            # Commit institution record immediately
            conn.commit()
            
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
            
            # 3. Process accounts and transactions first to get balances
            liabilities_response = get_liabilities(access_token)
            credit_cards = None
            if liabilities_response and hasattr(liabilities_response, 'liabilities'):
                credit_cards = liabilities_response.liabilities.credit
                print(f"Debug - Found {len(credit_cards)} credit cards in liabilities data")

            accounts = get_accounts(access_token)
            print(f"\nDebug - Accounts found: {len(accounts)}")
            
            # Get current accounts in database
            cur.execute("""
                SELECT account_id 
                FROM accounts 
                WHERE institution_id = %s
            """, (institution_info['institution_id'],))
            existing_account_ids = {row[0] for row in cur.fetchall()}

            # Get new accounts from Plaid
            plaid_accounts = get_accounts(access_token)
            plaid_account_ids = {acc.account_id for acc in plaid_accounts}

            # Check if there are any new accounts
            has_new_accounts = bool(plaid_account_ids - existing_account_ids)

            # Initialize transactions_response before the conditional block
            transactions_response = None
            
            # Get transactions based on whether this is initial load or update
            if item_info and (item_info.get('is_new_account') or has_new_accounts):
                print("New account(s) detected - fetching full transaction history")
                max_retries = 3
                retry_delay = 5  # Start with 5 seconds
                
                for attempt in range(max_retries):
                    try:
                        initial_response = get_initial_transactions(access_token)
                        print(f"Debug: Initial response cursor: {initial_response.get('next_cursor')}")
                        transactions_response = type('TransactionsResponse', (), {
                            'accounts': initial_response['accounts'],
                            'added': initial_response['transactions'],
                            'modified': [],
                            'removed': [],
                            'has_more': False,
                            'next_cursor': None
                        })()
                        break  # Success, exit retry loop
                    except Exception as e:
                        if 'PRODUCT_NOT_READY' in str(e) and attempt < max_retries - 1:
                            print(f"Product not ready, waiting {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            if attempt == max_retries - 1:
                                print("Max retries reached, falling back to sync endpoint")
                                transactions_response = get_transactions_sync(access_token, None)
                            break
            else:
                # If not a new account, use sync endpoint
                transactions_response = get_transactions_sync(access_token, None)

            # Add a check to ensure transactions_response is not None
            if transactions_response is None:
                raise Exception("Failed to fetch transactions from both initial and sync endpoints")

            # Get balances from transactions response
            bank_balances = transactions_response.accounts if hasattr(transactions_response, 'accounts') else []
            
            # Process accounts with balances from transactions sync
            accounts_dfs = process_accounts(accounts, bank_balances, credit_cards, {
                'institution_id': institution_info['institution_id']
            })
            
            # Save accounts using the same connection
            save_accounts_to_db(accounts_dfs, conn, cur)
            
            print(f"\nTransaction processing results:")
            print(f"- Added: {len(transactions_response.added)}")
            print(f"- Modified: {len(transactions_response.modified)}")
            print(f"- Removed: {len(transactions_response.removed)}")
            
            if transactions_response.added or transactions_response.modified:
                print(f"Debug: Processing transactions - Added: {len(transactions_response.added)}, Modified: {len(transactions_response.modified)}")
                if self.process_transactions(transactions_response, access_token):
                    results['transactions']['db_saved'] = True
                    results['transactions']['count'] = len(transactions_response.added) + len(transactions_response.modified)
                    results['transactions']['added'] = len(transactions_response.added)
                    results['transactions']['modified'] = len(transactions_response.modified)
                    results['transactions']['removed'] = len(transactions_response.removed)
                    print(f"Debug: Updated results after processing: {results}")
            
            # Save cursor regardless of whether it's an initial load or sync
            if hasattr(transactions_response, 'next_cursor') and transactions_response.next_cursor:
                print(f"Debug: Attempting to save cursor: {transactions_response.next_cursor[:10]}... for institution {institution_info['institution_id']}")
                try:
                    save_cursor(transactions_response.next_cursor, institution_info['institution_id'])
                    print(f"Debug: Successfully saved cursor for institution {institution_info['institution_id']}")
                except Exception as e:
                    print(f"Debug: Error saving cursor: {str(e)}")
            else:
                print("Debug: No cursor available to save")
            
            # Commit all changes
            conn.commit()
            
            results['success'] = True
            print(f"Debug: Final results state: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in main processing: {e}")
            results['error'] = str(e)
            return results
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
                save_cursor(transactions_response.next_cursor, institution_id)
            
            return results
            
        except Exception as e:
            print(f"Error processing transaction updates: {e}")
            raise

    def process_transactions(self, transactions_response, access_token):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            values = []
            
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
                # Get initial category and group from mappings
                saved_category = category_mappings.get(transaction.name)
                saved_group = group_mappings.get(transaction.name)
                
                # Apply Amazon Store Card logic
                if (hasattr(transaction, 'account_id') and 
                    (transaction.account_id == '13J3y079ewiVvXdkA68oikaaZB81zyha6KOwn' or
                     getattr(transaction, 'account_name', '') == 'Prime Store Card')):
                    # Only override if it's not "Amazon Prime"
                    if transaction.name != "Amazon Prime":
                        saved_category = "Shopping"
                        saved_group = "Misc"
                
                values.append((
                    transaction.transaction_id,
                    transaction.account_id,
                    transaction.amount,
                    transaction.date,
                    transaction.name,
                    saved_category,  # Now includes Amazon Store Card logic
                    transaction.merchant_name,
                    saved_group,    # Now includes Amazon Store Card logic
                    transaction.payment_channel,
                    transaction.authorized_datetime,
                    datetime.now().date()
                ))
            
            if values:
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
                
                # Update any existing Amazon Store Card transactions
                cur.execute("""
                    UPDATE transactions 
                    SET category = 'Shopping',
                        group_name = 'Misc'
                    WHERE account_id = '13J3y079ewiVvXdkA68oikaaZB81zyha6KOwn'
                    AND name != 'Amazon Prime'
                """)
                
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

 
        
    def fetch_initial_transactions(self, access_token, institution_id):
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Initialize transactions_response
            transactions_response = None
            
            # Get new accounts from Plaid
            plaid_accounts = get_accounts(access_token)
            print(f"Debug - Accounts found: {len(plaid_accounts)}")
            
            # Try to get liabilities, but handle gracefully if not available
            try:
                liabilities = get_liabilities(access_token)
            except plaid.ApiException as e:
                if 'NO_LIABILITY_ACCOUNTS' in str(e):
                    print("No liability accounts available - continuing")
                else:
                    print(f"Plaid API error getting liabilities: {str(e)}")
            except Exception as e:
                print(f"Unexpected error getting liabilities: {str(e)}")
            
            # Try transactions/get first with retries
            max_retries = 3
            retry_delay = 5  # Start with 5 seconds
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    transactions_response = get_initial_transactions(access_token)
                    
                    # Create a response object if we got raw data
                    if isinstance(transactions_response, dict):
                        transactions_response = type('TransactionsResponse', (), {
                            'transactions': transactions_response.get('transactions', []),
                            'added': transactions_response.get('transactions', []),
                            'modified': [],
                            'removed': [],
                            'has_more': transactions_response.get('has_more', False),
                            'next_cursor': transactions_response.get('next_cursor')
                        })()
                    
                    if transactions_response:
                        return self.process_transactions(transactions_response, access_token)
                    
                except Exception as e:
                    last_error = e
                    if 'PRODUCT_NOT_READY' in str(e) and attempt < max_retries - 1:
                        print(f"Product not ready, waiting {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    print(f"Error fetching transactions: {str(e)}")
            
            # If we got here, all attempts failed
            if last_error:
                print(f"All attempts failed. Last error: {last_error}")
                # Try sync endpoint as last resort
                try:
                    return self.process_transactions_sync(access_token, institution_id)
                except Exception as sync_error:
                    print(f"Sync endpoint also failed: {sync_error}")
                    return False
            
            return True  # No transactions to process
            
        finally:
            cur.close()
            conn.close()

    def cleanup_institution_data(self, institution_id):
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("BEGIN")
            
            # Get all access token IDs for this institution
            cur.execute("""
                SELECT token_id 
                FROM access_tokens 
                WHERE institution_id = %s
            """, (institution_id,))
            token_ids = [row[0] for row in cur.fetchall()]
            
            if token_ids:
                # Delete plaid API calls first using IN clause
                cur.execute("""
                    DELETE FROM plaid_api_calls 
                    WHERE access_token_id = ANY(%s)
                """, (token_ids,))
            
            # Delete transactions
            cur.execute("""
                DELETE FROM transactions 
                WHERE account_id IN (
                    SELECT account_id 
                    FROM accounts 
                    WHERE institution_id = %s
                )
            """, (institution_id,))
            
            # Delete account history
            cur.execute("""
                DELETE FROM account_history 
                WHERE institution_id = %s
            """, (institution_id,))
            
            # Delete cursor
            cur.execute("DELETE FROM institution_cursors WHERE institution_id = %s", (institution_id,))
            
            # Delete accounts
            cur.execute("""
                DELETE FROM accounts 
                WHERE institution_id = %s
            """, (institution_id,))
            
            # Finally delete access token
            cur.execute("""
                DELETE FROM access_tokens 
                WHERE institution_id = %s
            """, (institution_id,))
            
            cur.execute("COMMIT")
            
        except Exception as e:
            cur.execute("ROLLBACK")
            print(f"Error during cleanup: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()

    def cleanup_failed_refresh(self, institution_id, current_pull_date, cur):
        try:
            # Only delete data from the current refresh attempt
            cur.execute("BEGIN")
            
            # Delete only current pull cycle's data
            cur.execute("""
                DELETE FROM account_history 
                WHERE institution_id = %s AND pull_date = %s
            """, (institution_id, current_pull_date))
            
            # Delete only current pull cycle's transactions
            cur.execute("""
                DELETE FROM transactions 
                WHERE account_id IN (
                    SELECT account_id FROM accounts 
                    WHERE institution_id = %s
                ) AND pull_date = %s
            """, (institution_id, current_pull_date))
            
            cur.execute("COMMIT")
            
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")
            cur.execute("ROLLBACK")
