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




--checking rows of every table in my database

SELECT 
    schemaname,
    relname as table_name,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;



-- updating amazon prime store card transactions
UPDATE transactions 
SET category = 'Shopping',
    group_name = 'Misc'
WHERE account_id IN (
    SELECT account_id 
    FROM accounts 
    WHERE account_name = 'Prime Store Card'
)
AND name != 'Amazon Prime';

-- checking balance info for credit cards
with base as (
  select
    account_name,
    balance_current as bal_cur,
    balance_available as bal_avail
  from credit_accounts
)

select *
    , round((bal_cur / nullif(bal_avail, 0) * 100)::numeric, 2) as util_rate
from base
union all
select 
    'Total' as account_name,
    sum(bal_cur) as bal_cur,
    sum(bal_avail) as bal_avail,
    round((sum(bal_cur) / nullif(sum(bal_avail), 0) * 100)::numeric, 2) as util_rate
from base
order by 4 desc




SELECT * FROM account_history

-- Update credit limit for Visa Credit Card
UPDATE account_history
SET balance_limit = COALESCE(balance_limit, 0) + 27000
WHERE account_id IN (
    SELECT account_id 
    FROM accounts 
    WHERE account_name = 'Visa Credit Card'
)
AND pull_date = (
    SELECT MAX(pull_date) 
    FROM account_history ah2 
    WHERE ah2.account_id = account_history.account_id
);


select account_name
    , min(balance_current) as min_balance_current
    , max(balance_current) as max_balance_current
    , min(balance_limit) as min_balance_limit
    , max(balance_limit) as max_balance_limit
    , min(created_at) as min_created_at
    , max(created_at) as max_created_at
from account_history
group by 1
order by 1



