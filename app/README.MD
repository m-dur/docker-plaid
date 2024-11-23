## Setup
1. Copy `.env.example` to `.env` and fill in your credentials
2. The following files will be created automatically:
   - `access_tokens.json`: Stores Plaid access tokens
   - `cursor.json`: Manages Plaid transaction sync cursors
   - `link_token.json`: Stores Plaid link tokens

Note: These files contain sensitive information and are excluded from git via .gitignore
