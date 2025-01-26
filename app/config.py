import os
from dotenv import load_dotenv
from pathlib import Path

# Get the directory of the current file
base_dir = Path(__file__).resolve().parent.parent

# Construct the path to the .env file
env_path = base_dir / '.env'

# Load the .env file
load_dotenv(dotenv_path=env_path)

#print(f"Loading .env file from: {env_path}")

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    PLAID_CLIENT_ID = os.environ.get('PLAID_CLIENT_ID')
    PLAID_SECRET = os.environ.get('PLAID_SECRET')
    PLAID_ENV = os.environ.get('PLAID_ENV', 'production')  # Change this to 'development' or 'production' when ready
    SESSION_SECRET_KEY = os.environ.get('SESSION_SECRET_KEY') or 'your-session-secret-key'
    LINK_TOKEN = os.environ.get('LINK_TOKEN')
    PLAID_WEBHOOK_SECRET = os.getenv('PLAID_WEBHOOK_SECRET')
    APP_URL = os.getenv('APP_URL', 'http://localhost:8000')

    @classmethod
    def print_config(cls):
        print(f"PLAID_CLIENT_ID: {'Set' if cls.PLAID_CLIENT_ID else 'Not set'}")
        print(f"PLAID_SECRET: {'Set' if cls.PLAID_SECRET else 'Not set'}")
        print(f"PLAID_ENV: {cls.PLAID_ENV}")

    @classmethod
    def validate_config(cls):
        if not cls.PLAID_CLIENT_ID or not isinstance(cls.PLAID_CLIENT_ID, str):
            raise ValueError("PLAID_CLIENT_ID is not set or not a string")
        if not cls.PLAID_SECRET or not isinstance(cls.PLAID_SECRET, str):
            raise ValueError("PLAID_SECRET is not set or not a string")
        if not cls.PLAID_ENV or not isinstance(cls.PLAID_ENV, str):
            raise ValueError("PLAID_ENV is not set or not a string")

# Call these functions when the app starts
#Config.print_config()
#Config.validate_config()

#print("Environment variables:")
#print(f"PLAID_ENV: {os.environ.get('PLAID_ENV')}")
