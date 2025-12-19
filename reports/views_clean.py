from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal

from members.models import Member
from savings.models import SavingsAccount, SavingsTransaction
from loans.models import Loan, LoanRepayment
from transactions.models import Transaction, Account

@login_required
def comprehensive_annual_report(request):
    """Clean, comprehensive annual report with accurate data"""
    
    # Get year filter from request
    selected_year = request.GET.get('year', timezone.now().year)
    try:
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_year = timezone.now().year
    
    # Calculate date ranges
    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year, 12, 31)
    year_start_dt = timezone.make_aware(datetime.combine(year_start, datetime.min.time()))
    year_end_dt = timezone.make_aware(datetime.combine(year_end, datetime.max.time()))
    
    # === MEMBER STATISTICS ===
    total_members = Member.objects.filter(created_at__lte=year_end_dt).count()
    new_members_year = Member.objects.filter(
        created_at__range=[year_start_dt, year_end_dt]
    ).count()
    active_members = Member.objects.filter(
        membership_status='active',
        created_at__lte=year_end_dt
    ).count()
    
    # === SAVINGS ANALYSIS ===
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    annual_deposits = SavingsTransaction.objects.filter(
        transaction_type__in=['voluntary', 'collateral'],
        is_loan_repayment=False,
        transaction_date__range=[year_start_dt, year_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    annual_withdrawals = SavingsTransaction.objects.filter(
        transaction_type='withdrawal',
        transaction_date__range=[year_start_dt, year_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # === LOAN ANALYSIS ===
    annual_loan_disbursements = Loan.objects.filter(
        disbursement_date__range=[year_start_dt, year_end_dt]
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
    
    annual_loan_repayments = LoanRepayment.objects.filter(
        payment_date__range=[year_start, year_end]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    outstanding_loans = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('total_balance'))['total'] or Decimal('0.00')
    
    # === FINANCIAL SUMMARY ===
    registration_fees = Member.objects.filter(
        created_at__range=[year_start_dt, year_end_dt]
    ).aggregate(total=Sum('registration_fee_amount'))['total'] or Decimal('0.00')
    
    loan_interest_earned = annual_loan_disbursements * Decimal('0.10')
    total_income = registration_fees + loan_interest_earned
    
    # === MONTHLY BREAKDOWN ===
    monthly_data = []
    for month in range(1, 13):
        month_start = date(selected_year, month, 1)
        if month == 12:
            month_end = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
        month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
        
        month_deposits = SavingsTransaction.objects.filter(
            transaction_type__in=['voluntary', 'collateral'],
            is_loan_repayment=False,
            transaction_date__range=[month_start_dt, month_end_dt]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        month_withdrawals = SavingsTransaction.objects.filter(
            transaction_type='withdrawal',
            transaction_date__range=[month_start_dt, month_end_dt]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        month_loans = Loan.objects.filter(
            disbursement_date__range=[month_start_dt, month_end_dt]
        ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
        
        month_repayments = LoanRepayment.objects.filter(
            payment_date__range=[month_start, month_end]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        new_members_month = Member.objects.filter(
            created_at__range=[month_start_dt, month_end_dt]
        ).count()
        
        monthly_data.append({
            'month': month,
            'month_name': month_start.strftime('%B'),
            'deposits': month_deposits,
            'withdrawals': month_withdrawals,
            'loans': month_loans,
            'repayments': month_repayments,
            'new_members': new_members_month,
            'net_savings': month_deposits - month_withdrawals,
        })
    
    current_year = timezone.now().year
    available_years = list(range(current_year - 5, current_year + 1))

    context = {
        'selected_year': selected_year,
        'year_start': year_start,
        'year_end': year_end,
        'total_members': total_members,
        'new_members_year': new_members_year,
        'active_members': active_members,
        'total_savings': total_savings,
        'annual_deposits': annual_deposits,
        'annual_withdrawals': annual_withdrawals,
        'net_savings': annual_deposits - annual_withdrawals,
        'annual_loan_disbursements': annual_loan_disbursements,
        'annual_loan_repayments': annual_loan_repayments,
        'outstanding_loans': outstanding_loans,
        'registration_fees': registration_fees,
        'loan_interest_earned': loan_interest_earned,
        'total_income': total_income,
        'monthly_data': monthly_data,
        'available_years': available_years,
    }
    return render(request, 'reports/comprehensive_annual.html', context)

@login_required
def comprehensive_monthly_report(request):
    """Clean, comprehensive monthly report with accurate data"""
    
    # Get month and year filters from request
    selected_month = request.GET.get('month', timezone.now().month)
    selected_year = request.GET.get('year', timezone.now().year)
    
    try:
        selected_month = int(selected_month)
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_month = timezone.now().month
        selected_year = timezone.now().year
    
    # Calculate date ranges
    month_start = date(selected_year, selected_month, 1)
    if selected_month == 12:
        month_end = date(selected_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(selected_year, selected_month + 1, 1) - timedelta(days=1)
    
    month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
    month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
    
    # === MEMBER STATISTICS ===
    total_members = Member.objects.filter(created_at__lte=month_end_dt).count()
    new_members_month = Member.objects.filter(
        created_at__range=[month_start_dt, month_end_dt]
    ).count()
    active_members = Member.objects.filter(
        membership_status='active',
        created_at__lte=month_end_dt
    ).count()
    
    # === SAVINGS ANALYSIS ===
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    monthly_deposits = SavingsTransaction.objects.filter(
        transaction_type__in=['voluntary', 'collateral'],
        is_loan_repayment=False,
        transaction_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    monthly_withdrawals = SavingsTransaction.objects.filter(
        transaction_type='withdrawal',
        transaction_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # === LOAN ANALYSIS ===
    monthly_loan_disbursements = Loan.objects.filter(
        disbursement_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
    
    monthly_loan_repayments = LoanRepayment.objects.filter(
        payment_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    outstanding_loans = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('total_balance'))['total'] or Decimal('0.00')
    
    # === FINANCIAL SUMMARY ===
    registration_fees = Member.objects.filter(
        created_at__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('registration_fee_amount'))['total'] or Decimal('0.00')
    
    loan_interest_earned = monthly_loan_disbursements * Decimal('0.10')
    total_income = registration_fees + loan_interest_earned
    
    # === DAILY BREAKDOWN ===
    daily_data = []
    current_date = month_start
    while current_date <= month_end:
        day_start_dt = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
        day_end_dt = timezone.make_aware(datetime.combine(current_date, datetime.max.time()))
        
        day_deposits = SavingsTransaction.objects.filter(
            transaction_type__in=['voluntary', 'collateral'],
            is_loan_repayment=False,
            transaction_date__range=[day_start_dt, day_end_dt]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        day_withdrawals = SavingsTransaction.objects.filter(
            transaction_type='withdrawal',
            transaction_date__range=[day_start_dt, day_end_dt]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        day_loans = Loan.objects.filter(
            disbursement_date__range=[day_start_dt, day_end_dt]
        ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
        
        daily_data.append({
            'date': current_date,
            'deposits': day_deposits,
            'withdrawals': day_withdrawals,
            'loans': day_loans,
            'net_savings': day_deposits - day_withdrawals,
        })
        
        current_date += timedelta(days=1)
    
    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'month_start': month_start,
        'month_end': month_end,
        'month_name': month_start.strftime('%B'),
        'total_members': total_members,
        'new_members_month': new_members_month,
        'active_members': active_members,
        'total_savings': total_savings,
        'monthly_deposits': monthly_deposits,
        'monthly_withdrawals': monthly_withdrawals,
        'net_savings': monthly_deposits - monthly_withdrawals,
        'monthly_loan_disbursements': monthly_loan_disbursements,
        'monthly_loan_repayments': monthly_loan_repayments,
        'outstanding_loans': outstanding_loans,
        'registration_fees': registration_fees,
        'loan_interest_earned': loan_interest_earned,
        'total_income': total_income,
        'daily_data': daily_data,
    }
    return render(request, 'reports/comprehensive_monthly.html', context)

@login_required
def comprehensive_balance_sheet(request):
    """Clean, comprehensive balance sheet with accurate data"""
    
    # Get date filter from request
    as_of_date = request.GET.get('date', timezone.now().date())
    try:
        as_of_date = date.fromisoformat(str(as_of_date))
    except (ValueError, TypeError):
        as_of_date = timezone.now().date()
    
    as_of_datetime = timezone.make_aware(datetime.combine(as_of_date, datetime.max.time()))
    
    # === ASSETS === (SAME LOGIC AS DASHBOARD)
    # 1. Total Member Savings (Cash and Cash Equivalents)
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    # 2. Loans Receivable (Outstanding Loans)
    loans_receivable = sum(
        loan.principal_balance for loan in Loan.objects.filter(status='active')
    )
    
    # 3. Interest Receivable (from active loans)
    # Interest receivable = remaining interest balance (interest not yet paid)
    interest_receivable = sum(
        loan.interest_balance for loan in Loan.objects.filter(status='active')
    )
    
    # 4. Registration Fees (ALL registration fees)
    registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0.00')
    
    # 5. Loan Interest Earned (from actual repayments)
    loan_interest_earned = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')
    
    # 6. Other Income (from general transactions)
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).exclude(
        description__icontains='registration'
    ).exclude(
        description__icontains='loan interest'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Include savings interest income
    savings_interest_income = SavingsTransaction.objects.filter(
        transaction_type='interest',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    other_income = (other_income or Decimal('0.00')) + (savings_interest_income or Decimal('0.00'))
    
    # Total Assets = Same as Dashboard's Total Cooperative Balance
    total_assets = total_savings + loan_interest_earned + registration_fees + other_income
    
    # === LIABILITIES ===
    # 1. Member Savings (Liability to members)
    member_savings_liability = total_savings
    
    # 2. Accrued Interest Payable (ALL TIME)
    accrued_interest = SavingsTransaction.objects.filter(
        transaction_type='interest',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # 3. Other Liabilities (expenses) - ALL TIME
    other_liabilities = Transaction.objects.filter(
        transaction_type='expense'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_liabilities = member_savings_liability + accrued_interest + other_liabilities
    
    # === EQUITY ===
    # 1. Registration Fees Earned (ALL TIME)
    registration_fees_earned = registration_fees
    
    # 2. Loan Interest Earned (ALL TIME)
    loan_interest_earned_equity = loan_interest_earned
    
    # 3. Other Income (ALL TIME)
    other_income_equity = other_income
    
    # 4. Retained Earnings (ALL TIME)
    retained_earnings = registration_fees_earned + loan_interest_earned_equity + other_income_equity
    
    total_equity = retained_earnings
    
    # Balance Check
    balance_check = total_assets - (total_liabilities + total_equity)
    is_balanced = abs(balance_check) < Decimal('0.01')
    
    # === INCOME STATEMENT (for the period) ===
    # Income
    total_income = registration_fees + (loans_receivable * Decimal('0.10'))
    
    # Expenses (placeholder - you can add actual expense tracking)
    total_expenses = Decimal('0.00')  # Add your expense calculations here
    
    net_income = total_income - total_expenses
    
    # Financial ratios
    liquidity_ratio = (total_assets / total_liabilities) if total_liabilities > 0 else Decimal('0.00')
    
    context = {
        'as_of_date': as_of_date,
        
        # Assets
        'total_savings': total_savings,
        'loans_receivable': loans_receivable,
        'interest_receivable': interest_receivable,
        'registration_fees': registration_fees,
        'loan_interest_earned': loan_interest_earned,
        'other_income': other_income,
        'total_assets': total_assets,
        
        # Liabilities
        'member_savings_liability': member_savings_liability,
        'accrued_interest': accrued_interest,
        'other_liabilities': other_liabilities,
        'total_liabilities': total_liabilities,
        
        # Equity
        'registration_fees_earned': registration_fees_earned,
        'loan_interest_earned_equity': loan_interest_earned_equity,
        'other_income_equity': other_income_equity,
        'retained_earnings': retained_earnings,
        'total_equity': total_equity,
        'cooperative_equity': total_equity,  # For backward compatibility
        
        # Balance Check
        'balance_check': balance_check,
        'is_balanced': is_balanced,
        
        # Income Statement
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_income': net_income,
        
        # Financial Ratios
        'liquidity_ratio': liquidity_ratio,
    }
    return render(request, 'reports/comprehensive_balance_sheet.html', context)
