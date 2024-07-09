from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    plaid_transaction_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    date = Column(Date)
    description = Column(String)
    category = Column(String)