import json
import plaid
from flask import Flask, render_template, request, jsonify, session, send_file
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid_service import create_and_store_link_token, get_access_token, save_access_token, get_saved_access_tokens, get_institution_info, get_access_token_by_item_id, fire_sandbox_webhook, get_item, create_plaid_client, get_item_details
from financial_data.handlers.financial_data_handler import FinancialDataHandler
from db_schema import generate_db_schema
from financial_data.db_operations.query_operations import execute_query, CustomJSONEncoder
import psycopg2
import psycopg2.extras
from io import BytesIO
import pandas as pd
from datetime import datetime
import hmac
import hashlib
from config import Config
from financial_data.utils.db_connection import get_db_connection
import calendar
from dateutil.relativedelta import relativedelta
from psycopg2.extras import RealDictCursor
from plaid.model.item_remove_request import ItemRemoveRequest
from routes.analytics import analytics_bp
from routes.transactions import transactions_bp
import logging
import threading
import time
from psycopg2.extensions import AsIs

# Then create the Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key
app.json_encoder = CustomJSONEncoder

# Add logging configuration
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

# Register blueprints after creating the app
app.register_blueprint(analytics_bp)
app.register_blueprint(transactions_bp, url_prefix='/transactions')

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get institutions from database
        cur.execute("""
            SELECT i.*, at.access_token IS NOT NULL as has_access_token
            FROM institutions i
            LEFT JOIN access_tokens at ON i.id = at.institution_id
        """)
        institutions = cur.fetchall()
        has_access_token = any(inst['has_access_token'] for inst in institutions)
        
        link_token = create_and_store_link_token()
        schema_diagram = generate_db_schema()
        
        return render_template('index.html', 
                            link_token=link_token,
                            institutions=institutions,
                            has_access_token=has_access_token,
                            schema_diagram=schema_diagram)
    finally:
        cur.close()
        conn.close()

