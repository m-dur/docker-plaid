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
    last_statement_balance DECIMAL(12,2),
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

CREATE OR REPLACE VIEW credit_accounts AS 
SELECT DISTINCT ON (account_id)
    account_id,
    balance_current,
    balance_available,
    balance_limit,
    last_statement_balance,
    last_statement_date,
    minimum_payment_amount,
    next_payment_due_date,
    apr_percentage,
    apr_type,
    balance_subject_to_apr,
    interest_charge_amount,
    pull_date,
    created_at
FROM account_history
WHERE type = 'credit'
    AND created_at = (
        SELECT MAX(created_at) 
        FROM account_history 
        WHERE type = 'credit'
    )
ORDER BY account_id, created_at DESC;





-- loan accounts
CREATE TABLE loan_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    original_loan_amount DECIMAL(12,2),
    interest_rate DECIMAL(6,3),
    pull_date DATE DEFAULT CURRENT_DATE
);




-- Investment Accounts
CREATE TABLE investment_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    pull_date DATE DEFAULT CURRENT_DATE
);


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
CREATE TABLE api_calls (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    is_plaid BOOLEAN NOT NULL,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caller_type VARCHAR(50),  -- 'user', 'system', 'webhook', etc.
    caller_id VARCHAR(100),   -- user_id, system_process_id, etc.
    response_time FLOAT,      -- in seconds
    status_code INTEGER,
    error TEXT,
    request_payload JSONB,    -- store request parameters
    response_payload JSONB    -- store response data (if needed)
);

DELETE FROM plaid_api_calls;