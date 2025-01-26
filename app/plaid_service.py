import json
import os
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.credit_card_liability import CreditCardLiability
from datetime import datetime, timedelta
from app.config import Config
from plaid.api_client import Configuration, ApiClient
import time
from flask import session
from plaid.model.link_token_create_request_auth import LinkTokenCreateRequestAuth
from plaid.model.liabilities_get_request_options import LiabilitiesGetRequestOptions
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.sandbox_item_fire_webhook_request import SandboxItemFireWebhookRequest
from plaid.model.webhook_type import WebhookType
from app.utils.api_tracker import track_plaid_call
from app.financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import RealDictCursor
from plaid.model.transactions_get_request import TransactionsGetRequest



def save_cursor(cursor, institution_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check if this is first sync
        cur.execute("""
            INSERT INTO institution_cursors 
                (institution_id, cursor, last_sync_at, sync_status, first_sync_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP, 'completed', CURRENT_TIMESTAMP)
            ON CONFLICT (institution_id) 
            DO UPDATE SET 
                cursor = EXCLUDED.cursor,
                last_sync_at = CURRENT_TIMESTAMP,
                sync_status = 'completed'
            RETURNING (xmax = 0) as is_insert
        """, (institution_id, cursor))
        is_new = cur.fetchone()[0]
        conn.commit()
        
        if is_new:
            print(f"✓ Initial cursor created for institution {institution_id}")
        else:
            print(f"✓ Cursor updated for institution {institution_id}")
    except Exception as e:
        print(f"❌ Error saving cursor: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def get_saved_cursor(institution_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT cursor, last_sync_at 
            FROM institution_cursors 
            WHERE institution_id = %s
        """, (institution_id,))
        result = cur.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"❌ Error retrieving cursor: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def delete_cursor(institution_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE institution_cursors 
            SET cursor = NULL, 
                sync_status = 'pending',
                last_sync_at = CURRENT_TIMESTAMP 
            WHERE institution_id = %s
        """, (institution_id,))
        conn.commit()
        print(f"✓ Cursor reset for institution {institution_id}")
    except Exception as e:
        print(f"❌ Error deleting cursor: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def save_access_token(access_token, item_id, institution_id, institution_name):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Update institutions table
        cur.execute("""
            INSERT INTO institutions (id, name)
            VALUES (%s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
        """, (institution_id, institution_name))
        
        # Save access token
        cur.execute("""
            INSERT INTO access_tokens (institution_id, access_token, item_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (institution_id) 
            DO UPDATE SET 
                access_token = EXCLUDED.access_token,
                item_id = EXCLUDED.item_id,
                last_updated = CURRENT_TIMESTAMP
        """, (institution_id, access_token, item_id))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def get_saved_access_tokens():
    """Get all saved access tokens from database"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                at.institution_id,
                at.access_token,
                at.item_id,
                i.name as institution_name
            FROM access_tokens at
            JOIN institutions i ON at.institution_id = i.id
        """)
        results = cur.fetchall()
        
        # Convert to dictionary format for backward compatibility
        tokens_data = {}
        for row in results:
            tokens_data[row['institution_id']] = {
                'access_token': row['access_token'],
                'institution_id': row['institution_id'],
                'institution_name': row['institution_name'],
                'item_id': row['item_id']
            }
        
        return tokens_data
    except Exception as e:
        print(f"Error getting saved access tokens: {e}")
        return {}
    finally:
        cur.close()
        conn.close()

@track_plaid_call(product='auth', operation='exchange_token')
def get_access_token(public_token):
    client = create_plaid_client()
    exchange_request = ItemPublicTokenExchangeRequest(
        public_token=public_token
    )
    exchange_response = client.item_public_token_exchange(exchange_request)
    return exchange_response['access_token']

def create_plaid_client():
    client_id = Config.PLAID_CLIENT_ID
    secret = Config.PLAID_SECRET
    environment = Config.PLAID_ENV

    if not all([client_id, secret, environment]):
        raise ValueError("Missing Plaid configuration. Please check your .env file.")

    # Map environment string to Plaid environment
    plaid_env_map = {
        'sandbox': plaid.Environment.Sandbox,
        'production': plaid.Environment.Production
    }

    if environment.lower() not in plaid_env_map:
        raise ValueError(f"Invalid PLAID_ENV value: {environment}. Must be one of: {', '.join(plaid_env_map.keys())}")

    configuration = Configuration(
        host=plaid_env_map[environment.lower()],
        api_key={
            'clientId': str(client_id),
            'secret': str(secret),
        }
    )

    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

@track_plaid_call(product='transactions', operation='sync')
def get_transactions_sync(access_token, cursor=None, institution_id=None, retry_count=3, initial_delay=2):
    client = create_plaid_client()
    
    request_dict = {
        "access_token": access_token,
        "options": {
            "include_personal_finance_category": True,
            "include_original_description": True,
            "days_requested": 730  # Request maximum 2 years
        }
    }
    
    if cursor is not None and cursor.strip():
        request_dict["cursor"] = cursor.strip()
        # For incremental updates, we don't need to specify days_requested
        del request_dict["options"]["days_requested"]
    
    request = TransactionsSyncRequest(**request_dict)
    
    try:
        all_added = []
        all_modified = []
        all_removed = []
        
        while True:
            response = client.transactions_sync(request)
            
            all_added.extend(response.added)
            all_modified.extend(response.modified)
            all_removed.extend(response.removed)
            
            if not response.has_more:
                break
                
            request_dict["cursor"] = response.next_cursor
            request = TransactionsSyncRequest(**request_dict)
        
        # Create composite response with all transactions
        response.added = all_added
        response.modified = all_modified
        response.removed = all_removed
        
        return response
        
    except Exception as e:
        print(f"❌ Error in transaction sync: {str(e)}")
        raise

@track_plaid_call(product='link', operation='create_token')
def create_and_store_link_token():
    """Create and store a link token in the session"""
    print("\n=== Starting Link Token Creation ===")
    try:
        client = create_plaid_client()
        
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],
            required_if_supported_products=[
                Products("liabilities"),
                Products("investments")
            ],
            client_name="Financial Data Fetcher",
            country_codes=[CountryCode('US')],
            language='en',
            user=LinkTokenCreateRequestUser(
                client_user_id=str(time.time())
            ),
            transactions={
                "days_requested": 360
            }
        )
        
        print("Sending link token creation request to Plaid...")
        response = client.link_token_create(request)
        token = response['link_token']
        
        print(f"✓ Link token created successfully: {token[:10]}...")
        session['link_token'] = token
        
        return token
    except plaid.ApiException as e:
        print(f"❌ Error creating link token: {e}")
        print(f"Error code: {e.code}")
        print(f"Error message: {e.message}")
        return None

