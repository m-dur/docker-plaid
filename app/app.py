import json
import plaid
from flask import Flask, render_template, request, jsonify, session, send_file
from plaid_service import create_and_store_link_token, get_access_token, save_access_token, get_saved_access_tokens, delete_cursor, get_institution_info, get_access_token_by_item_id, fire_sandbox_webhook, get_item, create_plaid_client
from financial_data.handlers.financial_data_handler import FinancialDataHandler
from financial_data.config.excel_config import EXCEL_FILE
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
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from psycopg2.extras import RealDictCursor
from sqlalchemy import text
from dateutil.relativedelta import relativedelta
import calendar

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key
app.json_encoder = CustomJSONEncoder

@app.route('/')
def index():
    # Get all saved access tokens
    institutions = []
    has_access_token = False
    try:
        with open('access_tokens.json', 'r') as f:
            tokens_data = json.load(f)
            has_access_token = len(tokens_data) > 0
            institutions = [
                {
                    'name': data.get('institution_name'),
                    'id': data.get('institution_id')
                }
                for data in tokens_data.values()
            ]
    except (FileNotFoundError, json.JSONDecodeError):
        tokens_data = {}
    
    link_token = create_and_store_link_token()
    schema_diagram = generate_db_schema()
    
    return render_template('index.html', 
                         link_token=link_token,
                         institutions=institutions,
                         has_access_token=has_access_token,
                         schema_diagram=schema_diagram)

