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

-- Accounts


CREATE TABLE accounts (
    account_id VARCHAR(255) PRIMARY KEY,
    account_name VARCHAR(255),
    institution_id VARCHAR(255) REFERENCES institutions(id),
    type VARCHAR(50),
    subtype VARCHAR(50),
    mask VARCHAR(20),
    verification_status VARCHAR(50),
    currency VARCHAR(3),
    last_updated_datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pull_date DATE DEFAULT CURRENT_DATE
);

-- loan accounts
CREATE TABLE loan_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    original_loan_amount DECIMAL(12,2),
    interest_rate DECIMAL(6,3),
    pull_date DATE DEFAULT CURRENT_DATE
);


-- Depository Accounts 
CREATE TABLE depository_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    balance_available DECIMAL(12,2),
    pull_date DATE DEFAULT CURRENT_DATE
);

-- Credit Accounts
CREATE TABLE credit_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
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
    pull_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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