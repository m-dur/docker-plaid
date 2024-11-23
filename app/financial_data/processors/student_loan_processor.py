import pandas as pd
import numpy as np
from datetime import datetime
import json

def process_student_loans(student_loans):
    """Process student loan data into DataFrame format"""
    #print("\n=== Processing Student Loans ===")
    #print(f"Number of student loans to process: {len(student_loans)}")
    
    if not student_loans:
        return pd.DataFrame()
    
    records = []
    for loan in student_loans:
        #print(f"\nProcessing loan: {loan.account_id}")
        
        # Convert disbursement dates to string format
        disbursement_dates = None
        if hasattr(loan, 'disbursement_dates'):
            try:
                disbursement_dates = json.dumps([d.isoformat() if isinstance(d, (datetime, datetime.date)) 
                                             else d for d in loan.disbursement_dates])
            except:
                disbursement_dates = None

        # Convert servicer address to string
        servicer_address = None
        if hasattr(loan, 'servicer_address'):
            try:
                address_dict = {
                    'street': getattr(loan.servicer_address, 'street', None),
                    'city': getattr(loan.servicer_address, 'city', None),
                    'state': getattr(loan.servicer_address, 'state', None),
                    'postal_code': getattr(loan.servicer_address, 'postal_code', None)
                }
                servicer_address = json.dumps(address_dict)
            except:
                servicer_address = None

        # Convert is_overdue to Python bool before adding to record
        is_overdue_value = getattr(loan, 'is_overdue', False)
        if isinstance(is_overdue_value, np.bool_):
            is_overdue_value = bool(is_overdue_value)

        record = {
            'account_id': str(loan.account_id),
            'account_number': str(getattr(loan, 'account_number', '')),
            'disbursement_dates': disbursement_dates,
            'expected_payoff_date': getattr(loan, 'expected_payoff_date', None),
            'guarantor': getattr(loan, 'guarantor', None),
            'interest_rate_percentage': float(getattr(loan, 'interest_rate_percentage', 0)) if getattr(loan, 'interest_rate_percentage', None) is not None else None,
            'is_overdue': is_overdue_value,
            'last_payment_amount': float(getattr(loan, 'last_payment_amount', 0)) if getattr(loan, 'last_payment_amount', None) is not None else None,
            'last_payment_date': getattr(loan, 'last_payment_date', None),
            'last_statement_balance': float(getattr(loan, 'last_statement_balance', 0)) if getattr(loan, 'last_statement_balance', None) is not None else None,
            'last_statement_issue_date': getattr(loan, 'last_statement_issue_date', None),
            'loan_name': getattr(loan, 'loan_name', None),
            'loan_status_type': getattr(loan.loan_status, 'type', None) if hasattr(loan, 'loan_status') else None,
            'minimum_payment_amount': float(getattr(loan, 'minimum_payment_amount', 0)) if getattr(loan, 'minimum_payment_amount', None) is not None else None,
            'next_payment_due_date': getattr(loan, 'next_payment_due_date', None),
            'origination_date': getattr(loan, 'origination_date', None),
            'origination_principal_amount': float(getattr(loan, 'origination_principal_amount', 0)) if getattr(loan, 'origination_principal_amount', None) is not None else None,
            'outstanding_interest_amount': float(getattr(loan, 'outstanding_interest_amount', 0)) if getattr(loan, 'outstanding_interest_amount', None) is not None else None,
            'payment_reference_number': getattr(loan, 'payment_reference_number', None),
            'pslf_status_estimated_eligibility_date': getattr(loan.pslf_status, 'estimated_eligibility_date', None) if hasattr(loan, 'pslf_status') else None,
            'pslf_status_payments_made': int(getattr(loan.pslf_status, 'payments_made', 0)) if hasattr(loan, 'pslf_status') else None,
            'pslf_status_payments_remaining': int(getattr(loan.pslf_status, 'payments_remaining', 0)) if hasattr(loan, 'pslf_status') else None,
            'repayment_plan_type': getattr(loan.repayment_plan, 'type', None) if hasattr(loan, 'repayment_plan') else None,
            'repayment_plan_description': getattr(loan.repayment_plan, 'description', None) if hasattr(loan, 'repayment_plan') else None,
            'sequence_number': getattr(loan, 'sequence_number', None),
            'servicer_address': servicer_address,
            'ytd_interest_paid': float(getattr(loan, 'ytd_interest_paid', 0)) if getattr(loan, 'ytd_interest_paid', None) is not None else None,
            'ytd_principal_paid': float(getattr(loan, 'ytd_principal_paid', 0)) if getattr(loan, 'ytd_principal_paid', None) is not None else None,
            'pull_date': datetime.now().date()
        }
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # Convert date columns
    date_columns = ['expected_payoff_date', 'last_payment_date', 'last_statement_issue_date',
                   'next_payment_due_date', 'origination_date', 'pslf_status_estimated_eligibility_date', 'pull_date']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            df[col] = df[col].where(df[col].notna(), None)
            df[col] = df[col].apply(lambda x: x.date() if x is not None else None)
    
    #print("\nProcessed DataFrame:")
    #print(df.dtypes)
    #print("\nSample data:")
    #print(df.head())
    
    return df
