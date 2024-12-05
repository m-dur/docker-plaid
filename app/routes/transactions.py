from flask import Blueprint, jsonify, request
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
        current_app.logger.error(f"Error updating category: {str(e)}")
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
