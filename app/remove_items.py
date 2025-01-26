from app.financial_data.handlers.financial_data_handler import FinancialDataHandler

if __name__ == "__main__":
    handler = FinancialDataHandler()
    results = handler.remove_plaid_items_batch('remove.txt')