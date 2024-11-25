# Financial Data Fetcher

A robust Flask-based application that integrates with Plaid API to fetch, process, and manage financial data across multiple institutions.

## Overview

This application serves as a financial data aggregator that:
- Connects to multiple banking institutions via Plaid
- Automatically syncs and categorizes transactions
- Provides a clean web interface for data visualization
- Maintains historical financial records in a PostgreSQL database

## Technical Architecture

### Key Components
1. **Web Application Layer**
   - Flask backend with dynamic templating
   - Interactive frontend using jQuery and Plaid Link
   - Real-time data updates and loading states

2. **Services Layer**
   - Plaid API integration for secure bank connections
   - Financial data processing pipeline
   - Transaction categorization system

3. **Storage Layer**
   - PostgreSQL database for structured data storage
   - JSON-based token management
   - Cursor-based transaction syncing

### Database Schema
The application uses a sophisticated database design with:
- Core tables (accounts, transactions)
- Reference tables (institutions, account_types)
- Specialized account tables (depository, credit, investment)
- Category mapping system for transaction classification

## Technical Features

- **Security**
  - Token-based authentication
  - Secure credential management
  - No storage of sensitive bank credentials

- **Data Processing**
  - Automated transaction categorization
  - Real-time data synchronization
  - Batch processing capabilities

- **User Interface**
  - Institution connection management
  - Transaction viewing and categorization
  - Database statistics dashboard
  - Loading states and error handling

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials
2. The following files will be created automatically:
   - `access_tokens.json`: Stores Plaid access tokens
   - `cursor.json`: Manages Plaid transaction sync cursors
   - `link_token.json`: Stores Plaid link tokens

Note: These files contain sensitive information and are excluded from git via .gitignore

## System Architecture

### Component Diagram
![System Architecture](docs/images/diagram.png)

### Database Schema
![Database Schema](docs/images/database.png)

## Technologies Used
- Backend: Python/Flask
- Database: PostgreSQL
- Frontend: HTML/CSS/JavaScript
- API Integration: Plaid API
- Data Processing: Pandas
- Visualization: PlantUML for diagrams

## Goals
- Provide a unified view of financial data across institutions
- Automate transaction categorization and analysis
- Maintain historical financial records
- Enable easy financial data management and visualization

## Future Enhancements
- Advanced analytics dashboard
- Machine learning for transaction categorization
- Export capabilities for financial planning
- Multi-user support with role-based access
