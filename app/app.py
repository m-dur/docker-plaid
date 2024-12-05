import json
import plaid
from flask import Flask, render_template, request, jsonify, session, send_file
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid_service import create_and_store_link_token, get_access_token, save_access_token, get_saved_access_tokens, get_institution_info, get_access_token_by_item_id, fire_sandbox_webhook, get_item, create_plaid_client
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
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Start transaction
        cur.execute("BEGIN")
        
        public_token = request.json['public_token']
        institution_id = request.json['metadata']['institution']['institution_id']
        institution_name = request.json['metadata']['institution']['name']
        
        client = create_plaid_client()
        exchange_response = client.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        )
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
        
        # Get institution info before saving anything
        institution_info = get_institution_info(access_token)
        
        # For new accounts, we should start with a fresh sync
        handler = FinancialDataHandler()
        item_info = {
            'institution_id': institution_id,
            'is_new_account': True
        }
        success = handler.fetch_and_process_financial_data(access_token, conn=conn, cur=cur, item_info=item_info)
        
        if success:
            # Save access token to database
            save_access_token(access_token, item_id, institution_id, institution_name)
            
            # Commit transaction only if everything succeeded
            cur.execute("COMMIT")
            return jsonify({'message': 'Account linked and initial data fetched successfully'}), 200
        else:
            raise Exception("Failed to process financial data")
            
    except Exception as e:
        cur.execute("ROLLBACK")
        app.logger.error(f"Error in exchange_public_token: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

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
def remove_institution():
    try:
        data = request.get_json()
        institution_id = data.get('institution_id')
        
        if not institution_id:
            return jsonify({'error': 'Institution ID is required'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("BEGIN")
            
            # Get access token before deleting
            cur.execute("""
                SELECT access_token 
                FROM access_tokens 
                WHERE institution_id = %s
            """, (institution_id,))
            result = cur.fetchone()
            
            if result:
                access_token = result[0]
                try:
                    client = create_plaid_client()
                    plaid_request = ItemRemoveRequest(access_token=access_token)
                    client.item_remove(plaid_request)
                except Exception as e:
                    print(f"Error removing item from Plaid: {e}")

            # Delete data in correct order
            cur.execute("""
                WITH account_ids AS (
                    SELECT account_id FROM accounts WHERE institution_id = %s
                )
                DELETE FROM transactions WHERE account_id IN (SELECT account_id FROM account_ids)
            """, (institution_id,))
            
            # Delete from plaid_api_calls first
            cur.execute("""
                DELETE FROM plaid_api_calls 
                WHERE access_token_id IN (
                    SELECT token_id 
                    FROM access_tokens 
                    WHERE institution_id = %s
                )
            """, (institution_id,))
            
            # Then delete from other tables
            for table in ['depository_accounts', 'credit_accounts', 'loan_accounts', 'investment_accounts']:
                cur.execute(f"""
                    DELETE FROM {table} 
                    WHERE account_id IN (
                        SELECT account_id FROM accounts WHERE institution_id = %s
                    )
                """, (institution_id,))
            
            cur.execute("DELETE FROM accounts WHERE institution_id = %s", (institution_id,))
            cur.execute("DELETE FROM institution_cursors WHERE institution_id = %s", (institution_id,))
            cur.execute("DELETE FROM access_tokens WHERE institution_id = %s", (institution_id,))
            cur.execute("DELETE FROM institutions WHERE id = %s", (institution_id,))
            
            cur.execute("COMMIT")
            return jsonify({'success': True}), 200
            
        except Exception as e:
            cur.execute("ROLLBACK")
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
    print("----------------------------------------")
    print("Webhook received!")
    print("Headers:", dict(request.headers))
    print("Data:", request.data)
    print("JSON:", request.json)
    print("----------------------------------------")
    
    # Get Plaid-Verification header
    verification_header = request.headers.get('Plaid-Verification')
    
    if verification_header:
        # Get the raw request body for verification
        request_body = request.get_data().decode('utf-8')
        
        # Calculate the webhook signature
        webhook_secret = Config.PLAID_WEBHOOK_SECRET
        if not webhook_secret:
            app.logger.error("Webhook secret not configured")
            return jsonify({'error': 'Webhook secret not configured'}), 500
            
        calculated_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            request_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if verification_header != calculated_signature:
            app.logger.error("Invalid webhook signature")
            return jsonify({'error': 'Invalid webhook signature'}), 401
    
    webhook_data = request.json
    webhook_type = webhook_data.get('webhook_type')
    webhook_code = webhook_data.get('webhook_code')

    if webhook_type == 'TRANSACTIONS' and webhook_code == 'SYNC_UPDATES_AVAILABLE':
        item_id = webhook_data.get('item_id')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Get access token from database using item_id
            cur.execute("""
                SELECT access_token 
                FROM access_tokens 
                WHERE item_id = %s
            """, (item_id,))
            result = cur.fetchone()
            
            if not result:
                return jsonify({'error': 'Item not found'}), 404
                
            access_token = result[0]
            
            # Only process transaction updates
            handler = FinancialDataHandler()
            result = handler.process_transaction_updates(access_token)
            
            return jsonify({
                'success': True,
                'message': 'Successfully processed transaction updates',
                'result': result
            }), 200
            
        except Exception as e:
            app.logger.error(f"Error processing webhook: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            conn.close()

    return jsonify({'message': 'Webhook received but no action taken'}), 200

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
        # Get institution details
        cur.execute("""
            SELECT 
                last_refresh,
                created_at as connected_on
            FROM institutions 
            WHERE id = %s
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
        # Query to get all tables and their row counts from the public schema
        cur.execute("""
            SELECT 
                relname as table_name,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC;
        """)
        
        results = cur.fetchall()
        stats = {table_name: row_count for table_name, row_count in results}
                
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error getting database statistics: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True, port=5001)

