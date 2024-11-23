from financial_data.config.db_config import get_db_connection

def generate_db_schema():
    tables_html = []
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get tables and their columns with types
    cur.execute("""
        SELECT 
            t.table_name,
            array_agg(
                json_build_object(
                    'name', c.column_name,
                    'type', c.data_type,
                    'is_pk', CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END,
                    'is_fk', CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END
                )
                ORDER BY c.ordinal_position
            ) as columns
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
        ) pk ON t.table_name = pk.table_name AND c.column_name = pk.column_name
        LEFT JOIN (
            SELECT kcu.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
        ) fk ON t.table_name = fk.table_name AND c.column_name = fk.column_name
        WHERE t.table_schema = 'public'
        AND t.table_name NOT LIKE 'pg_%'
        GROUP BY t.table_name;
    """)
    
    tables = cur.fetchall()
    
    for table_name, columns in tables:
        table_html = f"""
        <div class="table-box">
            <div class="table-name">{table_name}</div>
            <div class="table-columns">
        """
        
        for column in columns:
            col_class = 'primary-key' if column['is_pk'] else 'foreign-key' if column['is_fk'] else ''
            table_html += f"""
                <div class="column {col_class}">
                    {column['name']}: {column['type']}
                </div>
            """
        
        table_html += """
            </div>
        </div>
        """
        tables_html.append(table_html)
    
    cur.close()
    conn.close()
    
    return '<div class="schema-container">' + ''.join(tables_html) + '</div>'
