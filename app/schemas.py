from pydantic import BaseModel
from datetime import date

class TransactionBase(BaseModel):
    amount: float
    date: date
    description: str
    category: str

class TransactionCreate(TransactionBase):
    plaid_transaction_id: str

class Transaction(TransactionBase):
    id: int
    plaid_transaction_id: str

    class Config:
        orm_mode = True