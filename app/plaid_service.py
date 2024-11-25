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
from config import Config
from plaid.api_client import Configuration, ApiClient
import time
from flask import session
from plaid.model.link_token_create_request_auth import LinkTokenCreateRequestAuth
from plaid.model.liabilities_get_request_options import LiabilitiesGetRequestOptions
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.sandbox_item_fire_webhook_request import SandboxItemFireWebhookRequest
from plaid.model.webhook_type import WebhookType

CURSOR_FILE = 'cursor.json'

def save_cursor(cursor):
    try:
        with open(CURSOR_FILE, 'w') as f:
            json.dump({'cursor': cursor}, f)
        print(f"Cursor saved successfully: {cursor}")
    except IOError as e:
        print(f"Error saving cursor: {e}")

def get_saved_cursor():
    if not os.path.exists(CURSOR_FILE):
        print("Cursor file does not exist. Returning None.")
        return None
    try:
        with open(CURSOR_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                print("Cursor file is empty. Returning None.")
                return None
            data = json.loads(content)
            cursor = data.get('cursor')
            print(f"Retrieved cursor: {cursor}")
            return cursor
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading cursor: {e}")
        return None

def delete_cursor():
    if os.path.exists(CURSOR_FILE):
        os.remove(CURSOR_FILE)
        print("Cursor file deleted.")
    else:
        print("Cursor file does not exist.")

def save_access_token(access_token, item_id, institution_id, institution_name):
    try:
        with open('access_tokens.json', 'r') as f:
            tokens = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tokens = {}
    
    # Add connection timestamp if this is a new institution
    if institution_id not in tokens:
        connected_at = datetime.now().isoformat()
    else:
        connected_at = tokens[institution_id].get('connected_at', datetime.now().isoformat())
    
    tokens[institution_id] = {
        'access_token': access_token,
        'item_id': item_id,
        'institution_id': institution_id,
        'institution_name': institution_name,
        'created_at': datetime.now().isoformat(),
        'connected_at': connected_at
    }
    
    with open('access_tokens.json', 'w') as f:
        json.dump(tokens, f)

def get_saved_access_tokens():
    try:
        with open('access_tokens.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
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

def get_transactions_sync(access_token, cursor=None):
    """Fetch transactions using the sync endpoint"""
    client = create_plaid_client()
    
    request_dict = {
        "access_token": access_token
    }
    
    if cursor is not None and cursor.strip():
        request_dict["cursor"] = cursor.strip()
    
    request = TransactionsSyncRequest(**request_dict)
    
    try:
        response = client.transactions_sync(request)
        # Save the new cursor after successful sync
        if response.next_cursor:
            save_cursor(response.next_cursor)
        return response
    except plaid.ApiException as e:
        error_response = json.loads(e.body)
        print(f"Error syncing transactions: {error_response.get('error_code')} - {error_response.get('error_message')}")
        raise
    except Exception as e:
        print(f"Unexpected error syncing transactions: {e}")
        raise

def save_cursor(cursor):
    with open('cursor.json', 'w') as f:
        json.dump({'cursor': cursor}, f)

def get_saved_cursor():
    try:
        with open('cursor.json', 'r') as f:
            data = json.load(f)
            return data.get('cursor')
    except FileNotFoundError:
        return None

def create_and_store_link_token():
    """Create and store a link token in the session"""
    try:
        client = create_plaid_client()
        webhook_url = f"{Config.APP_URL}/webhook"  # Add webhook URL
        
        request = LinkTokenCreateRequest(
            products=[Products("transactions")],  # Core product
            required_if_supported_products=[
                Products("liabilities"),
                Products("investments")
            ],
            client_name="Financial Data Fetcher",
            country_codes=[CountryCode('US')],
            language='en',
            webhook=webhook_url,  # Add webhook URL here
            user=LinkTokenCreateRequestUser(
                client_user_id=str(time.time())
            )
        )
        response = client.link_token_create(request)
        token = response['link_token']
        
        # Store in session and file
        session['link_token'] = token
        save_link_token(token)
        
        return token
    except plaid.ApiException as e:
        print(f"Error creating link token: {e}")
        return None

def save_link_token(token):
    """Save link token to file"""
    with open('link_token.json', 'w') as f:
        json.dump({'link_token': token}, f)

def get_stored_link_token():
    """Get link token from session or file"""
    token = session.get('link_token')
    if not token:
        try:
            with open('link_token.json', 'r') as f:
                data = json.load(f)
                token = data.get('link_token')
        except (FileNotFoundError, json.JSONDecodeError):
            token = None
    return token

def _get_accounts_internal(access_token):
    client = create_plaid_client()
    request = AccountsGetRequest(access_token=access_token)
    response = client.accounts_get(request)
    return response['accounts']

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

def get_account_balances(access_token):
    client = create_plaid_client()
    request = AccountsBalanceGetRequest(access_token=access_token)
    response = client.accounts_balance_get(request)
    return response['accounts']

def get_bank_balances(access_token):
    """Get bank balances from Plaid"""
    try:
        client = create_plaid_client()
        request = AccountsBalanceGetRequest(access_token=access_token)
        response = client.accounts_balance_get(request)
        return response.accounts
    except Exception as e:
        print(f"Error getting balances: {e}")
        return []

def get_liabilities(access_token):
    try:
        client = create_plaid_client()
        accounts = get_accounts(access_token)
        
        credit_accounts = [
            account.account_id
            for account in accounts
            if account.type == 'credit' or 
            (account.subtype and str(account.subtype).lower().find('credit') != -1)
        ]
        student_accounts = [
            account.account_id
            for account in accounts
            if account.subtype and str(account.subtype).lower().find('student') != -1
        ]
        
        # Step 1: Fetch accounts and filter for credit cards and student loans
        account_ids = credit_accounts + student_accounts

        if not account_ids:
            print("No credit card or student loan accounts found.")
            return [], []

        # Step 2: Modify the LiabilitiesGetRequest to include only specified account_ids
        request = LiabilitiesGetRequest(
            access_token=access_token,
            options=LiabilitiesGetRequestOptions(
                account_ids=account_ids
            )
        )

        try:
            response = client.liabilities_get(request)
            #print("Successfully retrieved liabilities data from Plaid")
        except plaid.ApiException as e:
            print(f"Plaid API error getting liabilities: {e.body}")
            return [], []

        liabilities = response.get('liabilities', {})

        # Process student loans
        student_loans = liabilities.get('student', [])
        #print(f"Found {len(student_loans)} student loans")

        # Process credit cards
        credit_cards = liabilities.get('credit', [])
        #print(f"Found {len(credit_cards)} credit cards")

        #print("\nLiabilities response:")
        #print(f"Student loans found: {len(student_loans)}")
        #print(f"Credit cards found: {len(credit_cards)}")

        return student_loans, credit_cards

    except plaid.ApiException as e:
        error_response = json.loads(e.body)
        print(f"Plaid API error: {error_response.get('error_code')} - {error_response.get('error_message')}")
        return [], []
    except Exception as e:
        print(f"\nError in get_liabilities: {str(e)}")
        raise

def get_investments(access_token):
    client = create_plaid_client()
    request = InvestmentsHoldingsGetRequest(access_token=access_token)
    response = client.investments_holdings_get(request)
    return response.holdings, response.securities, response.accounts

def get_institution_info(access_token):
    """Get institution info from Plaid"""
    try:
        print("\nDebug - get_institution_info started")
        client = create_plaid_client()
        
        # Get item info first
        print("Debug - Getting item info")
        item_request = ItemGetRequest(access_token=access_token)
        item_response = client.item_get(item_request)
        institution_id = item_response.item.institution_id
        print(f"Debug - Got institution_id: {institution_id}")
        
        # Get institution details
        print("Debug - Getting institution details")
        request = InstitutionsGetByIdRequest(
            institution_id=institution_id,
            country_codes=[CountryCode('US')]
        )
        response = client.institutions_get_by_id(request)
        print(f"Debug - Got institution response: {response}")
        
        if not response or not response.institution:
            raise Exception("No institution data received from Plaid")
            
        institution = response.institution
        
        # Convert products enum to strings
        products_list = [str(product) for product in institution.products]
        
        # Create base institution info with only required fields
        institution_info = {
            'institution_id': institution.institution_id,
            'name': institution.name,
            'products': products_list,
            'oauth': getattr(institution, 'oauth', False),
            'status': 'UNKNOWN',
            'billed_products': [str(product) for product in getattr(institution, 'billed_products', [])]
        }
        
        # Add optional fields if they exist
        if hasattr(institution, 'url'):
            institution_info['url'] = institution.url
        if hasattr(institution, 'refresh_interval'):
            institution_info['refresh_interval'] = institution.refresh_interval
            
        # Add status if available
        if hasattr(institution, 'status') and institution.status is not None:
            if hasattr(institution.status, 'item_logins') and institution.status.item_logins is not None:
                institution_info['status'] = ('HEALTHY' 
                    if institution.status.item_logins.status == 'HEALTHY' 
                    else 'DEGRADED')
        
        return institution_info
        
    except Exception as e:
        print(f"Error getting institution info: {str(e)}")
        raise Exception(f"Failed to get institution info: {str(e)}")

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
    try:
        with open('access_tokens.json', 'r') as f:
            tokens_data = json.load(f)
            
        # Search through tokens to find matching item_id
        for institution_data in tokens_data.values():
            access_token = institution_data.get('access_token')
            if access_token:
                # Get item info to check item_id
                item = get_item(access_token)
                if item and item.item_id == item_id:
                    return access_token
        return None
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def fire_sandbox_webhook(access_token):
    """Fire a test webhook in sandbox mode"""
    client = create_plaid_client()
    
    try:
        # Get the item_id first
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
        
        # For testing the webhook directly
        print(f"Test with: curl -X POST {Config.APP_URL}/webhook \\")
        print('  -H "Content-Type: application/json" \\')
        print(f'  -d \'{{"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": "{item.item_id}"}}\'')
        
        return response
    except Exception as e:
        print(f"Error firing sandbox webhook: {e}")
        raise
