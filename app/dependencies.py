from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from plaid import Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
SQLALCHEMY_DATABASE_URL = "sqlite:///./finance_app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Plaid client setup
plaid_client = Client(
    client_id=os.getenv('PLAID_CLIENT_ID', 'your_sandbox_client_id'),
    secret=os.getenv('PLAID_SECRET', 'your_sandbox_secret'),
    environment='sandbox'
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_plaid_client():
    return plaid_client