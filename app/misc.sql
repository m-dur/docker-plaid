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

-- Verify the update
SELECT 
    a.account_name,
    ah.pull_date,
    ah.balance_limit
FROM account_history ah
JOIN accounts a ON ah.account_id = a.account_id
WHERE a.account_name = 'Visa Credit Card'
ORDER BY ah.pull_date DESC
LIMIT 1;

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

select * from account_history;

SELECT *
FROM account_history
WHERE type = 'credit'
ORDER BY pull_date DESC

-- current order
-- history_id: integer
-- account_id: character varying
-- account_name: character varying
-- institution_id: character varying
-- type: character varying
-- subtype: character varying
-- mask: character varying
-- verification_status: character varying
-- currency: character varying
-- balance_current: numeric
-- balance_available: numeric
-- balance_limit: numeric
-- last_statement_balance: numeric
-- last_statement_date: date
-- minimum_payment_amount: numeric
-- next_payment_due_date: date
-- apr_percentage: numeric
-- apr_type: character varying
-- balance_subject_to_apr: numeric
-- interest_charge_amount: numeric
-- created_at: timestamp without time zone
-- pull_date: date
-- last_payment_date: date
-- last_payment_amount: numeric
-- last_statement_issue_date: date

-- requested order
-- history_id: integer
-- account_id: character varying
-- account_name: character varying
-- institution_id: character varying
-- type: character varying
-- subtype: character varying
-- mask: character varying
-- verification_status: character varying
-- currency: character varying
-- balance_current: numeric
-- balance_available: numeric
-- balance_limit: numeric
-- last_statement_issue_date: date
-- last_statement_balance: numeric
-- last_payment_amount: numeric
-- last_payment_date: date
-- last_statement_date: date
-- minimum_payment_amount: numeric
-- next_payment_due_date: date
-- apr_percentage: numeric
-- apr_type: character varying
-- balance_subject_to_apr: numeric
-- interest_charge_amount: numeric
-- created_at: timestamp without time zone
-- pull_date: date