def save_link_token(token):
    """Save link token to file"""
    with open('link_token.json', 'w') as f:
        json.dump({'link_token': token}, f)

@track_plaid_call(product='accounts', operation='get')
def get_accounts(access_token):
    """Get accounts from Plaid"""
    try:
        client = create_plaid_client()
        request = AccountsGetRequest(access_token=access_token)
        response = client.accounts_get(request)
        return response.accounts
    except Exception as e:
        print(f"Error getting accounts: {e}")
        return []

@track_plaid_call(product='accounts', operation='get_balances')
def get_bank_balances(access_token):
    """Get bank balances from transactions sync endpoint"""
    try:
        # Get institution_id from access token
        item = get_item(access_token)
        institution_id = item.institution_id
        
        # Get fresh data from transactions sync
        response = get_transactions_sync(access_token, None, institution_id)
        return response.accounts if hasattr(response, 'accounts') else []
        
    except Exception as e:
        print(f"Error getting balances: {e}")
        return []

@track_plaid_call(product='liabilities', operation='get')
def get_liabilities(access_token):
    client = create_plaid_client()
    try:
        print("\nDebug - Fetching liabilities data...")
        request = LiabilitiesGetRequest(
            access_token=access_token
        )
        response = client.liabilities_get(request)
        print(f"Debug - Liabilities response: {response.to_dict()}")
        return response
    except Exception as e:
        print(f"Plaid API error getting liabilities: {e}")
        return None

@track_plaid_call(product='investments', operation='get_holdings')
def get_investments(access_token):
    client = create_plaid_client()
    request = InvestmentsHoldingsGetRequest(access_token=access_token)
    response = client.investments_holdings_get(request)
    return response.holdings, response.securities, response.accounts

@track_plaid_call(product='institutions', operation='get_by_id')
def get_institution_info(access_token):
    """Get institution info from Plaid"""
    try:
        client = create_plaid_client()
        
        item_request = ItemGetRequest(access_token=access_token)
        item_response = client.item_get(item_request)
        institution_id = item_response.item.institution_id
        
        request = InstitutionsGetByIdRequest(
            institution_id=institution_id,
            country_codes=[CountryCode('US')]
        )
        response = client.institutions_get_by_id(request)
        
        if not response or not response.institution:
            raise Exception("No institution data received from Plaid")
            
        institution = response.institution
        
        products_list = [str(product) for product in institution.products]
        
        institution_info = {
            'institution_id': institution.institution_id,
            'name': institution.name,
            'products': products_list,
            'oauth': getattr(institution, 'oauth', False),
            'status': 'UNKNOWN',
            'billed_products': [str(product) for product in getattr(institution, 'billed_products', [])]
        }
        
        if hasattr(institution, 'url'):
            institution_info['url'] = institution.url
        if hasattr(institution, 'refresh_interval'):
            institution_info['refresh_interval'] = institution.refresh_interval
            
        if hasattr(institution, 'status') and institution.status is not None:
            if hasattr(institution.status, 'item_logins') and institution.status.item_logins is not None:
                institution_info['status'] = ('HEALTHY' 
                    if institution.status.item_logins.status == 'HEALTHY' 
                    else 'DEGRADED')
        
        return institution_info
        
    except Exception as e:
        print(f"Error getting institution info: {str(e)}")
        raise Exception(f"Failed to get institution info: {str(e)}")

