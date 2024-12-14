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

-- deleting rows in table [TESTING]
DELETE FROM institutions 
WHERE id = 'ins_10';

-- modifying tables 
ALTER TABLE institutions 
ADD COLUMN 
ADD COLUMN ;

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

with base as (
    select *
from stg_transactions t
left join accounts a 
on t.account_id = a.account_id
) select date
    ,account_name
    , name
    , amount
    , count(*)
from base
group by 1,2,3,4
having count(*) >1;

with base as (select * FROM transactions t
left join accounts a 
on t.account_id = a.account_id
)
select account_name,
    amount,
    category 
    , pending_transaction_id
    , pending
from base;


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


select *
from transactions t
left join accounts a
on t.account_id = a.account_id
where account_name ilike '%Blue%'
;

SELECT 
    to_char(date, 'MM-YYYY') as transaction_date,
    sum(amount) as amount 
FROM transactions 
WHERE name ILIKE '%External Withdrawal%'
and name not ilike '%MONEYLINE%'
and name not ilike '%WF%'
GROUP BY 1 
ORDER BY 1;

select sum(amount)
from transactions
where date >= '2024-8-01' and date <= '2024-8-31'
AND (name ILIKE 'Check%' or name ILIKE 'External Withdrawal%')
and name not ilike '%WF%'
and name not ilike '%MONEYLINE%'
group by date
order by date;

select * from credit_accounts

UPDATE account_history 
SET balance_limit = 27000
WHERE account_name = (
    SELECT a.account_name
    FROM account_history ah
    JOIN accounts a ON a.account_id = ah.account_id
    WHERE a.account_name = 'Visa Credit Card'
    ORDER BY ah.created_at DESC
    LIMIT 1
);

select * 
from account_history
where account_name = 'Visa Credit Card';

-- trying to fix credit card hardcode to keep 27000 limit instead of getting overwritten
with base as (
  SELECT
    account_id,
    balance_current,
    balance_available,
    COALESCE(
      balance_limit,
      (
        SELECT balance_limit 
        FROM account_history ah2 
        WHERE ah2.account_id = account_history.account_id 
          AND ah2.balance_limit IS NOT NULL
          AND ah2.created_at <= account_history.created_at
          AND type = 'credit'
        ORDER BY created_at DESC 
        LIMIT 1
      )
    ) as balance_limit,
    last_statement_balance,
    last_statement_date,
    minimum_payment_amount,
    next_payment_due_date,
    apr_percentage,
    apr_type,
    balance_subject_to_apr,
    interest_charge_amount,
    pull_date,
    created_at,
    row_number() over (partition by account_id order by created_at desc) as row_num
  FROM account_history
  WHERE type = 'credit' 
  ORDER BY account_id, created_at DESC
)
select * 
from base 
where row_num = 1;

select * 
from credit_accounts