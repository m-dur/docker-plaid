WITH source AS (
    SELECT * FROM {{ source('raw', 'transactions') }}
),

renamed AS (
    SELECT
        id,
        plaid_transaction_id,
        amount,
        date,
        description,
        category,
        CASE
            WHEN amount < 0 THEN 'expense'
            ELSE 'income'
        END AS transaction_type
    FROM source
)

SELECT * FROM renamed