@track_plaid_call(product='item', operation='get')
def get_item(access_token):
    """Get item info from Plaid"""
    try:
        client = create_plaid_client()
        request = ItemGetRequest(access_token=access_token)
        response = client.item_get(request)
        return response.item
    except Exception as e:
        print(f"Error getting item: {e}")
        return None

def get_access_token_by_item_id(item_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT access_token 
            FROM access_tokens 
            WHERE item_id = %s
        """, (item_id,))
        result = cur.fetchone()
        return result[0] if result else None
    finally:
        cur.close()
        conn.close()

@track_plaid_call(product='sandbox', operation='fire_webhook')
def fire_sandbox_webhook(access_token):
    """Fire a test webhook in sandbox mode"""
    client = create_plaid_client()
    
    try:
        item = get_item(access_token)
        if not item:
            raise Exception("Could not get item information")
            
        webhook_type = WebhookType("TRANSACTIONS")
        request = SandboxItemFireWebhookRequest(
            access_token=access_token,
            webhook_code="SYNC_UPDATES_AVAILABLE",
            webhook_type=webhook_type
        )
        response = client.sandbox_item_fire_webhook(request)
        print(f"Webhook fired response: {response}")
        
        print(f"Test with: curl -X POST {Config.APP_URL}/webhook \\")
        print('  -H "Content-Type: application/json" \\')
        print(f'  -d \'{{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": "{item.item_id}"}}\'')
        
        return response
    except Exception as e:
        print(f"Error firing sandbox webhook: {e}")
        raise

def save_account_balances_cache(accounts, institution_id):
    """Cache account balances from transactions sync response"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Store balances with timestamp
        cur.execute("""
            INSERT INTO account_balances_cache (
                institution_id,
                account_id,
                current_balance,
                available_balance,
                limit_balance,
                cached_at
            ) VALUES %s
            ON CONFLICT (account_id) DO UPDATE SET
                current_balance = EXCLUDED.current_balance,
                available_balance = EXCLUDED.available_balance,
                limit_balance = EXCLUDED.limit_balance,
                cached_at = EXCLUDED.cached_at
        """, [(
            institution_id,
            account.account_id,
            account.balances.current,
            account.balances.available,
            account.balances.limit,
            datetime.now()
        ) for account in accounts])
        
        conn.commit()
    except Exception as e:
        print(f"Error caching account balances: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def refresh_full_history(institution_id, access_token):
    # Delete existing cursor
    delete_cursor(institution_id)
    
    # Perform fresh sync
    return get_transactions_sync(access_token, None, institution_id)

@track_plaid_call(product='transactions', operation='get')
def get_initial_transactions(access_token, start_date=None, end_date=None, retry_count=3, retry_delay=2):
    client = create_plaid_client()
    
    # Default to 2 years of history if no dates specified
    if not start_date:
        start_date = (datetime.now() - timedelta(days=730)).date()
    if not end_date:
        end_date = datetime.now().date()
    
    try:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options={
                "include_personal_finance_category": True,
                "include_original_description": True,
                "count": 500  # Add explicit count
            }
        )
        
        while retry_count > 0:
            try:
                all_transactions = []
                total_transactions = None
                offset = 0
                
                while total_transactions is None or len(all_transactions) < total_transactions:
                    request.options['offset'] = offset
                    response = client.transactions_get(request)
                    
                    if total_transactions is None:
                        total_transactions = response.total_transactions
                        print(f"Total transactions to fetch: {total_transactions}")
                    
                    all_transactions.extend(response.transactions)
                    offset += len(response.transactions)
                    print(f"Fetched {len(all_transactions)} of {total_transactions} transactions")
                    
                    if len(response.transactions) == 0:
                        break
                
                return {
                    'accounts': response.accounts,
                    'transactions': all_transactions
                }
                
            except Exception as e:
                if 'PRODUCT_NOT_READY' in str(e):
                    retry_count -= 1
                    if retry_count > 0:
                        print(f"Product not ready, retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                raise
                
    except Exception as e:
        print(f"❌ Error getting initial transactions: {str(e)}")
        raise

@track_plaid_call(product='item', operation='get')
def get_item_details(access_token):
    """Get detailed item info from Plaid and print all available fields"""
    try:
        client = create_plaid_client()
        request = ItemGetRequest(access_token=access_token)
        response = client.item_get(request)
        
        # Convert the entire response to a dictionary
        response_dict = response.to_dict()
        
        print("\n=== Item Details ===")
        print(json.dumps(response_dict, indent=2, default=str))
        return response
        
    except Exception as e:
        print(f"Error getting item details: {e}")
        return None
