import pandas as pd
import os


class ExcelHandler:
    def __init__(self, excel_file='financial_data.xlsx'):
        self.EXCEL_FILE = excel_file

    def update_excel_file(self, new_transactions_df=None, new_bank_balances_df=None, 
                         new_credit_cards_df=None, new_student_loans_df=None, 
                         new_investments_df=None):
        #print("\n=== Updating Excel File ===")
        
        sheets_to_write = self._get_existing_sheets()
        self._update_sheets(sheets_to_write, {
            'Transactions': new_transactions_df,
            'Bank_Balances': new_bank_balances_df,
            'Credit_Cards': new_credit_cards_df,
            'Student_Loans': new_student_loans_df,
            'Investment_Accounts': new_investments_df
        })
        self._write_sheets(sheets_to_write)

    def _get_existing_sheets(self):
        sheets_to_write = {}
        if os.path.exists(self.EXCEL_FILE):
            with pd.ExcelFile(self.EXCEL_FILE) as xls:
                for sheet in xls.sheet_names:
                    sheets_to_write[sheet] = pd.read_excel(xls, sheet)
        return sheets_to_write

    def _update_sheets(self, sheets_to_write, new_data):
        for sheet_name, df in new_data.items():
            if df is not None and not df.empty:
                sheets_to_write[sheet_name] = df

    def _write_sheets(self, sheets_to_write):
        with pd.ExcelWriter(self.EXCEL_FILE, engine='openpyxl') as writer:
            for sheet_name, df in sheets_to_write.items():
                #print(f"Writing sheet: {sheet_name}")
                df.to_excel(writer, sheet_name=sheet_name, index=False)