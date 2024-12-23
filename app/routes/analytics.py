from flask import Blueprint, jsonify, request, render_template, current_app
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from financial_data.utils.db_connection import get_db_connection
from psycopg2.extras import RealDictCursor, DictCursor
import calendar
from zoneinfo import ZoneInfo

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
            FROM stg_transactions t
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
            LEFT JOIN stg_transactions t ON 
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
            LEFT JOIN stg_transactions t ON 
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
            FROM stg_transactions t
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
            LEFT JOIN stg_transactions t ON 
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
            LEFT JOIN stg_transactions t ON 
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
            FROM stg_transactions t
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
            LEFT JOIN stg_transactions t ON 
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
            LEFT JOIN stg_transactions t ON 
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
            LEFT JOIN stg_transactions t ON 
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
        
        current_timestamp = datetime.now(ZoneInfo("America/Los_Angeles"))
        pacific_time = current_timestamp
        
        current_month = datetime.strptime(month, '%Y-%m').replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        prior_month = current_month - relativedelta(months=1)

        # Get the last day for both months
        _, current_last_day = calendar.monthrange(current_month.year, current_month.month)
        _, prior_last_day = calendar.monthrange(prior_month.year, prior_month.month)
        
        # Set exact date ranges
        current_start = current_month.replace(day=1)
        current_end = current_month.replace(day=current_last_day)
        prior_start = prior_month.replace(day=1)
        prior_end = prior_month.replace(day=prior_last_day)
        
        base_query = """
        WITH RECURSIVE dates AS (
            SELECT generate_series(
                DATE_TRUNC('month', %s::timestamptz),
                (DATE_TRUNC('month', %s::timestamptz) + INTERVAL '1 month - 1 day'),
                '1 day'::interval
            )::date AS date
        ),
        daily_totals AS (
            SELECT 
                EXTRACT(DAY FROM (date AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date) as day_of_month,
                COALESCE(SUM(amount), 0) as daily_amount
            FROM stg_transactions 
            WHERE date >= %s::timestamptz 
            AND date < %s::timestamptz + INTERVAL '1 day'
            AND amount > 0
            AND LOWER(COALESCE(category, '')) NOT LIKE '%%transfer%%'
            {category_filter}
            GROUP BY EXTRACT(DAY FROM (date AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date)
        )
        SELECT 
            d.date,
            COALESCE(SUM(dt.daily_amount) OVER (ORDER BY d.date), 0) as cumulative_amount
        FROM dates d
        LEFT JOIN daily_totals dt ON EXTRACT(DAY FROM d.date) = dt.day_of_month
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
        params = [current_start, current_end, prior_start, prior_end]
        if category != 'all':
            params.append(category)
        cur.execute(query, tuple(params))
        prior_results = cur.fetchall()

        # Pad prior month results if needed
        prior_amounts = [float(row[1]) for row in prior_results]
        if len(prior_amounts) < len(current_results):
            last_value = prior_amounts[-1] if prior_amounts else 0
            prior_amounts.extend([last_value] * (len(current_results) - len(prior_amounts)))

        current_pacific_date = pacific_time.strftime('%Y-%m-%d')
        current_dates = [row[0].strftime('%Y-%m-%d') for row in current_results]
        
        return jsonify({
            'dates': current_dates,
            'amounts': [float(row[1]) for row in current_results],
            'prior_amounts': prior_amounts,
            'current_date': current_pacific_date
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
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        current_timestamp = datetime.now(ZoneInfo("America/Los_Angeles"))
        pacific_time = current_timestamp
        
        current_month = datetime.strptime(month, '%Y-%m').replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        prior_month = current_month - relativedelta(months=1)

        # Get the last day for both months
        _, current_last_day = calendar.monthrange(current_month.year, current_month.month)
        _, prior_last_day = calendar.monthrange(prior_month.year, prior_month.month)
        
        # Set exact date ranges
        current_start = current_month.replace(day=1)
        current_end = current_month.replace(day=current_last_day)
        prior_start = prior_month.replace(day=1)
        prior_end = prior_month.replace(day=prior_last_day)
        
        base_query = """
        WITH RECURSIVE dates AS (
            SELECT generate_series(
                DATE_TRUNC('month', %s::timestamptz),
                (DATE_TRUNC('month', %s::timestamptz) + INTERVAL '1 month - 1 day'),
                '1 day'::interval
            )::date AS date
        ),
        daily_totals AS (
            SELECT 
                EXTRACT(DAY FROM (date AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date) as day_of_month,
                COALESCE(SUM(amount), 0) as daily_amount
            FROM stg_transactions 
            WHERE date >= %s::timestamptz 
            AND date < %s::timestamptz + INTERVAL '1 day'
            AND amount > 0
            AND LOWER(COALESCE(group_name, '')) NOT LIKE '%%transfer%%'
            {group_filter}
            GROUP BY EXTRACT(DAY FROM (date AT TIME ZONE 'UTC' AT TIME ZONE 'America/Los_Angeles')::date)
        )
        SELECT 
            d.date,
            COALESCE(SUM(dt.daily_amount) OVER (ORDER BY d.date), 0) as cumulative_amount
        FROM dates d
        LEFT JOIN daily_totals dt ON EXTRACT(DAY FROM d.date) = dt.day_of_month
        ORDER BY d.date;
        """
        
        group_filter = "AND group_name = %s" if group != 'all' else ""
        query = base_query.format(group_filter=group_filter)
        
        # Get current month data using current month's date range
        params = [current_start, current_end, current_start, current_end]
        if group != 'all':
            params.append(group)
        cur.execute(query, tuple(params))
        current_results = cur.fetchall()
        
        # Get prior month data using prior month's date range
        params = [current_start, current_end, prior_start, prior_end]  # Use current dates for x-axis but prior dates for data
        if group != 'all':
            params.append(group)
        cur.execute(query, tuple(params))
        prior_results = cur.fetchall()

        # Pad prior month results if needed (in case prior month was shorter)
        prior_amounts = [float(row[1]) for row in prior_results]
        if len(prior_amounts) < len(current_results):
            last_value = prior_amounts[-1] if prior_amounts else 0
            prior_amounts.extend([last_value] * (len(current_results) - len(prior_amounts)))

        current_pacific_date = pacific_time.strftime('%Y-%m-%d')
        current_dates = [row[0].strftime('%Y-%m-%d') for row in current_results]
        
        return jsonify({
            'dates': current_dates,
            'amounts': [float(row[1]) for row in current_results],
            'prior_amounts': prior_amounts,
            'current_date': current_pacific_date
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in expenses_group_daily: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/cashflow')
def cashflow():
    return render_template('cashflow.html')

@analytics_bp.route('/api/cashflow')
def cashflow_summary():
    try:
        start_date = datetime(2024, 7, 1)
        
        # Get the latest transaction date
        conn = get_db_connection()
        cur = conn.cursor()
        
        latest_date_query = """
        SELECT MAX(date) FROM stg_transactions;
        """
        cur.execute(latest_date_query)
        end_date = cur.fetchone()[0]
        
        current_app.logger.info(f"Using dates - Start: {start_date}, End: {end_date}")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
        WITH RECURSIVE date_series AS (
            SELECT generate_series(
                %s::timestamp,
                %s::timestamp,
                '1 month'
            )::date as month
        ),
        monthly_flows AS (
            SELECT 
                DATE_TRUNC('month', ds.month) as month,
                COALESCE(SUM(CASE 
                    WHEN t.amount < 0 
                    AND LOWER(COALESCE(t.category, '')) NOT LIKE '%%transfer%%'
                    THEN ABS(t.amount) 
                    ELSE 0 
                END), 0) as inflow,
                COALESCE(SUM(CASE 
                    WHEN t.amount > 0 
                    AND (t.name ILIKE '%%External Withdrawal%%' or t.name ilike '%%Zelle To ZIQI%%' or t.name ILIKE '%%Check%%')
                    AND t.name not ilike '%%MONEYLINE%%'
                    AND t.name not ilike '%%WF%%'
                    THEN t.amount 
                    ELSE 0 
                END), 0) as outflow
            FROM date_series ds
            LEFT JOIN stg_transactions t ON 
                DATE_TRUNC('month', t.date) = DATE_TRUNC('month', ds.month)
            GROUP BY DATE_TRUNC('month', ds.month)
            ORDER BY DATE_TRUNC('month', ds.month)
        )
        SELECT 
            to_char(month, 'Mon YYYY') as month_label,
            ROUND(inflow::numeric, 2) as inflow,
            ROUND(outflow::numeric, 2) as outflow,
            ROUND((inflow - outflow)::numeric, 2) as net_flow
        FROM monthly_flows
        ORDER BY month;
        """
        
        try:
            cur.execute(query, (start_date, end_date))
            results = cur.fetchall()
            current_app.logger.info(f"Retrieved {len(results)} rows")
            
            # Debug log the first few results
            for i, row in enumerate(results[:3]):
                current_app.logger.debug(f"Row {i}: {row}")
            
            if not results:
                return jsonify({
                    'total_cash_in': 0,
                    'total_cash_out': 0,
                    'net_cash_flow': 0,
                    'months': [],
                    'cash_in': [],
                    'cash_out': [],
                    'net_flow': []
                })
            
            # Process results with explicit indices
            months = []
            cash_in = []
            cash_out = []
            net_flow = []
            
            for row in results:
                try:
                    months.append(str(row[0]))  # Month label
                    cash_in.append(float(row[1]))  # Inflow
                    cash_out.append(float(row[2]))  # Outflow
                    net_flow.append(float(row[3]))  # Net flow
                except Exception as e:
                    current_app.logger.error(f"Error processing row {row}: {str(e)}")
                    continue
            
            # Calculate totals
            total_cash_in = sum(cash_in)
            total_cash_out = sum(cash_out)
            net_cash_flow = total_cash_in - total_cash_out
            
            # Add query for transactions using same logic as monthly summary
            transactions_query = """
            WITH cash_flows AS (
                SELECT 
                    date,
                    name as description,
                    category,
                    CASE 
                        WHEN amount < 0 
                        AND LOWER(COALESCE(category, '')) NOT LIKE '%%transfer%%'
                        THEN ABS(amount)
                        ELSE 0 
                    END as inflow,
                    CASE 
                        WHEN amount > 0 
                        AND (name ILIKE '%%External Withdrawal%%' or name ilike '%%Zelle To ZIQI%%' or name ILIKE '%%Check%%')
                        AND name not ilike '%%MONEYLINE%%'
                        AND name not ilike '%%WF%%'
                        THEN amount
                        ELSE 0 
                    END as outflow
                FROM stg_transactions 
                WHERE date BETWEEN %s AND %s
            )
            SELECT 
                date,
                description,
                category,
                inflow,
                outflow
            FROM cash_flows
            WHERE inflow > 0 OR outflow > 0
            ORDER BY date DESC
            """
            
            cur.execute(transactions_query, (start_date, end_date))
            transactions = [{
                'date': row[0].strftime('%Y-%m-%d'),
                'description': row[1],
                'category': row[2] or 'Uncategorized',
                'amount': float(row[3] if row[3] > 0 else -row[4])
            } for row in cur.fetchall()]
            
            # Add this query right after the transactions_query (around line 928)
            summary_query = """
            WITH cash_flows AS (
                SELECT 
                    name as description,
                    CASE 
                        WHEN amount > 0 
                        AND (name ILIKE '%%External Withdrawal%%' or name ilike '%%Zelle To ZIQI%%' or name ILIKE '%%Check%%')
                        AND name not ilike '%%MONEYLINE%%'
                        AND name not ilike '%%WF%%'
                        THEN amount
                        ELSE 0 
                    END as outflow
                FROM stg_transactions 
                WHERE date BETWEEN %s AND %s
            )
            SELECT 
                description,
                SUM(outflow) as total_outflow,
                COUNT(*) as transaction_count,
                ROUND(AVG(outflow), 2) as avg_outflow
            FROM cash_flows
            WHERE outflow > 0
            GROUP BY description
            ORDER BY total_outflow DESC;
            """
            
            cur.execute(summary_query, (start_date, end_date))
            outflow_summary = [{
                'description': row[0],
                'total': float(row[1]),
                'count': row[2],
                'average': float(row[3])
            } for row in cur.fetchall()]
            
            return jsonify({
                'total_cash_in': total_cash_in,
                'total_cash_out': total_cash_out,
                'net_cash_flow': net_cash_flow,
                'months': months,
                'cash_in': cash_in,
                'cash_out': cash_out,
                'net_flow': net_flow,
                'transactions': transactions,
                'outflow_summary': outflow_summary
            })
            
        except Exception as e:
            current_app.logger.error(f"Query execution error: {str(e)}")
            current_app.logger.error(f"Query being executed: {query}")
            current_app.logger.error(f"Parameters: {(start_date, end_date)}")
            raise
            
    except Exception as e:
        current_app.logger.error(f"Error in cashflow_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/balances')
def balances():
    return render_template('balances.html')

@analytics_bp.route('/api/balances')
def get_balances():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        WITH base AS (
            SELECT DISTINCT ON (ca.account_id)
                ca.account_name,
                ca.balance_current as bal_cur,
                ca.balance_limit as bal_limit,
                ah.institution_id,
                i.transactions_last_successful_update as last_update
            FROM credit_accounts ca
            JOIN account_history ah ON ca.account_id = ah.account_id
            LEFT JOIN items i ON ah.institution_id = i.institution_id
            WHERE ah.type = 'credit'
            ORDER BY ca.account_id, ah.created_at DESC
        )
        SELECT 
            account_name,
            bal_cur,
            bal_limit,
            last_update,
            ROUND((bal_cur / NULLIF(bal_limit, 0) * 100)::numeric, 2) as util_rate
        FROM base
        UNION ALL
        SELECT 
            'Total' as account_name,
            SUM(bal_cur) as bal_cur,
            SUM(bal_limit) as bal_limit,
            MAX(last_update) as last_update,
            ROUND((SUM(bal_cur) / NULLIF(SUM(bal_limit), 0) * 100)::numeric, 2) as util_rate
        FROM base
        ORDER BY util_rate DESC;
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        return jsonify([dict(row) for row in results])
        
    except Exception as e:
        current_app.logger.error(f"Error in get_balances: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/daily/expenses')
def daily_expenses():
    try:
        selected_month = request.args.get('month')  # Format: "YYYY-MM"
        
        # Convert selected_month to start and end dates
        start_date = datetime.strptime(f"{selected_month}-01", "%Y-%m-%d")
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
        WITH daily_expenses AS (
            SELECT 
                date_trunc('day', date) as day,
                name as description,
                category,
                amount
            FROM stg_transactions
            WHERE date >= %s 
            AND date < %s
            AND amount > 0
            AND LOWER(COALESCE(category, '')) NOT LIKE '%%transfer%%'
            ORDER BY date
        )
        SELECT 
            EXTRACT(DAY FROM day) as day_of_month,
            json_agg(
                json_build_object(
                    'description', description,
                    'category', COALESCE(category, 'Uncategorized'),
                    'amount', amount
                )
            ) as transactions,
            SUM(amount) as daily_total
        FROM daily_expenses
        GROUP BY day_of_month
        ORDER BY day_of_month;
        """
        
        cur.execute(query, (start_date, end_date))
        results = cur.fetchall()
        
        # Initialize days dictionary
        days = {}
        
        # Process results
        for row in results:
            day = int(row[0])
            days[day] = {
                'total': float(row[2]),
                'transactions': row[1]
            }
        
        return jsonify({'days': days})
        
    except Exception as e:
        current_app.logger.error(f"Error in daily_expenses: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/daily')
def daily():
    return render_template('daily.html')

@analytics_bp.route('/bank-balances')
def bank_balances():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        WITH base AS (
            SELECT
                a.account_name,
                d.balance_current,
                d.pull_date,
                0 as sort_order
            FROM depository_accounts d
            JOIN accounts a ON d.account_id = a.account_id
        )
        SELECT *
        FROM base
        UNION ALL
        SELECT 
            'Total' as account_name,
            SUM(balance_current) as balance_current,
            MAX(pull_date) as pull_date,
            1 as sort_order
        FROM base
        ORDER BY sort_order, account_name;
        """
        
        cur.execute(query)
        accounts = cur.fetchall()
        
        return render_template('bank_balances.html', accounts=accounts)
        
    except Exception as e:
        current_app.logger.error(f"Error in bank_balances: {str(e)}")
        return render_template('bank_balances.html', accounts=[])
    finally:
        cur.close()
        conn.close()

@analytics_bp.route('/api/bank-balances')
def get_bank_balances():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        WITH base AS (
            SELECT
                a.account_name,
                d.balance_current as current_balance,
                d.balance_available as available_balance,
                d.pull_date
            FROM depository_accounts d
            JOIN accounts a ON d.account_id = a.account_id
        )
        SELECT *,
            ROUND(current_balance::numeric, 2) as current_balance,
            ROUND(available_balance::numeric, 2) as available_balance
        FROM base
        UNION ALL
        SELECT 
            'Total' as account_name,
            ROUND(SUM(current_balance)::numeric, 2) as current_balance,
            ROUND(SUM(available_balance)::numeric, 2) as available_balance,
            MAX(pull_date) as pull_date
        FROM base
        ORDER BY 
            CASE WHEN account_name = 'Total' THEN 1 ELSE 0 END,
            account_name;
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        return jsonify([dict(row) for row in results])
        
    except Exception as e:
        current_app.logger.error(f"Error in get_bank_balances: {str(e)}")
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
