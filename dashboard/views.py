from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from members.models import Member
from savings.models import SavingsAccount, SavingsTransaction
from loans.models import Loan, LoanRepayment
from transactions.models import Transaction, CashFlow

@login_required
def dashboard_redirect(request):
    """Redirect users to the appropriate dashboard based on their role"""
    # Check if user is admin/staff first
    if request.user.is_superuser or request.user.is_staff:
        return redirect('dashboard:home')
    
    # Check if user is a regular member
    try:
        member = Member.objects.get(user=request.user)
        return redirect('dashboard:member_dashboard')
    except Member.DoesNotExist:
        # If user is not a member, redirect to admin dashboard
        return redirect('dashboard:home')

@login_required
def dashboard_home(request):
    """Admin/Staff Dashboard - Main dashboard with key statistics and recent activities"""
    
    # Get current date
    today = timezone.now().date()
    current_month = today.replace(day=1)
    current_year = today.replace(month=1, day=1)
    
    # Member Statistics (exclude admin/staff users)
    total_members = Member.regular_members().filter(
        membership_status='active'
    ).count()
    
    new_members_this_month = Member.regular_members().filter(
        date_joined__gte=current_month,
        membership_status='active'
    ).count()
    
    # Savings Statistics
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or 0
    
    savings_this_month = SavingsTransaction.objects.filter(
        transaction_date__gte=current_month,
        transaction_type__in=['compulsory', 'voluntary'],
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Enhanced Loan Statistics
    active_loans = Loan.objects.filter(status='active').count()
    total_loans_disbursed = Loan.objects.filter(
        status__in=['active', 'completed']
    ).aggregate(total=Sum('approved_amount'))['total'] or 0
    
    pending_loan_applications = Loan.objects.filter(status='pending').count()
    approved_loans = Loan.objects.filter(status='approved').count()
    overdue_loans = Loan.objects.filter(
        status='active',
        expected_completion_date__lt=today
    ).count()
    
    # New loan analytics
    total_loan_interest_earned = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or 0
    
    total_loan_principal_repaid = LoanRepayment.objects.aggregate(
        total=Sum('principal_amount')
    )['total'] or 0
    
    # Loan phase analytics
    interest_phase_loans = 0
    principal_phase_loans = 0
    completed_loans = Loan.objects.filter(status='completed').count()
    
    for loan in Loan.objects.filter(status='active'):
        loan_progress = loan.member.get_loan_progress()
        if loan_progress['is_interest_phase']:
            interest_phase_loans += 1
        elif loan_progress['is_principal_phase']:
            principal_phase_loans += 1
    
    # Cash Flow Statistics
    monthly_inflow = CashFlow.objects.filter(
        date__gte=current_month,
        flow_type='inflow'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_outflow = CashFlow.objects.filter(
        date__gte=current_month,
        flow_type='outflow'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    net_cash_flow = monthly_inflow - monthly_outflow
    
    # ACCURATE FINANCIAL CALCULATIONS
    
    # 1. Total Member Savings (from savings accounts)
    total_member_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0')
    
    # 2. Total Outstanding Loans (money owed to cooperative)
    total_outstanding_loans = sum(
        loan.principal_balance for loan in Loan.objects.filter(status='active')
    )
    
    # 3. Total Disbursed Loans (money given out)
    total_disbursed_loans = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    # 4. Loan Interest Earned (ONLY from actual repayments, not from disbursement)
    # Interest is only added to cooperative balance when members make actual payments
    # The 10% interest is calculated and stored in the loan, but not added to balance until paid
    
    # Interest from actual repayments (this is the interest portion of repayments)
    repaid_interest = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0')
    
    # Total interest earned = ONLY from actual repayments (not from disbursement)
    loan_interest_earned = repaid_interest
    
    # 5. Registration Fees (from member registration, exclude admin/staff)
    registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0')
    
    # 6. Other Income (all income transactions except registration fees)
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).exclude(
        description__icontains='registration'
    ).exclude(
        description__icontains='loan interest'  # Exclude loan interest as it's calculated separately
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # Also include any income from savings transactions (like interest payments)
    savings_income = SavingsTransaction.objects.filter(
        transaction_type='interest',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Total other income = general transactions + savings interest
    other_income = other_income + savings_income
    
    # Calculate total expenses from transactions
    total_expenses = Transaction.objects.filter(
        transaction_type='expense',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # TOTAL COOPERATIVE BALANCE = All money the cooperative has (excluding outstanding loans)
    # Outstanding loans are receivables, not available cash
    # Expenses reduce the cooperative balance
    total_cooperative_balance = (
        total_member_savings + 
        loan_interest_earned + 
        registration_fees + 
        other_income -
        total_expenses  # Subtract expenses from balance
    )
    
    # AVAILABLE CASH = Total cooperative balance - outstanding loans (not disbursed loans)
    # Outstanding loans decrease as members make repayments, so available balance increases
    # This represents the actual cash the cooperative has available for new loans
    available_balance = total_cooperative_balance - total_outstanding_loans
    
    # Breakdown for details
    amount_breakdown = {
        'member_savings': total_member_savings,
        'outstanding_loans': total_outstanding_loans,
        'disbursed_loans': total_disbursed_loans,
        'available_balance': available_balance,
        'total_expenses': total_expenses,  # Total expenses from transactions
        'loan_interest_earned': loan_interest_earned,
        'repaid_interest': repaid_interest,  # Interest from actual repayments
        'registration_fees': registration_fees,
        'other_income': other_income,
        'savings_income': savings_income,  # Interest from savings
        'total_cooperative_balance': total_cooperative_balance
    }
    
    # Recent Activities
    recent_transactions = Transaction.objects.filter(
        status='completed'
    ).order_by('-transaction_date')[:5]
    
    # Recent Savings Transactions (deposits and withdrawals)
    recent_savings_transactions = SavingsTransaction.objects.filter(
        status='completed'
    ).order_by('-transaction_date')[:5]
    
    recent_loan_applications = Loan.objects.filter(
        status='pending'
    ).order_by('-application_date')[:5]
    
    recent_repayments = LoanRepayment.objects.filter(
        status='completed'
    ).order_by('-payment_date')[:5]
    
    # Monthly Savings Trend (last 6 months)
    monthly_savings_data = []
    for i in range(6):
        month_start = (current_month - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_savings = SavingsTransaction.objects.filter(
            transaction_date__gte=month_start,
            transaction_date__lte=month_end,
            transaction_type__in=['compulsory', 'voluntary'],
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_savings_data.append({
            'month': month_start.strftime('%b %Y'),
            'amount': float(month_savings)
        })
    
    monthly_savings_data.reverse()
    
    context = {
        'total_members': total_members,
        'new_members_this_month': new_members_this_month,
        'total_savings': total_savings,
        'savings_this_month': savings_this_month,
        'active_loans': active_loans,
        'total_loans_disbursed': total_loans_disbursed,
        'pending_loan_applications': pending_loan_applications,
        'approved_loans': approved_loans,
        'overdue_loans': overdue_loans,
        'total_loan_interest_earned': total_loan_interest_earned,
        'total_loan_principal_repaid': total_loan_principal_repaid,
        'interest_phase_loans': interest_phase_loans,
        'principal_phase_loans': principal_phase_loans,
        'completed_loans': completed_loans,
        'monthly_inflow': monthly_inflow,
        'monthly_outflow': monthly_outflow,
        'net_cash_flow': net_cash_flow,
        'recent_transactions': recent_transactions,
        'recent_savings_transactions': recent_savings_transactions,
        'recent_loan_applications': recent_loan_applications,
        'recent_repayments': recent_repayments,
        'monthly_savings_data': monthly_savings_data,
        'total_cooperative_balance': total_cooperative_balance,
        'available_balance': available_balance,
        'amount_breakdown': amount_breakdown,
    }
    
    return render(request, 'dashboard/home.html', context)

@login_required
def member_dashboard(request):
    """Member-specific dashboard showing personal loan progress and savings"""
    # First check if user is actually a member
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        # If user is not a member, redirect to admin dashboard
        return redirect('dashboard:home')
    
    # Get savings account
    try:
        savings_account = member.savings_account
    except SavingsAccount.DoesNotExist:
        savings_account = None
    
    # Get loan progress
    loan_progress = member.get_loan_progress()
    
    # Get recent savings transactions
    recent_savings = []
    if savings_account:
        recent_savings = SavingsTransaction.objects.filter(
            savings_account=savings_account
        ).order_by('-transaction_date')[:10]
    
    # Get recent loan repayments
    recent_repayments = []
    if loan_progress['has_active_loan']:
        from loans.models import Loan
        active_loan = Loan.objects.filter(
            member=member,
            status__in=['active', 'approved']
        ).first()
        if active_loan:
            recent_repayments = LoanRepayment.objects.filter(
                loan=active_loan
            ).order_by('-payment_date')[:10]
    
    # Get ALL recent transactions (including general transactions)
    from transactions.models import Transaction
    recent_transactions = Transaction.objects.filter(
        member=member
    ).order_by('-transaction_date')[:15]
    
    # Get all member's loans (active, completed, rejected)
    from loans.models import Loan
    all_loans = Loan.objects.filter(member=member).order_by('-application_date')
    
    # Get loan statistics
    total_loans_applied = all_loans.count()
    active_loans = all_loans.filter(status='active').count()
    completed_loans = all_loans.filter(status='completed').count()
    rejected_loans = all_loans.filter(status='rejected').count()
    
    # Calculate total amounts
    total_borrowed = all_loans.filter(status__in=['active', 'completed']).aggregate(
        total=Sum('approved_amount')
    )['total'] or 0
    
    total_repaid = LoanRepayment.objects.filter(
        loan__member=member,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Calculate monthly deposit impact on loan repayment
    monthly_deposit = member.monthly_savings
    max_loan_amount = member.maximum_loan_amount
    
    # Get member's transaction summary - only count actual deposits (collateral and voluntary)
    # Compulsory transactions are not considered deposits in this system
    total_deposits = SavingsTransaction.objects.filter(
        savings_account=savings_account,
        transaction_type__in=['voluntary', 'collateral'],
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_withdrawals = SavingsTransaction.objects.filter(
        savings_account=savings_account,
        transaction_type='withdrawal',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'member': member,
        'savings_account': savings_account,
        'loan_progress': loan_progress,
        'recent_savings': recent_savings,
        'recent_repayments': recent_repayments,
        'recent_transactions': recent_transactions,
        'all_loans': all_loans,
        'monthly_deposit': monthly_deposit,
        'max_loan_amount': max_loan_amount,
        'total_loans_applied': total_loans_applied,
        'active_loans': active_loans,
        'completed_loans': completed_loans,
        'rejected_loans': rejected_loans,
        'total_borrowed': total_borrowed,
        'total_repaid': total_repaid,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
    }
    
    return render(request, 'dashboard/member_dashboard.html', context)
