--current tables
select * from transactions;
select * from category_mappings;
select * from accounts;
select * from account_types;
select * from depository_accounts;
select * from credit_accounts;
select * from investment_accounts;
select * from loan_accounts;
select * from institutions;

-- Table Creation
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
-- indexed for transactions
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_pull_date ON transactions(pull_date);

-- Category Mappings
CREATE TABLE category_mappings (
    transaction_name VARCHAR(255) PRIMARY KEY,
    category VARCHAR(255),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Accounts
CREATE TABLE accounts (
    account_id VARCHAR(255) PRIMARY KEY,
    account_name VARCHAR(255),
    last_updated_datetime TIMESTAMP,
    account_type_id INTEGER REFERENCES account_types(id),
    institution_id VARCHAR(255) REFERENCES institutions(id),  -- Changed to VARCHAR to match institutions table
    mask VARCHAR(20),
    verification_status VARCHAR(50),
    currency VARCHAR(3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pull_date DATE DEFAULT CURRENT_DATE
);

-- account indexes
CREATE INDEX idx_accounts_type_id ON accounts(account_type_id);
CREATE INDEX idx_accounts_institution ON accounts(institution_id);
CREATE INDEX idx_accounts_pull_date ON accounts(pull_date);

-- Account Types
 CREATE TABLE account_types (
    id SERIAL PRIMARY KEY,
    account_type VARCHAR(50),
    subtype VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_type, subtype)
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

-- Credit accounts indexes
CREATE INDEX idx_credit_accounts_pull_date ON credit_accounts(pull_date); 

-- Investment Accounts
CREATE TABLE investment_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    pull_date DATE DEFAULT CURRENT_DATE
);

-- indexes
CREATE INDEX idx_depository_pull_date ON depository_accounts(pull_date);
CREATE INDEX idx_credit_pull_date ON credit_accounts(pull_date);
CREATE INDEX idx_loan_pull_date ON loan_accounts(pull_date);
CREATE INDEX idx_investment_pull_date ON investment_accounts(pull_date);

-- Loan Accounts
CREATE TABLE loan_accounts (
    account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(account_id),
    balance_current DECIMAL(12,2),
    original_loan_amount DECIMAL(12,2),
    interest_rate DECIMAL(6,3),
    pull_date DATE DEFAULT CURRENT_DATE
);

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