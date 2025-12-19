from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Transaction, TransactionEntry, Account, AccountCategory, CashFlow
from .forms import TransactionForm, QuickTransactionForm, TransactionSearchForm
from savings.models import SavingsTransaction, SavingsAccount
from members.models import Member
from loans.models import Loan, LoanRepayment
from decimal import Decimal
import json
from datetime import datetime
from calendar import monthrange

def calculate_cooperative_balance():
    """
    Helper function to calculate the current cooperative balance.
    This matches the calculation used in dashboard and transaction_list views.
    Returns the current cooperative balance as Decimal.
    """
    # 1. Total member savings
    total_member_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')

    # 2. Loan interest earned (ONLY from actual repayments)
    loan_interest_earned = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')

    # 3. Registration fees (exclude admin/staff)
    registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0.00')

    # 4. Other income (exclude registration and explicit loan interest)
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).exclude(description__icontains='registration').exclude(
        description__icontains='loan interest'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 5. Savings interest income
    savings_interest_income = SavingsTransaction.objects.filter(
        transaction_type='interest', status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    other_income = (other_income or Decimal('0.00')) + (savings_interest_income or Decimal('0.00'))

    # 6. Calculate total expenses from transactions
    total_expenses = Transaction.objects.filter(
        transaction_type='expense',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Total cooperative balance (expenses reduce the balance)
    cooperative_balance = (
        total_member_savings + 
        loan_interest_earned + 
        registration_fees + 
        other_income - 
        total_expenses
    )
    
    return cooperative_balance

@login_required
def transaction_list(request):
    """List all transactions including savings transactions"""
    quick_search = (request.GET.get('quick_search') or '').strip()
    quick_type = request.GET.get('quick_type') or ''

    form = TransactionSearchForm(request.GET or None)
    
    # Get regular transactions
    regular_transactions = Transaction.objects.all().order_by('-transaction_date')
    
    # Get savings transactions
    savings_transactions = SavingsTransaction.objects.all().order_by('-transaction_date')

    # Apply quick filters first
    if quick_search:
        regular_transactions = regular_transactions.filter(
            Q(member__user__first_name__icontains=quick_search) |
            Q(member__user__last_name__icontains=quick_search) |
            Q(description__icontains=quick_search)
        )
        savings_transactions = savings_transactions.filter(
            Q(savings_account__member__user__first_name__icontains=quick_search) |
            Q(savings_account__member__user__last_name__icontains=quick_search) |
            Q(description__icontains=quick_search)
        )

    if quick_type == 'income':
        regular_transactions = regular_transactions.filter(transaction_type='income')
        savings_transactions = savings_transactions.filter(
            transaction_type__in=['compulsory', 'voluntary', 'interest']
        )
    elif quick_type == 'expense':
        regular_transactions = regular_transactions.filter(transaction_type='expense')
        savings_transactions = savings_transactions.filter(transaction_type='withdrawal')
    elif quick_type == 'savings_deposit':
        savings_transactions = savings_transactions.filter(
            transaction_type__in=['compulsory', 'voluntary', 'interest']
        )
        regular_transactions = regular_transactions.none()
    elif quick_type == 'savings_withdrawal':
        savings_transactions = savings_transactions.filter(transaction_type='withdrawal')
        regular_transactions = regular_transactions.none()
    
    # Apply filters to regular transactions
    if form.is_valid():
        search = form.cleaned_data.get('search')
        transaction_type = form.cleaned_data.get('transaction_type')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        account = form.cleaned_data.get('account')
        category = form.cleaned_data.get('category')
        amount_min = form.cleaned_data.get('amount_min')
        amount_max = form.cleaned_data.get('amount_max')
        
        if search:
            regular_transactions = regular_transactions.filter(
                Q(transaction_id__icontains=search) |
                Q(description__icontains=search)
            )
            savings_transactions = savings_transactions.filter(
                Q(savings_account__member__user__first_name__icontains=search) |
                Q(savings_account__member__user__last_name__icontains=search) |
                Q(description__icontains=search)
            )
        if transaction_type:
            regular_transactions = regular_transactions.filter(transaction_type=transaction_type)
            # Map transaction types for savings transactions
            if transaction_type == 'income':
                savings_transactions = savings_transactions.filter(transaction_type__in=['compulsory', 'voluntary', 'interest'])
            elif transaction_type == 'expense':
                savings_transactions = savings_transactions.filter(transaction_type='withdrawal')
        if start_date:
            regular_transactions = regular_transactions.filter(transaction_date__gte=start_date)
            savings_transactions = savings_transactions.filter(transaction_date__gte=start_date)
        if end_date:
            regular_transactions = regular_transactions.filter(transaction_date__lte=end_date)
            savings_transactions = savings_transactions.filter(transaction_date__lte=end_date)
        if account:
            regular_transactions = regular_transactions.filter(entries__account=account)
        if category:
            regular_transactions = regular_transactions.filter(entries__account__category=category)
        if amount_min:
            regular_transactions = regular_transactions.filter(amount__gte=amount_min)
            savings_transactions = savings_transactions.filter(amount__gte=amount_min)
        if amount_max:
            regular_transactions = regular_transactions.filter(amount__lte=amount_max)
            savings_transactions = savings_transactions.filter(amount__lte=amount_max)

        regular_transactions = regular_transactions.distinct()
    
    # Combine and sort all transactions
    all_transactions = list(regular_transactions) + list(savings_transactions)
    all_transactions.sort(key=lambda x: x.transaction_date, reverse=True)
    
    # Calculate summary statistics
    total_income = regular_transactions.filter(transaction_type='income').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_expense = regular_transactions.filter(transaction_type='expense').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Note: Transfer transactions have been removed from the system
    total_transfer = Decimal('0.00')
    
    # Calculate savings transaction totals
    total_savings_deposits = savings_transactions.filter(
        transaction_type__in=['compulsory', 'voluntary', 'interest']
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_savings_withdrawals = savings_transactions.filter(
        transaction_type='withdrawal'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # New financial metrics for display
    # 1. Total savings (actual member savings balance)
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    # 2. Total loan repayment interest
    total_loan_repayment_interest = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')
    
    # 3. Total registration fees
    total_registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0.00')
    
    # 4. Total income (from general transactions)
    total_income_amount = regular_transactions.filter(transaction_type='income').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # 5. Total withdrawals (from savings)
    total_withdrawals_amount = total_savings_withdrawals
    
    # Calculate net amounts
    net_regular = total_income - total_expense
    net_savings = total_savings_deposits - total_savings_withdrawals
    
    # Unified cooperative balance calculation (same logic as dashboard)
    # 1. Total member savings
    total_member_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')

    # 2. Total disbursed loans (active)
    total_disbursed_loans = Loan.objects.filter(status='active').aggregate(
        total=Sum('approved_amount')
    )['total'] or Decimal('0.00')

    # 3. Loan interest earned (ONLY from actual repayments, not from disbursement)
    # Interest is only added to cooperative balance when members make actual payments
    loan_interest_earned = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')

    # 4. Registration fees (exclude admin/staff)
    registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0.00')

    # 5. Other income (exclude registration and explicit loan interest)
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).exclude(description__icontains='registration').exclude(
        description__icontains='loan interest'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # 6. Savings interest income
    savings_interest_income = SavingsTransaction.objects.filter(
        transaction_type='interest', status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    other_income = (other_income or Decimal('0.00')) + (savings_interest_income or Decimal('0.00'))

    # Calculate total expenses from transactions
    total_expenses = Transaction.objects.filter(
        transaction_type='expense',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Total cooperative balance (cash position proxy)
    # Expenses reduce the cooperative balance
    cooperative_balance = (
        total_member_savings + loan_interest_earned + registration_fees + other_income - total_expenses
    )
    
    # Net position should represent the overall financial position
    # This is the cooperative balance minus outstanding loans (available cash)
    total_outstanding_loans = sum(
        loan.principal_balance for loan in Loan.objects.filter(status='active')
    )
    net_position = cooperative_balance - total_outstanding_loans
    
    # Calculate total available balance for the new financial metrics
    total_available_balance = cooperative_balance - total_outstanding_loans
    
    # Paginate the combined results
    paginator = Paginator(all_transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'transactions/list.html', {
        'search_form': form,
        'page_obj': page_obj,
        'transactions': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'summary': {
            'total_income': total_income,
            'total_expense': total_expense,
            'total_transfer': total_transfer,
            'total_savings_deposits': total_savings_deposits,
            'total_savings_withdrawals': total_savings_withdrawals,
            'net_regular': net_regular,
            'net_savings': net_savings,
            'total_net': net_position,  # Use net_position instead of total_net
            'cooperative_balance': cooperative_balance,
            'total_transactions': len(all_transactions),
            # New financial metrics
            'total_savings': total_savings,
            'total_loan_repayment_interest': total_loan_repayment_interest,
            'total_registration_fees': total_registration_fees,
            'total_income_amount': total_income_amount,
            'total_withdrawals_amount': total_withdrawals_amount,
            'total_available_balance': total_available_balance,
        },
        'quick_search': quick_search,
        'quick_type': quick_type,
    })

@login_required
def add_transaction(request):
    """Create new transaction"""
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                transaction = form.save(commit=False)
                
                # Validate expense transactions: check if cooperative has sufficient balance
                if transaction.transaction_type == 'expense':
                    current_balance = calculate_cooperative_balance()
                    expense_amount = transaction.amount
                    
                    if expense_amount > current_balance:
                        messages.error(
                            request, 
                            f'Insufficient cooperative balance. Available: ₦{current_balance:,.2f}, Required: ₦{expense_amount:,.2f}'
                        )
                        return render(request, 'transactions/add.html', {'form': form})
                
                transaction.created_by = request.user
                transaction.save()
                messages.success(request, f'Transaction {transaction.transaction_id} created successfully!')
                return redirect('transactions:detail', pk=transaction.pk)
            except Exception as e:
                messages.error(request, f'Error creating transaction: {str(e)}')
                return render(request, 'transactions/add.html', {'form': form})
    else:
        form = TransactionForm()
    
    return render(request, 'transactions/add.html', {'form': form})

@login_required
def transaction_detail(request, pk):
    """View transaction details"""
    transaction = get_object_or_404(Transaction, pk=pk)
    entries = TransactionEntry.objects.filter(transaction=transaction)
    
    return render(request, 'transactions/detail.html', {
        'transaction': transaction,
        'entries': entries
    })

@login_required
def edit_transaction(request, pk):
    """Edit transaction"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            try:
                # Get the new transaction data before saving
                new_transaction = form.save(commit=False)
                
                # Validate expense transactions: check if cooperative has sufficient balance
                if new_transaction.transaction_type == 'expense':
                    # Calculate current balance excluding this transaction (if it was already an expense)
                    current_balance = calculate_cooperative_balance()
                    
                    # If editing an existing expense transaction, add back its old amount to balance
                    if transaction.transaction_type == 'expense' and transaction.status == 'completed':
                        current_balance += transaction.amount
                    
                    expense_amount = new_transaction.amount
                    
                    if expense_amount > current_balance:
                        messages.error(
                            request, 
                            f'Insufficient cooperative balance. Available: ₦{current_balance:,.2f}, Required: ₦{expense_amount:,.2f}'
                        )
                        return render(request, 'transactions/edit.html', {
                            'form': form,
                            'transaction': transaction
                        })
                
                form.save()
                messages.success(request, 'Transaction updated successfully!')
                return redirect('transactions:detail', pk=pk)
            except Exception as e:
                messages.error(request, f'Error updating transaction: {str(e)}')
    else:
        form = TransactionForm(instance=transaction)
    
    return render(request, 'transactions/edit.html', {
        'form': form,
        'transaction': transaction
    })

@login_required
def delete_transaction(request, pk):
    """Delete transaction"""
    transaction = get_object_or_404(Transaction, pk=pk)
    
    if request.method == 'POST':
        try:
            transaction.delete()
            messages.success(request, 'Transaction deleted successfully!')
            return redirect('transactions:list')
        except Exception as e:
            messages.error(request, f'Error deleting transaction: {str(e)}')
            return redirect('transactions:detail', pk=pk)
    
    return render(request, 'transactions/delete.html', {
        'transaction': transaction
    })

@login_required
def quick_transaction(request):
    """Process quick transaction"""
    if request.method == 'POST':
        form = QuickTransactionForm(request.POST)
        if form.is_valid():
            try:
                transaction_type = form.cleaned_data.get('transaction_type')
                amount = form.cleaned_data.get('amount')
                description = form.cleaned_data.get('description')
                transaction_date = form.cleaned_data.get('transaction_date')
                
                # Validate expense transactions: check if cooperative has sufficient balance
                if transaction_type == 'expense':
                    current_balance = calculate_cooperative_balance()
                    
                    if amount > current_balance:
                        messages.error(
                            request, 
                            f'Insufficient cooperative balance. Available: ₦{current_balance:,.2f}, Required: ₦{amount:,.2f}'
                        )
                        return render(request, 'transactions/quick.html', {'form': form})
                
                # Create Transaction object manually since QuickTransactionForm is a regular Form
                # Convert date to datetime for transaction_date field
                from datetime import date
                if isinstance(transaction_date, date) and not isinstance(transaction_date, datetime):
                    transaction_datetime = timezone.make_aware(
                        datetime.combine(transaction_date, datetime.min.time())
                    )
                else:
                    transaction_datetime = timezone.now()
                
                transaction = Transaction.objects.create(
                    transaction_type=transaction_type,
                    description=description,
                    amount=amount,
                    transaction_date=transaction_datetime,
                    created_by=request.user,
                    status='completed'
                )
                
                messages.success(request, f'Transaction {transaction.transaction_id} processed successfully!')
                return redirect('transactions:list')
            except Exception as e:
                messages.error(request, f'Error processing transaction: {str(e)}')
                return render(request, 'transactions/quick.html', {'form': form})
    else:
        form = QuickTransactionForm()
    
    return render(request, 'transactions/quick.html', {'form': form})

@login_required
def accounts_list(request):
    """List all accounts"""
    accounts = Account.objects.all().order_by('code')
    return render(request, 'transactions/accounts.html', {'accounts': accounts})

@login_required
def account_detail(request, pk):
    """View account details"""
    account = get_object_or_404(Account, pk=pk)
    entries = TransactionEntry.objects.filter(account=account).order_by('-transaction__transaction_date')
    
    return render(request, 'transactions/account_detail.html', {
        'account': account,
        'entries': entries
    })

@login_required
def cash_flow(request):
    """Cash flow report"""
    from .forms import CashFlowForm
    
    cash_flows = CashFlow.objects.all().order_by('-date')
    form = CashFlowForm()
    
    if request.method == 'POST':
        form = CashFlowForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cash flow record added successfully!')
            return redirect('transactions:cash_flow')
    
    return render(request, 'transactions/cash_flow.html', {
        'cash_flows': cash_flows,
        'form': form
    })

@login_required
def transaction_dashboard(request):
    """Transaction dashboard"""
    # Summary statistics
    total_transactions = Transaction.objects.count()
    total_amount = Transaction.objects.aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent transactions
    recent_transactions = Transaction.objects.order_by('-transaction_date')[:10]
    
    # Transaction types
    transaction_types = list(Transaction.objects.values('transaction_type').annotate(count=Count('id')))
    
    context = {
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'recent_transactions': recent_transactions,
        'transaction_types': json.dumps(transaction_types),
    }
    return render(request, 'transactions/dashboard.html', context)

# Additional views for URL compatibility
@login_required
def dashboard(request):
    """Transaction dashboard (alias for transaction_dashboard)"""
    return transaction_dashboard(request)

@login_required
def journal_entry(request):
    """Journal entry view"""
    return render(request, 'transactions/journal.html')

@login_required
def create_account(request):
    """Create account view"""
    return render(request, 'transactions/create_account.html')

@login_required
def edit_account(request, pk):
    """Edit account view"""
    account = get_object_or_404(Account, pk=pk)
    return render(request, 'transactions/edit_account.html', {'account': account})

@login_required
def account_ledger(request, pk):
    """Account ledger view"""
    account = get_object_or_404(Account, pk=pk)
    entries = TransactionEntry.objects.filter(account=account).order_by('-transaction__transaction_date')
    return render(request, 'transactions/account_ledger.html', {
        'account': account,
        'entries': entries
    })

@login_required
def cash_flow_view(request):
    """Cash flow view (alias for cash_flow)"""
    return cash_flow(request)

@login_required
def create_cash_flow(request):
    """Create cash flow view"""
    return render(request, 'transactions/create_cash_flow.html')

@login_required
def financial_statements(request):
    """Financial statements view"""
    return render(request, 'transactions/statements.html')

@login_required
def bank_reconciliation(request):
    """Bank reconciliation view"""
    return render(request, 'transactions/reconciliation.html')

@login_required
def bulk_upload(request):
    """Bulk upload view"""
    return render(request, 'transactions/bulk_upload.html')

@login_required
def undo_transaction(request, pk):
    """Undo a recent transaction (for duplicate submissions)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        transaction = get_object_or_404(Transaction, pk=pk)
        
        # Check if transaction is recent (within last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        if transaction.transaction_date < timezone.now() - timedelta(hours=24):
            return JsonResponse({'success': False, 'error': 'Transaction is too old to undo'})
        
        # Check if transaction is not completed
        if transaction.status == 'completed':
            return JsonResponse({'success': False, 'error': 'Cannot undo completed transaction'})
        
        # Delete the transaction
        transaction.delete()
        
        return JsonResponse({'success': True, 'message': 'Transaction undone successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def balance_sheet(request):
    """Generate comprehensive balance sheet with monthly/yearly filtering"""
    # Get filter parameters
    year = request.GET.get('year', datetime.now().year)
    month = request.GET.get('month', None)
    report_type = request.GET.get('type', 'monthly')  # monthly or yearly
    
    try:
        year = int(year)
        if month:
            month = int(month)
    except (ValueError, TypeError):
        year = datetime.now().year
        month = None
    
    # Set date range based on report type
    if report_type == 'yearly':
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        period_label = f"Year {year}"
    else:  # monthly
        if month:
            start_date = datetime(year, month, 1)
            last_day = monthrange(year, month)[1]
            end_date = datetime(year, month, last_day, 23, 59, 59)
            period_label = f"{datetime(year, month, 1).strftime('%B')} {year}"
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            period_label = f"Year {year}"
    
    # Convert to timezone aware
    start_date = timezone.make_aware(start_date)
    end_date = timezone.make_aware(end_date)
    
    # Calculate all financial metrics
    context = calculate_balance_sheet_data(start_date, end_date, period_label)
    
    # Add filter options for template
    context.update({
        'current_year': year,
        'current_month': month,
        'report_type': report_type,
        'available_years': range(2020, datetime.now().year + 2),
        'months': [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
    })
    
    return render(request, 'transactions/balance_sheet.html', context)

def calculate_balance_sheet_data(start_date, end_date, period_label):
    """Calculate comprehensive balance sheet data"""
    
    # ASSETS - Point-in-time snapshots (as of now)
    # 1. Total Member Savings (Cash and Cash Equivalents)
    total_member_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    # 2. Loans Receivable (Outstanding Loans)
    outstanding_loans = sum(
        loan.principal_balance for loan in Loan.objects.filter(status='active')
    )
    
    # 3. Interest Receivable (from active loans)
    # Interest receivable = total interest - interest already paid
    # We can calculate this as: total_interest - (total_interest - interest_balance) = interest_balance
    # Or simply use interest_balance which represents the remaining interest
    interest_receivable = sum(
        loan.interest_balance for loan in Loan.objects.filter(status='active')
    )
    
    # 4. Registration Fees collected within period
    registration_fees = Member.regular_members().filter(
        date_joined__range=[start_date.date(), end_date.date()]
    ).aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0.00')
    
    # 5. Loan Interest Earned (from actual repayments) within period
    loan_interest_earned = LoanRepayment.objects.filter(
        payment_date__range=[start_date, end_date]
    ).aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0.00')
    
    # 6. Other Income (from general transactions) within period
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).filter(
        transaction_date__range=[start_date, end_date]
    ).exclude(
        description__icontains='registration'
    ).exclude(
        description__icontains='loan interest'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Include savings interest income within period
    savings_interest_income = SavingsTransaction.objects.filter(
        transaction_type='interest',
        status='completed',
        transaction_date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    other_income = (other_income or Decimal('0.00')) + (savings_interest_income or Decimal('0.00'))
    
    # Calculate total expenses from transactions (ALL TIME for balance sheet)
    total_expenses_all_time = Transaction.objects.filter(
        transaction_type='expense',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Total Assets = Same as Dashboard's Total Cooperative Balance
    # Expenses reduce the total assets/cooperative balance
    total_assets = total_member_savings + loan_interest_earned + registration_fees + other_income - total_expenses_all_time
    
    # LIABILITIES
    # 1. Member Savings (Liability to members)
    member_savings_liability = total_member_savings
    
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
    
    # EQUITY - SAME LOGIC AS DASHBOARD
    # 1. Registration Fees Earned (ALL TIME - same as dashboard)
    registration_fees_earned = registration_fees  # Use the same value as assets
    
    # 2. Loan Interest Earned (ALL TIME - same as dashboard)  
    loan_interest_earned_equity = loan_interest_earned  # Use the same value as assets
    
    # 3. Other Income (ALL TIME - same as dashboard)
    other_income_equity = other_income  # Use the same value as assets
    
    # 4. Net Income for the period (Income - Expenses within date range)
    period_income = Transaction.objects.filter(
        transaction_type='income',
        created_at__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    period_expenses = Transaction.objects.filter(
        transaction_type='expense',
        created_at__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    net_income = period_income - period_expenses
    
    # 5. Retained Earnings (ALL TIME)
    retained_earnings = registration_fees_earned + loan_interest_earned_equity + other_income_equity
    
    total_equity = retained_earnings
    
    # INCOME STATEMENT
    # Revenue
    total_revenue = registration_fees_earned + loan_interest_earned_equity + other_income_equity
    
    # Expenses
    total_expenses_amount = period_expenses + accrued_interest
    
    # Net Profit
    net_profit = total_revenue - total_expenses_amount
    
    # CASH FLOW
    # Available Balance (Cash available for new loans) - SAME AS DASHBOARD
    total_cooperative_balance = total_assets  # Same as total assets
    available_balance = total_cooperative_balance - outstanding_loans
    
    # Key Metrics
    total_members = Member.regular_members().count()
    active_loans = Loan.objects.filter(status='active').count()
    total_transactions = Transaction.objects.filter(
        created_at__range=[start_date, end_date]
    ).count()
    
    # Balance Check (Assets should equal Liabilities + Equity)
    balance_check = total_assets - (total_liabilities + total_equity)
    is_balanced = abs(balance_check) < Decimal('0.01')  # Allow for small rounding differences
    
    return {
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        
        # Assets
        'total_member_savings': total_member_savings,
        'outstanding_loans': outstanding_loans,
        'interest_receivable': interest_receivable,
        'registration_fees_receivable': Decimal('0.00'),  # Not used in new calculation
        'other_assets': other_income,  # Use other_income as other_assets
        'total_assets': total_assets,
        
        # Liabilities
        'member_savings_liability': member_savings_liability,
        'accrued_interest': accrued_interest,
        'other_liabilities': other_liabilities,
        'total_liabilities': total_liabilities,
        
        # Equity
        'registration_fees_earned': registration_fees_earned,
        'loan_interest_earned': loan_interest_earned_equity,
        'other_income': other_income_equity,
        'net_income': net_income,
        'retained_earnings': retained_earnings,
        'total_equity': total_equity,
        
        # Income Statement
        'total_revenue': total_revenue,
        'total_expenses_amount': total_expenses_amount,
        'net_profit': net_profit,
        
        # Cash Flow
        'total_cooperative_balance': total_cooperative_balance,
        'available_balance': available_balance,
        
        # Key Metrics
        'total_members': total_members,
        'active_loans': active_loans,
        'total_transactions': total_transactions,
        
        # Balance Check
        'balance_check': balance_check,
        'is_balanced': is_balanced,
    }
