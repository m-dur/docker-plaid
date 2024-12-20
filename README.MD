# Financial Data Fetcher

A Flask-based application that integrates with Plaid API to fetch, process, analyze, and visualize financial data across multiple institutions.

## Overview

This application serves as a comprehensive financial data management system that:
- Connects to multiple banking institutions via Plaid
- Automatically syncs and categorizes transactions
- Provides detailed financial analysis and visualizations
- Maintains historical financial records in a PostgreSQL database
- Offers real-time database statistics and monitoring

## Technical Architecture

### Key Components
1. **Web Application Layer**
   - Flask backend with modular routing system
   - Interactive frontend with real-time updates
   - Dynamic database schema visualization
   - Comprehensive error handling and loading states

2. **Analytics Layer**
   - Cash flow analysis
   - Income tracking and analysis
   - Net income calculations
   - Daily expense monitoring
   - Group-based expense categorization

3. **Services Layer**
   - Plaid API integration
   - Financial data processing pipeline
   - Transaction categorization system
   - Institution metadata management

4. **Storage Layer**
   - PostgreSQL database with views and materialized tables
   - API call tracking and monitoring
   - Cursor-based transaction syncing
   - Token management system

### Database Schema
The application uses a sophisticated database design with:
- Core tables (institutions, account_history)
- View tables (accounts, account type views)
- Transaction tables & views
- API tracking (plaid_api_calls)
- Authentication (access_tokens)
- Reference tables (category_mappings, group_mappings)

## Technical Features

- **Financial Analysis**
  - Cash flow visualization
  - Income analysis
  - Net income tracking
  - Daily expense monitoring
  - Credit card balance tracking
  - Bank account balance monitoring

- **Data Processing**
  - Automated transaction categorization
  - Real-time data synchronization
  - Group-based transaction mapping
  - Historical data tracking

- **User Interface**
  - Institution connection management
  - Real-time database statistics
  - Interactive data visualizations
  - Dynamic schema visualization
  - Loading states and error handling

## Setup
1. Configure PostgreSQL database
2. Copy `.env.example` to `.env` and configure:
   - Plaid API credentials
   - Database connection details
   - Environment settings
   - Webhook configurations

## System Architecture

### Component Overview
![Component Overview](app/static/images/diagrams/summary.png)

### Detailed Component Diagram
![Component Diagram](app/static/images/diagrams/diagram.png)

### Database Schema
![Database Schema](app/static/images/diagrams/database.png)

## Technologies Used
- Backend: Python/Flask
- Database: PostgreSQL
- Frontend: HTML/CSS/JavaScript/jQuery
- API Integration: Plaid API
- Visualization: PlantUML for diagrams
- Monitoring: Custom API tracking system

## Features
- Multi-institution support
- Real-time financial data syncing
- Comprehensive financial analysis
- Transaction categorization
- Group-based expense tracking
- Database statistics monitoring
- Schema visualization
- Historical data tracking

## Future Enhancements
- Machine learning for transaction categorization
- Advanced financial forecasting
- API performance optimization
- Enhanced error recovery mechanisms
- Extended analytics capabilities