@app.route('/exchange_public_token', methods=['POST'])
def exchange_public_token():
    print("\n=== Starting Public Token Exchange ===")
    try:
        data = request.get_json()
        public_token = data.get('public_token')
        metadata = data.get('metadata')
        
        if not public_token or not metadata:
            return jsonify({'error': 'Missing required data'}), 400
            
        print(f"Received metadata for institution: {metadata['institution']['name']}")
        
        # Increase delay to prevent rate limiting
        time.sleep(2)  # Increased from 1 to 2 seconds
        
        client = create_plaid_client()
        
        # Add more detailed logging
        try:
            exchange_response = client.item_public_token_exchange(
                ItemPublicTokenExchangeRequest(public_token=public_token)
            )
        except Exception as e:
            print(f"Plaid exchange error: {str(e)}")
            raise
            
        access_token = exchange_response.access_token
        item_id = exchange_response.item_id
        institution_id = metadata['institution']['institution_id']
        
        # Add transaction logging
        print(f"Successfully exchanged token for institution {institution_id}")
        
        # Save access token
        save_access_token(
            access_token=access_token,
            item_id=item_id,
            institution_id=institution_id,
            institution_name=metadata['institution']['name']
        )
        
        return jsonify({
            'success': True,
            'message': 'Account linked successfully',
            'institution_id': institution_id
        })
        
    except Exception as e:
        print(f"Detailed error in exchange_public_token: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_financial_data', methods=['POST'])
def fetch_financial_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get access tokens from database
        cur.execute("""
            SELECT 
                at.access_token,
                i.name as institution_name
            FROM access_tokens at
            JOIN institutions i ON at.institution_id = i.id
        """)
        tokens = cur.fetchall()
        
        if not tokens:
            return jsonify({'error': 'No access tokens found'}), 500
            
        handler = FinancialDataHandler()
        
        all_results = []
        for token in tokens:
            try:
                result = handler.fetch_and_process_financial_data(token['access_token'])
                result['institution_name'] = token['institution_name']
                all_results.append(result)
                app.logger.info(f"Successfully processed data for {token['institution_name']}")
            except Exception as e:
                app.logger.error(f"Error processing institution {token['institution_name']}: {str(e)}")
                return jsonify({'error': f"Error processing institution {token['institution_name']}: {str(e)}"}), 500

        return jsonify({'results': all_results}), 200
        
    except Exception as e:
        app.logger.error(f"Error fetching financial data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/remove_institution', methods=['POST'])
@app.route('/remove_institution/<institution_id>', methods=['POST'])
def remove_institution(institution_id=None):
    try:
        if institution_id is None:
            data = request.get_json()
            institution_id = data.get('institution_id')
            
        if not institution_id:
            return jsonify({'error': 'Institution ID is required'}), 400
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("BEGIN")
            
            # Get access token before deleting (if it exists)
            cur.execute("""
                SELECT access_token, token_id 
                FROM access_tokens 
                WHERE institution_id = %s
            """, (institution_id,))
            result = cur.fetchone()
            
            if result:
                access_token = result[0]
                token_id = result[1]
                
                try:
                    # Remove from Plaid first
                    client = create_plaid_client()
                    plaid_request = ItemRemoveRequest(access_token=access_token)
                    client.item_remove(plaid_request)
                except Exception as e:
                    app.logger.error(f"Error removing item from Plaid: {e}")
                
                # Delete all plaid API calls first
                cur.execute("""
                    DELETE FROM plaid_api_calls 
                    WHERE access_token_id = %s
                """, (token_id,))

            # Delete transactions
            cur.execute("""
                DELETE FROM transactions 
                WHERE account_id IN (
                    SELECT DISTINCT account_id 
                    FROM account_history 
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
            
            # Delete access token
            cur.execute("DELETE FROM access_tokens WHERE institution_id = %s", (institution_id,))
            
            # Delete items record first (before institution)
            cur.execute("DELETE FROM items WHERE institution_id = %s", (institution_id,))
            
            # Finally delete institution
            cur.execute("DELETE FROM institutions WHERE id = %s", (institution_id,))
            
            cur.execute("COMMIT")
            session['last_removal_time'] = time.time()
            return jsonify({'success': True}), 200
            
        except Exception as e:
            cur.execute("ROLLBACK")
            app.logger.error(f"Error in remove_institution: {str(e)}")
            raise e
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data')
def data():
    schema_diagram = generate_db_schema()
    return render_template('data.html', schema_diagram=schema_diagram)


@app.route('/api/run_query', methods=['POST'])
def run_query():
    query = request.json.get('query')
    try:
        results = execute_query(query)
        return jsonify({
            'success': True,
            'data': results if results else []
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/export_query')
def export_query():
    query = request.args.get('query')
    
    try:
        # Execute query and ensure we get results
        results = execute_query(query)
        if not results:
            return jsonify({'error': 'No data returned from query'}), 404
            
        # Convert to DataFrame - ensure results is a list of dictionaries
        df = pd.DataFrame.from_records(results)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Query Results', index=False)
            
        output.seek(0)
        
        # Set filename with timestamp
        filename = f'query_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Export error: {str(e)}")  # Add logging
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    print("\n=== Webhook Received ===")
    print(f"Headers: {dict(request.headers)}")
    print(f"Data: {request.data}")
    print(f"JSON: {request.json}")
    
    # Get Plaid-Verification header
    verification_header = request.headers.get('Plaid-Verification')
    
    if verification_header:
        print("\nVerifying webhook signature...")
        request_body = request.get_data().decode('utf-8')
        
        webhook_secret = Config.PLAID_WEBHOOK_SECRET
        if not webhook_secret:
            error_msg = "❌ Webhook secret not configured"
            app.logger.error(error_msg)
            print(error_msg)
            return jsonify({'error': 'Webhook secret not configured'}), 500
        
        calculated_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            request_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"Expected signature: {verification_header}")
        print(f"Calculated signature: {calculated_signature}")
        
        if verification_header != calculated_signature:
            error_msg = "❌ Invalid webhook signature"
            app.logger.error(error_msg)
            print(error_msg)
            return jsonify({'error': 'Invalid webhook signature'}), 401
    
    webhook_data = request.json
    webhook_type = webhook_data.get('webhook_type')
    webhook_code = webhook_data.get('webhook_code')
    
    print(f"\nWebhook Type: {webhook_type}")
    print(f"Webhook Code: {webhook_code}")
    
    if webhook_type == 'TRANSACTIONS' and webhook_code == 'SYNC_UPDATES_AVAILABLE':
        item_id = webhook_data.get('item_id')
        print(f"Processing transaction updates for item: {item_id}")
        
        try:
            handler = FinancialDataHandler()
            result = handler.process_transaction_updates(access_token)
            print(f"✓ Successfully processed transaction updates: {result}")
            return jsonify({
                'success': True,
                'message': 'Successfully processed transaction updates',
                'result': result
            }), 200
            
        except Exception as e:
            error_msg = f"❌ Error processing webhook: {str(e)}"
            app.logger.error(error_msg)
            print(error_msg)
            return jsonify({'error': str(e)}), 500

@app.route('/test_webhook', methods=['POST'])
def test_webhook():
    try:
        print("Starting test_webhook...")
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Get first available access token from database
            cur.execute("""
                SELECT at.access_token, i.name as institution_name 
                FROM access_tokens at
                JOIN institutions i ON at.institution_id = i.id
                LIMIT 1
            """)
            result = cur.fetchone()
            
            if not result:
                return jsonify({'error': 'No access tokens found'}), 400
                
            access_token = result[0]
            institution_name = result[1]
            print(f"Using access token for institution: {institution_name}")
            
            # Fire the webhook
            print("About to fire webhook...")
            response = fire_sandbox_webhook(access_token)
            print(f"Webhook response: {response}")
            
            return jsonify({
                'success': True,
                'message': 'Webhook fired successfully',
                'response': str(response)
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"Error in test_webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/institution_metadata/<institution_id>')
def get_institution_metadata(institution_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get institution details and item count
        cur.execute("""
            SELECT 
                i.last_refresh,
                i.created_at as connected_on,
                COUNT(DISTINCT it.item_id) as item_count
            FROM institutions i
            LEFT JOIN items it ON i.id = it.institution_id
            WHERE i.id = %s
            GROUP BY i.last_refresh, i.created_at
        """, (institution_id,))
        inst_data = cur.fetchone()
        
        # Get last transaction date
        cur.execute("""
            SELECT MAX(date) 
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.institution_id = %s
        """, (institution_id,))
        last_transaction = cur.fetchone()[0]
        
        # Get account counts
        cur.execute("""
            SELECT 
                COUNT(DISTINCT a.account_id) as account_count,
                COUNT(DISTINCT t.transaction_id) as transaction_count,
                COUNT(DISTINCT CASE WHEN t.category IS NULL THEN t.transaction_id END) as uncategorized_count
            FROM accounts a
            LEFT JOIN transactions t ON a.account_id = t.account_id
            WHERE a.institution_id = %s
        """, (institution_id,))
        counts = cur.fetchone()
        
        # Get new transactions (since last refresh)
        cur.execute("""
            SELECT COUNT(*) 
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.institution_id = %s
            AND t.created_at > COALESCE(
                (SELECT last_refresh FROM institutions WHERE id = %s),
                '1970-01-01'::timestamp
            )
        """, (institution_id, institution_id))
        new_transactions = cur.fetchone()[0]
        
        return jsonify({
            'last_transaction': last_transaction.isoformat() if last_transaction else None,
            'last_refresh': inst_data[0].isoformat() if inst_data and inst_data[0] else None,
            'connected_on': inst_data[1].isoformat() if inst_data and inst_data[1] else None,
            'new_transactions': new_transactions,
            'item_count': inst_data[2],
            'account_count': counts[0],
            'transaction_count': counts[1],
            'uncategorized_count': counts[2] if counts[2] else 0
        })
        
    except Exception as e:
        print(f"Error in get_institution_metadata: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/database_statistics')
def get_database_statistics():
    print("\n=== Database Statistics Debug ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # First get all tables and views
        cur.execute("""
            SELECT 
                n.nspname as schemaname,
                c.relname as relation_name,
                c.relkind as relation_type
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
            AND c.relkind IN ('r', 'v')  -- 'r' for tables, 'v' for views
        """)
        
        results = cur.fetchall()
        stats = {}
        
        for schema, name, rel_type in results:
            try:
                # Use COUNT(*) for both tables and views
                cur.execute(f"SELECT COUNT(*) FROM {name}")
                count = cur.fetchone()[0]
            except Exception as e:
                print(f"Error counting {name}: {e}")
                count = 0
            
            # Create more user-friendly display name
            display_name = name
            if rel_type == 'v':
                display_name += ' (view)'
            
            stats[display_name] = count
        
        # Sort by count in descending order
        sorted_stats = dict(sorted(stats.items(), key=lambda x: x[1], reverse=True))
        return jsonify(sorted_stats)
        
    except Exception as e:
        print(f"Error getting database statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/expenses/chart', methods=['GET'])
def get_expense_chart_data():
    selected_month = request.args.get('month')
    selected_category = request.args.get('category')
    
    app.logger.info(f"Expense Chart Request - Month: {selected_month}, Category: {selected_category}")
    app.logger.info(f"Current Server Time: {datetime.now().isoformat()}")
    
    # ... rest of the existing code ...

@app.route('/refresh_financial_data/<institution_id>', methods=['POST'])
def refresh_financial_data(institution_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        access_token = get_access_token(institution_id)
        
        # Get item details first
        item_response = get_item_details(access_token)
        if item_response:
            item_dict = item_response.to_dict()
            item = item_dict['item']
            status = item_dict['status']
            
            # Insert/Update items table
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
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (item_id) DO UPDATE SET
                    available_products = EXCLUDED.available_products,
                    billed_products = EXCLUDED.billed_products,
                    products = EXCLUDED.products,
                    consented_products = EXCLUDED.consented_products,
                    consented_data_scopes = EXCLUDED.consented_data_scopes,
                    consented_use_cases = EXCLUDED.consented_use_cases,
                    consent_expiration_time = EXCLUDED.consent_expiration_time,
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
                item['item_id'],
                institution_id,
                item['institution_name'],
                item['available_products'],
                item['billed_products'],
                item['products'],
                item.get('consented_products', []),
                item.get('consented_data_scopes', []),
                item.get('consented_use_cases', []),
                item.get('consent_expiration_time'),
                item['created_at'],
                item['update_type'],
                item['webhook'],
                item.get('error', {}).get('error_type'),
                item.get('error', {}).get('error_code'),
                item.get('error', {}).get('error_message'),
                status.get('transactions', {}).get('last_successful_update'),
                status.get('transactions', {}).get('last_failed_update'),
                status.get('last_webhook')
            ))
            conn.commit()

        # Continue with existing financial data processing
        handler = FinancialDataHandler()
        item_info = {
            'institution_id': institution_id,
            'is_manual_refresh': True
        }
        result = handler.fetch_and_process_financial_data(access_token, conn, cur, item_info)
        return jsonify(result)
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/create_link_token', methods=['GET'])
def create_new_link_token():
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            link_token = create_and_store_link_token()
            if link_token:
                return jsonify({'link_token': link_token})
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'Failed to create link token after multiple attempts'}), 500

@app.route('/get_institutions')
def get_institutions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT i.*, at.access_token IS NOT NULL as has_access_token
            FROM institutions i
            LEFT JOIN access_tokens at ON i.id = at.institution_id
        """)
        institutions = cur.fetchall()
        
        return jsonify({
            'success': True,
            'institutions': institutions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/item_details/<institution_id>')
def get_item_details_route(institution_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get access token using institution_id instead of item_id
        cur.execute("""
            SELECT access_token 
            FROM access_tokens 
            WHERE institution_id = %s
        """, (institution_id,))
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Institution not found'}), 404
            
        access_token = result[0]
        
        # Get and print item details
        item_details = get_item_details(access_token)
        
        return jsonify({'message': 'Item details printed to terminal'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5001)

