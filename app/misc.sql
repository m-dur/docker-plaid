-- to run lines, cmd + e
drop table institutions;
drop table account_types;
drop table accounts;
drop table account_subtypes;
-- All transactions

SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';


-- delete all tables
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    -- Disable foreign key checks during deletion
    EXECUTE 'SET CONSTRAINTS ALL DEFERRED';
    
    -- Drop all tables in public schema
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;

--delete rows from all tables
DO $$ 
DECLARE 
    r RECORD;
BEGIN
    -- Temporarily disable foreign key constraints
    EXECUTE 'SET CONSTRAINTS ALL DEFERRED';
    
    -- Get all tables and truncate them
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
    
    -- Re-enable constraints
    EXECUTE 'SET CONSTRAINTS ALL IMMEDIATE';
END $$;



-- existing tables
select * from transactions;
select * from accounts;
select * from account_types;
select * from depository_accounts;
select * from categories;
select * from investment_accounts;
select * from loan_accounts;
select * from credit_accounts;
select * from institutions;
select * from category_mappings;

-- deleting rows in table [TESTING]




--checking rows of every table in my database


SELECT 
    schemaname,
    relname as table_name,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

with daily_sum as (
    SELECT 
    date,
    group_name,
    sum(amount) as daily_sum
FROM transactions
LEFT JOIN categories
    ON categories.id = transactions.category_type_id
WHERE group_name IN ('digital purchase', 'travel')
group by 1,2
ORDER BY 1
)

select * 
    , sum(daily_sum) over (partition by group_name order by date rows between 2 preceding and current row) as moving_avg_3d
    , SUM(daily_sum) OVER (
        PARTITION BY group_name, DATE_TRUNC('month', date)  -- or EXTRACT(month FROM date)
) as month_sum,
row_number() over (partition by group_name, date order by daily_sum) as daily_rank
from daily_sum;

WITH daily_sum AS (
    SELECT 
        date,
        group_name,
        SUM(amount) as daily_sum
    FROM transactions
    LEFT JOIN categories
        ON categories.id = transactions.category_type_id
    WHERE group_name IN ('digital purchase', 'travel')
    GROUP BY 1,2
),
ranked_transactions AS (
    SELECT 
        date,
        group_name,
        daily_sum,
        DATE_TRUNC('month', date) as month,
        ROW_NUMBER() OVER (
            PARTITION BY group_name, DATE_TRUNC('month', date)
            ORDER BY daily_sum DESC
        ) as rank
    FROM daily_sum
)
SELECT *
FROM ranked_transactions
WHERE rank < 3
ORDER BY month, group_name, rank;