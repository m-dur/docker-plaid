import logging
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.exceptions import ApiException
from datetime import datetime, timedelta
from . import models
from .dependencies import get_db, get_plaid_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/fetch-plaid-transactions/")
def fetch_plaid_transactions(db: Session = Depends(get_db), plaid_client: plaid_api.PlaidApi = Depends(get_plaid_client)):
    # In a real application, you'd retrieve this token securely for each user
    access_token = 'access-sandbox-f94c0541-74f8-409f-85a3-4f9ab2ad6d92'
    
    start_date = (datetime.now() - timedelta(days=30)).date()
    end_date = datetime.now().date()
    
    try:
        request = TransactionsGetRequest(
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            options=TransactionsGetRequestOptions(
                count=100,
                offset=0
            )
        )
        response = plaid_client.transactions_get(request)
        transactions = response.transactions
        
        new_transactions = 0
        for transaction in transactions:
            # Check if transaction already exists
            existing_transaction = db.query(models.Transaction).filter_by(
                plaid_transaction_id=transaction.transaction_id
            ).first()
            
            if existing_transaction is None:
                db_transaction = models.Transaction(
                    plaid_transaction_id=transaction.transaction_id,
                    amount=transaction.amount,
                    date=transaction.date,
                    description=transaction.name,
                    category=transaction.category[0] if transaction.category else 'Uncategorized'
                )
                db.add(db_transaction)
                new_transactions += 1
        
        db.commit()
        logger.info(f"Fetched {len(transactions)} transactions, {new_transactions} new transactions stored")
        return {"message": f"Fetched {len(transactions)} transactions, {new_transactions} new transactions stored"}
    
    except ApiException as e:
        logger.error(f"Plaid API error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Plaid API error: {str(e)}")
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")