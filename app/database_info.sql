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


-- Table Creation

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

