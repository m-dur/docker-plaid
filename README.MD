## Setup
1. Copy `.env.example` to `.env` and fill in your credentials
2. The following files will be created automatically:
   - `access_tokens.json`: Stores Plaid access tokens
   - `cursor.json`: Manages Plaid transaction sync cursors
   - `link_token.json`: Stores Plaid link tokens

Note: These files contain sensitive information and are excluded from git via .gitignore

## System Architecture
![System Architecture](http://www.plantuml.com/plantuml/proxy?src=https://raw.githubusercontent.com/YourUsername/YourRepo/main/app/diagrams/diagram.puml)

### Components
- **Web Application**: Contains the main Flask app and web interface
- **Services**: 
  - Plaid Service: Handles communication with Plaid API
  - Financial Data Handler: Processes and stores financial data
    - Account Processor: Handles account data
    - Institution Processor: Handles institution data
    - Transaction Processor: Handles transaction data
- **Storage**:
  - PostgreSQL Database: Stores all financial data
  - File Storage: Manages access tokens and sync cursors