@app.route('/exchange_public_token', methods=['POST'])
def exchange_public_token():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Start transaction
        cur.execute("BEGIN")
        
        public_token = request.json['public_token']
        institution_id = request.json['metadata']['institution']['institution_id']
        
        client = create_plaid_client()
        exchange_response = client.item_public_token_exchange(
            ItemPublicTokenExchangeRequest(public_token=public_token)
        )
        access_token = exchange_response['access_token']
        
        # Get institution info before saving anything
        institution_info = get_institution_info(access_token)
        
        # Process financial data with transaction support
        handler = FinancialDataHandler()
        success = handler.fetch_and_process_financial_data(access_token, conn=conn, cur=cur)
        
        if success:
            # Only save access token if everything else succeeded
            tokens_data = {}
            try:
                with open('access_tokens.json', 'r') as f:
                    tokens_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                tokens_data = {}
            
            tokens_data[institution_id] = {
                'access_token': access_token,
                'institution_id': institution_id,
                'institution_name': request.json['metadata']['institution']['name']
            }
            
            with open('access_tokens.json', 'w') as f:
                json.dump(tokens_data, f)
            
            # Commit transaction only if everything succeeded
            cur.execute("COMMIT")
            return jsonify({'message': 'Account linked and initial data fetched successfully'}), 200
        else:
            raise Exception("Failed to process financial data")
            
    except Exception as e:
        # Roll back transaction and clean up on any error
        cur.execute("ROLLBACK")
        app.logger.error(f"Error in exchange_public_token: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/fetch_financial_data', methods=['POST'])
def fetch_financial_data():
    try:
        # Get access tokens
        tokens_data = {}
        try:
            with open('access_tokens.json', 'r') as f:
                tokens_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            app.logger.error(f"Error reading access tokens: {str(e)}")
            return jsonify({'error': 'No access tokens found'}), 500

        handler = FinancialDataHandler()
        
        all_results = []
        for institution_data in tokens_data.values():
            access_token = institution_data['access_token']
            try:
                result = handler.fetch_and_process_financial_data(access_token)
                result['institution_name'] = institution_data['institution_name']
                all_results.append(result)
                app.logger.info(f"Successfully processed data for {institution_data['institution_name']}")
            except Exception as e:
                app.logger.error(f"Error processing institution {institution_data['institution_name']}: {str(e)}")
                return jsonify({'error': f"Error processing institution {institution_data['institution_name']}: {str(e)}"}), 500

        return jsonify({'results': all_results}), 200
        
    except Exception as e:
        app.logger.error(f"Error fetching financial data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/remove_institution', methods=['POST'])
def remove_institution():
    try:
        data = request.get_json()
        institution_id = data.get('institution_id')
        
        if not institution_id:
            return jsonify({'error': 'Institution ID is required'}), 400

        # Get access tokens
        tokens_data = {}
        try:
            with open('access_tokens.json', 'r') as f:
                tokens_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Get the access_token if it exists
        institution_data = tokens_data.get(institution_id, {})
        access_token = institution_data.get('access_token')
        
        # Remove from Plaid if we have an access token
        if access_token:
            try:
                client = create_plaid_client()
                plaid_request = ItemRemoveRequest(access_token=access_token)
                client.item_remove(plaid_request)
            except Exception as e:
                print(f"Error removing item from Plaid: {e}")

        # Remove from database in correct order
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            
            # Get all account IDs for this institution
            cur.execute("SELECT account_id FROM accounts WHERE institution_id = %s", (institution_id,))
            account_ids = [row[0] for row in cur.fetchall()]
            
            # Delete from all related tables in correct order
            for account_id in account_ids:
                cur.execute("DELETE FROM transactions WHERE account_id = %s", (account_id,))
                cur.execute("DELETE FROM depository_accounts WHERE account_id = %s", (account_id,))
                cur.execute("DELETE FROM credit_accounts WHERE account_id = %s", (account_id,))
                cur.execute("DELETE FROM loan_accounts WHERE account_id = %s", (account_id,))
                cur.execute("DELETE FROM investment_accounts WHERE account_id = %s", (account_id,))
            
            # Now safe to delete from accounts
            cur.execute("DELETE FROM accounts WHERE institution_id = %s", (institution_id,))
            
            # Finally delete the institution
            cur.execute("DELETE FROM institutions WHERE id = %s", (institution_id,))
            
            # Remove from access_tokens.json
            if institution_id in tokens_data:
                del tokens_data[institution_id]
                with open('access_tokens.json', 'w') as f:
                    json.dump(tokens_data, f)
            
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

@app.route('/api/transactions')
def get_transactions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
             SELECT 
                t.date,  
                t.category,
                t.group_name,
                t.name,
                t.amount,
                a.account_name
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.account_id
            order by date desc
        """)
        transactions = cur.fetchall()
        return jsonify(transactions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

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
        try:
            access_token = get_access_token_by_item_id(item_id)
            if not access_token:
                return jsonify({'error': 'Item not found'}), 404

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

    return jsonify({'message': 'Webhook received but no action taken'}), 200

@app.route('/test_webhook', methods=['POST'])
def test_webhook():
    try:
        print("Starting test_webhook...")
        with open('access_tokens.json', 'r') as f:
            tokens_data = json.load(f)
            print(f"Loaded tokens data: {tokens_data}")
            
        if not tokens_data:
            return jsonify({'error': 'No access tokens found'}), 400
            
        first_institution = next(iter(tokens_data.values()))
        access_token = first_institution['access_token']
        print(f"Using access token: {access_token}")
        
        # Fire the webhook
        print("About to fire webhook...")
        response = fire_sandbox_webhook(access_token)
        print(f"Webhook response: {response}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook fired successfully',
            'response': str(response)
        }), 200
        
    except Exception as e:
        print(f"Error in test_webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/institution/<institution_id>/metadata')
def get_institution_metadata(institution_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get institution info and basic counts
        cur.execute("""
            WITH stats AS (
                SELECT 
                    i.*, 
                    COUNT(DISTINCT a.account_id) as connected_accounts,
                    COUNT(DISTINCT t.transaction_id) as total_transactions,
                    COUNT(DISTINCT CASE 
                        WHEN t.category IS NULL OR t.group_name IS NULL 
                        THEN t.transaction_id 
                    END) as uncategorized_transactions,
                    MAX(t.date) as last_transaction_date,
                    MIN(i.created_at) as connected_on
                FROM institutions i
                LEFT JOIN accounts a ON i.id = a.institution_id
                LEFT JOIN transactions t ON a.account_id = t.account_id
                WHERE i.id = %s
                GROUP BY i.id
            )
            SELECT * FROM stats
        """, (institution_id,))
        
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Institution not found'}), 404
            
        metadata = {
            'id': result['id'],
            'name': result['name'],
            'status': result['status'],
            'connectedAccounts': result['connected_accounts'] or 0,
            'totalTransactions': result['total_transactions'] or 0,
            'uncategorizedTransactions': result['uncategorized_transactions'] or 0,
            'lastTransactionDate': result['last_transaction_date'].isoformat() if result['last_transaction_date'] else None,
            'connectedOn': result['connected_on'].isoformat() if result['connected_on'] else None,
            'lastAccountRefresh': None,
            'lastCreditPull': None
        }
        
        return jsonify({'metadata': metadata})
        
    except Exception as e:
        print(f"Error getting institution metadata: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/transactions')
def transactions():
    return render_template('transactions.html')

@app.route('/api/transactions/update_category', methods=['POST'])
def update_transaction_category():
    try:
        transaction_id = request.json.get('transaction_id')
        new_category = request.json.get('category')
        update_all = request.json.get('update_all', False)
        transaction_name = request.json.get('transaction_name')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # First, update the category_mappings table
        cur.execute("""
            INSERT INTO category_mappings (transaction_name, category)
            VALUES (%s, %s)
            ON CONFLICT (transaction_name) 
            DO UPDATE SET 
                category = EXCLUDED.category,
                last_updated = CURRENT_TIMESTAMP
        """, (transaction_name, new_category))
        
        # Then update the transactions table
        if update_all:
            cur.execute("""
                UPDATE transactions 
                SET category = %s
                WHERE name = %s
                RETURNING transaction_id, category, name
            """, (new_category, transaction_name))
        else:
            cur.execute("""
                UPDATE transactions 
                SET category = %s
                WHERE transaction_id = %s
                RETURNING transaction_id, category, name
            """, (new_category, transaction_id))
        
        updated = cur.fetchall()
        conn.commit()
        
        return jsonify({
            'success': True, 
            'updated_count': len(updated),
            'transaction_id': transaction_id,
            'category': new_category
        })
        
    except Exception as e:
        app.logger.error(f"Error updating category: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/transactions/update_group', methods=['POST'])
def update_transaction_group():
    try:
        transaction_id = request.json.get('transaction_id')
        new_group = request.json.get('group')
        update_all = request.json.get('update_all', False)
        transaction_name = request.json.get('transaction_name')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # First, update the group_mappings table
        cur.execute("""
            INSERT INTO group_mappings (transaction_name, group_name)
            VALUES (%s, %s)
            ON CONFLICT (transaction_name) 
            DO UPDATE SET 
                group_name = EXCLUDED.group_name,
                last_updated = CURRENT_TIMESTAMP
        """, (transaction_name, new_group))
        
        # Then update the transactions table
        if update_all:
            cur.execute("""
                UPDATE transactions 
                SET group_name = %s
                WHERE name = %s
                RETURNING transaction_id, group_name, name
            """, (new_group, transaction_name))
        else:
            cur.execute("""
                UPDATE transactions 
                SET group_name = %s
                WHERE transaction_id = %s
                RETURNING transaction_id, group_name, name
            """, (new_group, transaction_id))
        
        updated = cur.fetchall()
        conn.commit()
        
        return jsonify({
            'success': True, 
            'updated_count': len(updated),
            'transaction_id': transaction_id,
            'group': new_group
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/expenses')
def expenses():
    return render_template('expenses.html')

@app.route('/api/expenses/summary')
def expenses_summary():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get filter parameters
        category = request.args.get('category', 'all')
        month = request.args.get('month', 'all')
        
        # Get last 12 months
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=11)
        
        base_conditions = """
            WHERE t.amount > 0
            AND t.date BETWEEN %s AND %s
            AND LOWER(COALESCE(t.category, '')) NOT LIKE '%%transfer%%'
        """
        
        params = [start_date, end_date]
        
        if category != 'all':
            base_conditions += " AND t.category = %s"
            params.append(category)
            
        if month != 'all':
            base_conditions += " AND TO_CHAR(t.date, 'YYYY-MM') = %s"
            params.append(month)
        
        query = f"""
        WITH filtered_transactions AS (
            SELECT 
                t.transaction_id,
                t.name,
                t.category,
                t.amount,
                t.date
            FROM transactions t
            {base_conditions}
        ),
        category_totals AS (
            SELECT 
                category,
                SUM(amount) as category_total
            FROM filtered_transactions
            GROUP BY category
        ),
        total_amount AS (
            SELECT SUM(amount) as grand_total 
            FROM filtered_transactions
        )
        SELECT 
            ft.transaction_id,
            ft.name,
            ft.category,
            ft.amount,
            ft.date,
            (ft.amount / NULLIF(ct.category_total, 0) * 100) as category_percentage
        FROM filtered_transactions ft
        LEFT JOIN category_totals ct ON ft.category = ct.category
        CROSS JOIN total_amount
        ORDER BY ft.date DESC, ft.amount DESC
        """
        
        cur.execute(query, tuple(params))
        results = cur.fetchall()
        
        # Calculate summary statistics
        total_expenses = sum(abs(float(row[3])) for row in results)
        monthly_average = total_expenses / 12 if results else 0
        
        # Find highest category
        category_totals = {}
        for row in results:
            category = row[2] or 'Uncategorized'
            amount = abs(float(row[3]))
            category_totals[category] = category_totals.get(category, 0) + amount
        
        highest_category = max(category_totals.items(), key=lambda x: x[1])[0] if category_totals else ''
        
        return jsonify({
            'total_expenses': total_expenses,
            'monthly_average': monthly_average,
            'highest_category': highest_category,
            'transactions': [{
                'transaction_id': row[0],
                'name': row[1],
                'category': row[2] or 'Uncategorized',
                'amount': abs(float(row[3])),
                'date': row[4].isoformat(),
                'percentage': float(row[5] or 0)
            } for row in results]
        })
        
    except Exception as e:
        print(f"Error in expenses_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/expenses/monthly')
def expenses_monthly():
    category = request.args.get('category', 'all')
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get last 12 months
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=11)
        
        if category != 'all':
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(t.amount), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount > 0
                AND category = %s
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
            """
            cur.execute(query, (start_date, end_date, category))
        else:
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(t.amount), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount > 0
                AND category <> 'Transfer'
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
            """
            cur.execute(query, (start_date, end_date))
            
        results = cur.fetchall()
        
        months = []
        amounts = []
        
        for row in results:
            months.append(row[0].strftime('%B %Y'))
            amounts.append(float(row[1]))
            
        return jsonify({
            'months': months,
            'amounts': amounts
        })
        
    except Exception as e:
        print(f"Error in expenses_monthly: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/categories')
def get_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        query = """
        SELECT DISTINCT category 
        FROM transactions 
        WHERE amount > 0 
        AND category IS NOT NULL 
        AND LOWER(COALESCE(category, '')) NOT LIKE '%transfer%'
        ORDER BY category
        """
        cur.execute(query)
        categories = [row[0] for row in cur.fetchall()]
        return jsonify({'categories': categories})
    except Exception as e:
        print(f"Error getting categories: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/expenses/daily')
def expenses_daily():
    category = request.args.get('category', 'all')
    month = request.args.get('month')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        current_month = datetime.strptime(month, '%Y-%m')
        prior_month = current_month - relativedelta(months=1)
        
        _, last_day = calendar.monthrange(current_month.year, current_month.month)
        _, prior_last_day = calendar.monthrange(prior_month.year, prior_month.month)
        
        current_start = current_month.replace(day=1)
        current_end = current_month.replace(day=last_day)
        prior_start = prior_month.replace(day=1)
        prior_end = prior_month.replace(day=prior_last_day)
        
        # Add prior month data to the response
        base_query = """
        WITH RECURSIVE dates AS (
            SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date AS date
        ),
        daily_totals AS (
            SELECT date::date, COALESCE(SUM(amount), 0) as daily_amount
            FROM transactions 
            WHERE date >= %s AND date <= %s
            AND amount > 0
            AND LOWER(COALESCE(category, '')) NOT LIKE '%%transfer%%'
            {category_filter}
            GROUP BY date::date
        )
        SELECT 
            d.date,
            COALESCE(SUM(dt.daily_amount) OVER (ORDER BY d.date), 0) as cumulative_amount
        FROM dates d
        LEFT JOIN daily_totals dt ON d.date = dt.date
        ORDER BY d.date;
        """
        
        category_filter = "AND category = %s" if category != 'all' else ""
        query = base_query.format(category_filter=category_filter)
        
        # Get current month data
        params = [current_start, current_end, current_start, current_end]
        if category != 'all':
            params.append(category)
        cur.execute(query, tuple(params))
        current_results = cur.fetchall()
        
        # Get prior month data
        params = [prior_start, prior_end, prior_start, prior_end]
        if category != 'all':
            params.append(category)
        cur.execute(query, tuple(params))
        prior_results = cur.fetchall()
        
        return jsonify({
            'dates': [row[0].strftime('%Y-%m-%d') for row in current_results],
            'amounts': [float(row[1]) for row in current_results],
            'prior_dates': [row[0].strftime('%Y-%m-%d') for row in prior_results],
            'prior_amounts': [float(row[1]) for row in prior_results]
        })
        
    except Exception as e:
        print(f"Error in expenses_daily: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/database_status')
def database_status():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Query to get row counts for all tables
        query = """
        SELECT 
            table_name,
            (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = c.table_name) as column_count,
            (SELECT reltuples::bigint FROM pg_class WHERE relname = c.table_name) as row_count
        FROM information_schema.tables c
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        stats = {}
        for table_name, column_count, row_count in results:
            stats[table_name] = {
                'count': row_count,
                'columns': column_count
            }
            
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error getting database stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/groups')
def get_groups():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        query = """
        SELECT DISTINCT group_name 
        FROM transactions 
        WHERE amount > 0 
        AND group_name IS NOT NULL 
        AND LOWER(COALESCE(group_name, '')) NOT LIKE '%transfer%'
        ORDER BY group_name
        """
        cur.execute(query)
        groups = [row[0] for row in cur.fetchall()]
        return jsonify({'groups': groups})
    except Exception as e:
        print(f"Error getting groups: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/expenses/group_daily')
def expenses_group_daily():
    group = request.args.get('group', 'all')
    month = request.args.get('month')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        current_month = datetime.strptime(month, '%Y-%m')
        prior_month = current_month - relativedelta(months=1)
        
        _, last_day = calendar.monthrange(current_month.year, current_month.month)
        _, prior_last_day = calendar.monthrange(prior_month.year, prior_month.month)
        
        current_start = current_month.replace(day=1)
        current_end = current_month.replace(day=last_day)
        prior_start = prior_month.replace(day=1)
        prior_end = prior_month.replace(day=prior_last_day)
        
        base_query = """
        WITH RECURSIVE dates AS (
            SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date AS date
        ),
        daily_totals AS (
            SELECT date::date, COALESCE(SUM(amount), 0) as daily_amount
            FROM transactions 
            WHERE date >= %s AND date <= %s
            AND amount > 0
            AND LOWER(COALESCE(group_name, '')) NOT LIKE '%%transfer%%'
            {group_filter}
            GROUP BY date::date
        )
        SELECT 
            d.date,
            COALESCE(SUM(dt.daily_amount) OVER (ORDER BY d.date), 0) as cumulative_amount
        FROM dates d
        LEFT JOIN daily_totals dt ON d.date = dt.date
        ORDER BY d.date;
        """
        
        group_filter = "AND group_name = %s" if group != 'all' else ""
        query = base_query.format(group_filter=group_filter)
        
        # Get current month data
        params = [current_start, current_end, current_start, current_end]
        if group != 'all':
            params.append(group)
        cur.execute(query, tuple(params))
        current_results = cur.fetchall()
        
        # Get prior month data
        params = [prior_start, prior_end, prior_start, prior_end]
        if group != 'all':
            params.append(group)
        cur.execute(query, tuple(params))
        prior_results = cur.fetchall()
        
        return jsonify({
            'dates': [row[0].strftime('%Y-%m-%d') for row in current_results],
            'amounts': [float(row[1]) for row in current_results],
            'prior_dates': [row[0].strftime('%Y-%m-%d') for row in prior_results],
            'prior_amounts': [float(row[1]) for row in prior_results]
        })
        
    except Exception as e:
        print(f"Error in expenses_group_daily: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/expenses/group')
def expenses_group():
    return render_template('expenses_group.html')

@app.route('/api/expenses/group_summary')
def expenses_group_summary():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get filter parameters
        group = request.args.get('group', 'all')
        month = request.args.get('month', 'all')
        
        # Get last 12 months
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=11)
        
        base_conditions = """
            WHERE t.amount > 0
            AND t.date BETWEEN %s AND %s
            AND LOWER(COALESCE(t.group_name, '')) NOT LIKE '%%transfer%%'
        """
        
        params = [start_date, end_date]
        
        if group != 'all':
            base_conditions += " AND t.group_name = %s"
            params.append(group)
            
        if month != 'all':
            base_conditions += " AND TO_CHAR(t.date, 'YYYY-MM') = %s"
            params.append(month)
        
        query = f"""
        WITH filtered_transactions AS (
            SELECT 
                t.transaction_id,
                t.name,
                t.group_name,
                t.amount,
                t.date
            FROM transactions t
            {base_conditions}
        ),
        group_totals AS (
            SELECT 
                group_name,
                SUM(amount) as group_total
            FROM filtered_transactions
            GROUP BY group_name
        ),
        total_amount AS (
            SELECT SUM(amount) as grand_total 
            FROM filtered_transactions
        )
        SELECT 
            ft.transaction_id,
            ft.name,
            ft.group_name,
            ft.amount,
            ft.date,
            (ft.amount / NULLIF(gt.group_total, 0) * 100) as group_percentage
        FROM filtered_transactions ft
        LEFT JOIN group_totals gt ON ft.group_name = gt.group_name
        CROSS JOIN total_amount
        ORDER BY ft.date DESC, ft.amount DESC
        """
        
        cur.execute(query, tuple(params))
        results = cur.fetchall()
        
        # Calculate summary statistics
        total_expenses = sum(abs(float(row[3])) for row in results)
        monthly_average = total_expenses / 12 if results else 0
        
        # Find highest group
        group_totals = {}
        for row in results:
            group = row[2] or 'Uncategorized'
            amount = abs(float(row[3]))
            group_totals[group] = group_totals.get(group, 0) + amount
        
        highest_group = max(group_totals.items(), key=lambda x: x[1])[0] if group_totals else ''
        
        return jsonify({
            'total_expenses': total_expenses,
            'monthly_average': monthly_average,
            'highest_group': highest_group,
            'transactions': [{
                'transaction_id': row[0],
                'name': row[1],
                'group_name': row[2] or 'Uncategorized',
                'amount': abs(float(row[3])),
                'date': row[4].isoformat(),
                'percentage': float(row[5] or 0)
            } for row in results]
        })
        
    except Exception as e:
        print(f"Error in expenses_group_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/expenses/group_monthly')
def expenses_group_monthly():
    group = request.args.get('group', 'all')
    start_date = datetime.fromisoformat(request.args.get('start_date').replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(request.args.get('end_date').replace('Z', '+00:00'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if group != 'all':
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(t.amount), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount > 0
                AND group_name = %s
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
            """
            cur.execute(query, (start_date, end_date, group))
        else:
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(t.amount), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount > 0
                AND LOWER(COALESCE(group_name, '')) NOT LIKE '%%transfer%%'
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
            """
            cur.execute(query, (start_date, end_date))
            
        results = cur.fetchall()
        
        months = []
        amounts = []
        
        for row in results:
            months.append(row[0].strftime('%B %Y'))
            amounts.append(float(row[1]))
            
        return jsonify({
            'months': months,
            'amounts': amounts
        })
        
    except Exception as e:
        print(f"Error in expenses_group_monthly: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5001)

