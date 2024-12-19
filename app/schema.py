from financial_data.utils.db_connection import get_db_connection

def generate_schema_html():
    """Generate HTML representation of database schema"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get all tables and their columns with types, constraints
        cur.execute("""
            SELECT 
                t.table_name,
                array_agg(
                    json_build_object(
                        'column_name', c.column_name,
                        'data_type', c.data_type,
                        'is_nullable', c.is_nullable,
                        'column_default', c.column_default,
                        'is_pk', CASE 
                            WHEN tc.constraint_type = 'PRIMARY KEY' THEN true 
                            ELSE false 
                        END,
                        'is_fk', CASE 
                            WHEN tc.constraint_type = 'FOREIGN KEY' THEN true 
                            ELSE false 
                        END
                    ) ORDER BY c.ordinal_position
                ) as columns
            FROM information_schema.tables t
            JOIN information_schema.columns c 
                ON t.table_name = c.table_name
            LEFT JOIN information_schema.key_column_usage kcu
                ON c.table_name = kcu.table_name 
                AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc
                ON kcu.constraint_name = tc.constraint_name
                AND kcu.table_name = tc.table_name
            WHERE t.table_schema = 'public'
            AND t.table_type = 'BASE TABLE'
            GROUP BY t.table_name
            ORDER BY t.table_name;
        """)
        
        tables = cur.fetchall()
        
        # Generate HTML with minimal whitespace
        html = '<div class="schema-container">'
        
        for table_name, columns in tables:
            html += f'<div class="table-box"><div class="table-name">{table_name}</div><div class="table-columns">'
            
            for col in columns:
                # Determine column class for styling
                col_class = ''
                if col['is_pk']:
                    col_class = 'primary-key'
                elif col['is_fk']:
                    col_class = 'foreign-key'
                
                # Format column info with minimal whitespace
                col_info = f"{col['column_name']}:{col['data_type']}"  # Removed space after colon
                if col['column_default']:
                    col_info += f"={col['column_default']}"  # Removed spaces around equals
                if col['is_nullable'] == 'NO':
                    col_info += "(NOT NULL)"  # Removed spaces inside parentheses
                
                html += f'<div class="column {col_class}">{col_info}</div>'
            
            html += '</div></div>'
        
        html += '</div>'
        return html
        
    finally:
        cur.close()
        conn.close()
