from flask import Blueprint, jsonify, request, render_template
from financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import RealDictCursor

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/')
def transactions():
    return render_template('transactions.html')

@transactions_bp.route('/api/transactions/update_category', methods=['POST'])
def update_transaction_category():
    try:
        transaction_id = request.json.get('transaction_id')
        new_category = request.json.get('category')
        update_all = request.json.get('update_all', False)
        transaction_name = request.json.get('transaction_name')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Start transaction
            cur.execute("BEGIN")
            
            # Always update the specific transaction
            cur.execute("""
                UPDATE transactions 
                SET category = %s
                WHERE transaction_id = %s
                RETURNING transaction_id, category, name
            """, (new_category, transaction_id))
            
            # Always create/update the mapping
            cur.execute("""
                INSERT INTO category_mappings (transaction_name, category)
                VALUES (%s, %s)
                ON CONFLICT (transaction_name) 
                DO UPDATE SET 
                    category = EXCLUDED.category,
                    last_updated = CURRENT_TIMESTAMP
            """, (transaction_name, new_category))
            
            # Only update other existing transactions if update_all is True
            if update_all:
                cur.execute("""
                    UPDATE transactions 
                    SET category = %s
                    WHERE name = %s
                    AND transaction_id != %s
                """, (new_category, transaction_name, transaction_id))
            
            conn.commit()
            return jsonify({
                'success': True,
                'transaction_id': transaction_id,
                'category': new_category
            })
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@transactions_bp.route('/api/transactions/update_group', methods=['POST'])
def update_transaction_group():
    try:
        transaction_id = request.json.get('transaction_id')
        new_group = request.json.get('group')
        update_all = request.json.get('update_all', False)
        transaction_name = request.json.get('transaction_name')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Start transaction
            cur.execute("BEGIN")
            
            # Always update the specific transaction
            cur.execute("""
                UPDATE transactions 
                SET group_name = %s
                WHERE transaction_id = %s
                RETURNING transaction_id, group_name, name
            """, (new_group, transaction_id))
            
            # Always create/update the mapping
            cur.execute("""
                INSERT INTO group_mappings (transaction_name, group_name)
                VALUES (%s, %s)
                ON CONFLICT (transaction_name) 
                DO UPDATE SET 
                    group_name = EXCLUDED.group_name,
                    last_updated = CURRENT_TIMESTAMP
            """, (transaction_name, new_group))
            
            # Only update other existing transactions if update_all is True
            if update_all:
                cur.execute("""
                    UPDATE transactions 
                    SET group_name = %s
                    WHERE name = %s
                    AND transaction_id != %s
                """, (new_group, transaction_name, transaction_id))
            
            conn.commit()
            return jsonify({
                'success': True,
                'transaction_id': transaction_id,
                'group': new_group
            })
            
        except Exception as e:
            cur.execute("ROLLBACK")
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@transactions_bp.route('/api/categories')
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

@transactions_bp.route('/api/groups')
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

@transactions_bp.route('/api/transactions')
def get_transactions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                t.transaction_id,
                t.date,
                a.account_name,
                t.category,
                t.group_name,
                t.name,
                t.amount
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.account_id
            ORDER BY t.date DESC
        """)
        transactions = cur.fetchall()
        return jsonify(transactions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
