from flask import Blueprint, jsonify, request
from financial_data.utils.db_connection import get_db_connection
from datetime import datetime
from collections import defaultdict

misc_bp = Blueprint('misc', __name__)

@misc_bp.route('/api/expenses/subs_stats')
def get_subs_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all subscription transactions
        query = """
        WITH base_transactions AS (
            SELECT 
                REGEXP_REPLACE(name, '\s*-\s*\d+.*$|\s*#\d+.*$', '') as base_name,
                amount,
                date
            FROM stg_transactions 
            WHERE category = 'Subs'
            AND amount > 0
            AND date >= NOW() - INTERVAL '12 months'
        ),
        sub_transactions AS (
            SELECT 
                base_name as name,
                SUM(amount) as total_spent,
                COUNT(*) as occurrence_count,
                MIN(date) as first_payment,
                MAX(date) as last_payment,
                MAX(amount) as amount
            FROM base_transactions
            GROUP BY base_name
        )
        SELECT
            name,
            amount,
            occurrence_count as payment_count,
            first_payment,
            last_payment,
            total_spent,
            CASE 
                WHEN occurrence_count >= 12 THEN 'Monthly'
                WHEN occurrence_count >= 4 THEN 'Quarterly'
                WHEN occurrence_count >= 2 THEN 'Semi-Annual'
                ELSE 'Annual'
            END as frequency
        FROM sub_transactions
        ORDER BY total_spent DESC
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        # Process subscription data
        subscriptions = []
        total_spent = 0
        most_expensive = {'name': '', 'amount': 0}
        first_date = None
        last_date = None
        
        for row in results:
            sub = {
                'name': row[0],
                'amount': float(row[1]),
                'payment_count': row[2],
                'first_payment': row[3].isoformat(),
                'last_payment': row[4].isoformat(),
                'total_spent': float(row[5]),
                'frequency': row[6]
            }
            
            subscriptions.append(sub)
            total_spent += sub['total_spent']
            
            # Track most expensive subscription
            if sub['amount'] > most_expensive['amount']:
                most_expensive = {'name': sub['name'], 'amount': sub['amount']}
            
            # Track first and last dates
            if first_date is None or row[3] < first_date:
                first_date = row[3]
            if last_date is None or row[4] > last_date:
                last_date = row[4]
        
        # Calculate monthly average based on actual months with data
        months_active = len(set(sub['last_payment'][:7] for sub in subscriptions))
        monthly_average = total_spent / months_active if months_active > 0 else 0
        
        # Add monthly data query
        monthly_query = """
        WITH base_transactions AS (
            SELECT 
                REGEXP_REPLACE(name, '\s*-\s*\d+.*$|\s*#\d+.*$', '') as base_name,
                amount,
                date_trunc('month', date)::date as month
            FROM stg_transactions 
            WHERE category = 'Subs'
            AND amount > 0
            AND date >= NOW() - INTERVAL '12 months'
        )
        SELECT 
            base_name as name,
            to_char(month, 'YYYY-MM') as month,
            SUM(amount) as amount
        FROM base_transactions
        GROUP BY base_name, month
        ORDER BY month, base_name;
        """
        
        cur.execute(monthly_query)
        monthly_results = cur.fetchall()
        monthly_data = [
            {
                'name': row[0],
                'month': row[1],
                'amount': float(row[2])
            }
            for row in monthly_results
        ]
        
        return jsonify({
            'active_count': len(subscriptions),
            'total_spent': total_spent,
            'monthly_average': monthly_average,
            'first_date': first_date.isoformat() if first_date else None,
            'last_date': last_date.isoformat() if last_date else None,
            'most_expensive': most_expensive,
            'subscriptions': subscriptions,
            'monthly_data': monthly_data
        })
        
    except Exception as e:
        print(f"Error in get_subs_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
