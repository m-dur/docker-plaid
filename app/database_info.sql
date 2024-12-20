--current tables
select * from transactions;
select * from category_mappings;
select * from accounts;
select * from depository_accounts;
select * from credit_accounts;
select * from investment_accounts;
select * from loan_accounts;
select * from institutions;
select * from category_mappings;
select * from group_mappings;
select * from institution_cursors;
select * from access_tokens;
select * from plaid_api_calls;

-- Table Creation
drop table institutions;

-- institutions
CREATE TABLE institutions (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(255),
    oauth BOOLEAN DEFAULT FALSE,
    refresh_interval VARCHAR(50),
    type TEXT,
    status VARCHAR(50),
    billed_products TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_refresh TIMESTAMP
);

-- Account history

CREATE TABLE account_history (
    history_id SERIAL PRIMARY KEY,
    account_id VARCHAR(255),
    account_name VARCHAR(255),
    institution_id VARCHAR(255) REFERENCES institutions(id),
    type VARCHAR(50),
    subtype VARCHAR(50),
    mask VARCHAR(20),
    verification_status VARCHAR(50),
    currency VARCHAR(3),
    balance_current DECIMAL(12,2),
    balance_available DECIMAL(12,2),
    balance_limit DECIMAL(12,2),
    last_statement_issue_date DATE,
    last_statement_balance DECIMAL(12,2),
    last_payment_amount DECIMAL(12,2),
    last_payment_date DATE,
    last_statement_date DATE,
    minimum_payment_amount DECIMAL(12,2),
    next_payment_due_date DATE,
    apr_percentage DECIMAL(5,2),
    apr_type VARCHAR(50),
    balance_subject_to_apr DECIMAL(12,2),
    interest_charge_amount DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pull_date DATE DEFAULT CURRENT_DATE
);

-- Current accounts view
CREATE OR REPLACE VIEW accounts AS
SELECT DISTINCT ON (account_id)
    account_id,
    account_name,
    institution_id,
    type,
    subtype,
    mask,
    verification_status,
    currency,
    pull_date
FROM account_history
ORDER BY account_id, pull_date DESC;

-- Current depository accounts view
CREATE OR REPLACE VIEW depository_accounts AS
SELECT DISTINCT ON (account_id)
    account_id,
    balance_current,
    balance_available,
    pull_date
FROM account_history
WHERE type = 'depository'
ORDER BY account_id, pull_date DESC;

-- Current credit accounts view
--drop view credit_accounts;
with base as (
  SELECT
    account_id,
    account_name,
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
    last_payment_date,
    last_payment_amount,
    last_statement_issue_date,
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




-- Category Mappings
CREATE TABLE category_mappings (
    transaction_name VARCHAR(255) PRIMARY KEY,
    category VARCHAR(255),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- group mappings 
CREATE TABLE group_mappings (
    transaction_name VARCHAR(255) PRIMARY KEY,
    group_name VARCHAR(255),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions
CREATE TABLE transactions (
    transaction_id VARCHAR(255) PRIMARY KEY,
    account_id VARCHAR(255) REFERENCES accounts(account_id),
    amount DECIMAL(12,2),
    date DATE,
    name VARCHAR(255),
    category VARCHAR(255),
    group_name VARCHAR(255),
    merchant_name VARCHAR(255),
    payment_channel VARCHAR(50),
    authorized_datetime TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pull_date DATE DEFAULT CURRENT_DATE
);

CREATE OR REPLACE VIEW stg_transactions AS
SELECT 
    transaction_id,
    account_id,
    amount,
    date,
    name,
    merchant_name,
    category,
    group_name,
    payment_channel,
    authorized_datetime,
    pull_date
FROM transactions 
WHERE pending = FALSE 
AND (pending_transaction_id IS NULL OR pending_transaction_id = '');


-- institution cursor
CREATE TABLE institution_cursors (
    cursor_id SERIAL PRIMARY KEY,
    institution_id VARCHAR(255) NOT NULL,
    cursor TEXT,
    first_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'pending',
    CONSTRAINT fk_institution_cursor
        FOREIGN KEY(institution_id) 
        REFERENCES institutions(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_institution_cursor
        UNIQUE(institution_id)
);

-- Access tokens
CREATE TABLE access_tokens (
    token_id SERIAL PRIMARY KEY,
    institution_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    item_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_institution_token
        FOREIGN KEY(institution_id) 
        REFERENCES institutions(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_institution_token
        UNIQUE(institution_id)
);

-- API Calls

CREATE TABLE plaid_api_calls (
    id INTEGER PRIMARY KEY,
    access_token_id INTEGER,
    product VARCHAR(255),
    operation VARCHAR(255),
    institution_id VARCHAR(255),
    request_timestamp TIMESTAMP WITHOUT TIME ZONE,
    response_time_ms INTEGER,
    error_code VARCHAR(255),
    error_message TEXT,
    success BOOLEAN,
    rate_limit_remaining INTEGER,
    items_retrieved INTEGER,
    request_id VARCHAR(255),
    cursor_used TEXT,
    next_cursor TEXT,
    has_more BOOLEAN,
    batch_number INTEGER,
    total_batches INTEGER
);

-- Add investment_accounts view
CREATE OR REPLACE VIEW investment_accounts AS
SELECT DISTINCT ON (account_id)
    account_id,
    balance_current numeric,
    pull_date date
FROM account_history
WHERE type = 'investment'
ORDER BY account_id, pull_date DESC;

-- Add loan_accounts view
CREATE OR REPLACE VIEW loan_accounts AS
SELECT DISTINCT ON (account_id)
    account_id,
    balance_current numeric,
    original_loan_amount numeric,
    interest_rate numeric,
    pull_date date
FROM account_history
WHERE type = 'loan'
ORDER BY account_id, pull_date DESC;

