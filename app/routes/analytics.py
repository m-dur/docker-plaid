from flask import Blueprint, jsonify, request, render_template, current_app
from datetime import datetime
from dateutil.relativedelta import relativedelta
from financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import RealDictCursor
import calendar

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/expenses')
def expenses():
    return render_template('expenses.html')

@analytics_bp.route('/expenses/group')
def expenses_group():
    return render_template('expenses_group.html')

@analytics_bp.route('/income')
def income():
    return render_template('income.html')

@analytics_bp.route('/net_income')
def net_income():
    return render_template('net_income.html')

@analytics_bp.route('/api/expenses/summary')
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

@analytics_bp.route('/api/expenses/monthly')
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
                AND LOWER(COALESCE(t.category, '')) NOT LIKE '%%transfer%%'
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

@analytics_bp.route('/api/expenses/group_summary')
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

@analytics_bp.route('/api/expenses/group_monthly')
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

@analytics_bp.route('/api/income/summary')
def income_summary():
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
            WHERE t.amount < 0
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
                ABS(t.amount) as amount,
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
        ORDER BY ft.date DESC, ft.amount DESC
        """
        cur.execute(query, tuple(params))
        results = cur.fetchall()
        
        # Calculate summary statistics
        total_income = sum(float(row[3]) for row in results)
        monthly_average = total_income / 12 if results else 0
        
        # Find highest income category
        category_totals = {}
        for row in results:
            category = row[2] or 'Uncategorized'
            amount = float(row[3])
            category_totals[category] = category_totals.get(category, 0) + amount
        
        highest_category = max(category_totals.items(), key=lambda x: x[1])[0] if category_totals else ''
        
        return jsonify({
            'total_income': total_income,
            'monthly_average': monthly_average,
            'highest_category': highest_category,
            'transactions': [{
                'transaction_id': row[0],
                'name': row[1],
                'category': row[2] or 'Uncategorized',
                'amount': float(row[3]),
                'date': row[4].isoformat(),
                'percentage': float(row[5] or 0)
            } for row in results]
        })
        
    except Exception as e:
        print(f"Error in income_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/income/monthly')
def income_monthly():
    category = request.args.get('category', 'all')
    start_date = datetime.fromisoformat(request.args.get('start_date').replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(request.args.get('end_date').replace('Z', '+00:00'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if category != 'all':
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(ABS(t.amount)), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount < 0
                AND category = %s
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
            """
            cur.execute(query, (start_date, end_date, category))
        else:
            query = """
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(ABS(t.amount)), 0) as total_amount
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND t.amount < 0
                AND LOWER(COALESCE(category, '')) NOT LIKE '%%transfer%%'
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
        print(f"Error in income_monthly: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/net_income/monthly')
def net_income_monthly():
    start_date = datetime.fromisoformat(request.args.get('start_date').replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(request.args.get('end_date').replace('Z', '+00:00'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        query = """
        WITH monthly_data AS (
            SELECT 
                DATE_TRUNC('month', d.date) as month,
                COALESCE(SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 0) as expenses
            FROM (
                SELECT generate_series(
                    DATE_TRUNC('month', %s::timestamp),
                    DATE_TRUNC('month', %s::timestamp),
                    '1 month'
                ) as date
            ) d
            LEFT JOIN transactions t ON 
                DATE_TRUNC('month', t.date) = d.date
                AND LOWER(COALESCE(t.category, '')) NOT LIKE '%%transfer%%'
            GROUP BY DATE_TRUNC('month', d.date)
            ORDER BY DATE_TRUNC('month', d.date)
        )
        SELECT 
            to_char(month, 'Month YYYY') as month,
            income,
            expenses,
            (income - expenses) as net_income
        FROM monthly_data
        """
        
        cur.execute(query, (start_date, end_date))
        results = cur.fetchall()
        
        months = []
        income = []
        expenses = []
        net = []
        
        for row in results:
            months.append(row[0].strip())
            income.append(float(row[1]))
            expenses.append(float(row[2]))
            net.append(float(row[3]))
            
        return jsonify({
            'months': months,
            'income': income,
            'expenses': expenses,
            'net': net
        })
    except Exception as e:
        print(f"Error in net_income_monthly: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/expenses/daily')
def expenses_daily():
    category = request.args.get('category', 'all')
    month = request.args.get('month')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Parse the selected month
        current_month = datetime.strptime(month, '%Y-%m')
        prior_month = current_month - relativedelta(months=1)
        
        # Get the last day of each month
        _, last_day = calendar.monthrange(current_month.year, current_month.month)
        _, prior_last_day = calendar.monthrange(prior_month.year, prior_month.month)
        
        # Set exact date ranges
        current_start = current_month.replace(day=1)
        current_end = current_month.replace(day=last_day)
        prior_start = prior_month.replace(day=1)
        prior_end = prior_month.replace(day=prior_last_day)
        
        base_query = """
        WITH RECURSIVE dates AS (
            SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date AS date
        ),
        daily_totals AS (
            SELECT 
                date::date, 
                COALESCE(SUM(amount), 0) as daily_amount
            FROM transactions 
            WHERE date >= %s::date 
            AND date <= %s::date
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
            'prior_amounts': [float(row[1]) for row in prior_results],
            'current_date': current_end.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in expenses_daily: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/expenses/group_daily')
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
        current_app.logger.error(f"Error in expenses_group_daily: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# Add all other analytics routes from app.py
# Including:
# - /api/expenses/monthly
# - /api/expenses/group_summary
# - /api/expenses/group_monthly
# - /api/income/summary
# - /api/income/monthly
# - /api/net_income/monthly

# [Rest of the analytics routes copied from app.py with Blueprint notation]
