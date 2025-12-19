from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from decimal import Decimal
from .models import Transaction, TransactionEntry, Account, AccountCategory, CashFlow
from members.models import Member
from savings.models import SavingsAccount, SavingsTransaction
from loans.models import Loan, LoanRepayment
import json
from datetime import datetime, timedelta

@login_required
def process_member_payment(request):
    """Process member payments (savings, loan repayments, fees)"""
    if request.method == 'POST':
        try:
            with db_transaction.atomic():
                # Parse form data
                member_id = request.POST.get('member_id')
                payment_type = request.POST.get('payment_type')
                amount = Decimal(str(request.POST.get('amount', '0')))
                description = request.POST.get('description', '')
                reference_id = request.POST.get('reference_id', '')
                
                if amount <= 0:
                    messages.error(request, 'Payment amount must be greater than zero.')
                    return redirect('transactions:member_payment')
                
                member = get_object_or_404(Member, pk=member_id)
                
                # Create main transaction record
                transaction = Transaction.objects.create(
                    transaction_type='income' if payment_type in ['savings_deposit', 'registration_fee'] else 'transfer',
                    description=description or f'{payment_type.replace("_", " ").title()} from {member.user.get_full_name()}',
                    amount=amount,
                    member=member,
                    created_by=request.user,
                    status='completed',
                    transaction_date=timezone.now()
                )
                
                # Process specific payment type
                success_message = handle_payment_by_type(transaction, payment_type, reference_id, amount)
                
                messages.success(request, success_message)
                return redirect('transactions:detail', pk=transaction.pk)
                
        except Exception as e:
            messages.error(request, f'Error processing payment: {str(e)}')
    
    # GET request - show payment form
    context = {
        'members': Member.objects.filter(membership_status='active').order_by('user__first_name'),
        'payment_types': [
            ('savings_deposit', 'Savings Deposit'),
            ('loan_repayment', 'Loan Repayment'),
            ('registration_fee', 'Registration Fee'),
            ('service_fee', 'Service Fee'),
            ('share_capital', 'Share Capital Payment'),
        ],
    }
    return render(request, 'transactions/member_payment.html', context)

def handle_payment_by_type(transaction, payment_type, reference_id, amount):
    """Process payment based on type and update related records"""
    
    if payment_type == 'savings_deposit':
        if reference_id:
            savings_account = get_object_or_404(SavingsAccount, pk=reference_id)
        else:
            # Get member's primary savings account
            savings_account = SavingsAccount.objects.filter(
                member=transaction.member,
                is_active=True
            ).first()
            
            if not savings_account:
                raise Exception('No active savings account found for member')
        
        # Create savings transaction
        SavingsTransaction.objects.create(
            savings_account=savings_account,
            transaction_type='deposit',
            amount=amount,
            description=f'Deposit via transaction {transaction.transaction_id}',
            reference_number=transaction.transaction_id,
            processed_by=transaction.created_by
        )
        
        # Update savings balance
        savings_account.balance = F('balance') + amount
        savings_account.save()
        
        # Link to transaction
        transaction.savings_account = savings_account
        transaction.save()
        
        return f'Savings deposit of {amount} processed successfully for account {savings_account.account_number}'
    
    elif payment_type == 'loan_repayment':
        loan = get_object_or_404(Loan, pk=reference_id)
        
        if loan.status != 'active':
            raise Exception('Loan is not active')
        
        # Calculate interest and principal portions
        monthly_interest_rate = loan.loan_product.interest_rate / 12 / 100
        outstanding_balance = loan.total_balance
        
        # Calculate interest on outstanding balance
        interest_amount = outstanding_balance * monthly_interest_rate
        principal_amount = amount - interest_amount
        
        if principal_amount < 0:
            # Payment is less than interest - all goes to interest
            principal_amount = Decimal('0.00')
            interest_amount = amount
        
        # Create loan repayment record
        LoanRepayment.objects.create(
            loan=loan,
            payment_amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            payment_date=transaction.transaction_date.date(),
            reference_number=transaction.transaction_id,
            processed_by=transaction.created_by
        )
        
        # Update loan balance
        new_balance = outstanding_balance - principal_amount
        loan.total_balance = max(new_balance, Decimal('0.00'))
        
        # Check if loan is fully paid
        if loan.total_balance <= Decimal('0.01'):  # Account for rounding
            loan.total_balance = Decimal('0.00')
            loan.status = 'completed'
            loan.completion_date = timezone.now().date()
        
        loan.save()
        
        # Link to transaction
        transaction.loan = loan
        transaction.save()
        
        return f'Loan repayment of {amount} processed (Principal: {principal_amount}, Interest: {interest_amount})'
    
    elif payment_type == 'registration_fee':
        member = transaction.member
        
        if member.registration_fee_paid:
            raise Exception('Registration fee already paid')
        
        if amount < member.registration_fee_amount:
            raise Exception(f'Insufficient amount. Registration fee is {member.registration_fee_amount}')
        
        # Mark registration fee as paid
        member.registration_fee_paid = True
        member.membership_status = 'active'
        member.save()
        
        return f'Registration fee of {amount} processed for {member.user.get_full_name()}'
    
    elif payment_type in ['service_fee', 'share_capital']:
        # General fee payments - no specific account updates needed
        return f'{payment_type.replace("_", " ").title()} of {amount} processed for {transaction.member.user.get_full_name()}'
    
    else:
        raise Exception('Invalid payment type')

@login_required
def member_payment_ajax(request):
    """Handle AJAX member payment requests"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            member_id = data.get('member_id')
            payment_type = data.get('payment_type')
            amount = Decimal(str(data.get('amount', '0')))
            description = data.get('description', '')
            reference_id = data.get('reference_id', '')
            
            if amount <= 0:
                return JsonResponse({'success': False, 'error': 'Amount must be greater than zero'})
            
            member = get_object_or_404(Member, pk=member_id)
            
            with db_transaction.atomic():
                # Create transaction
                transaction = Transaction.objects.create(
                    transaction_type='income',
                    description=description or f'{payment_type.replace("_", " ").title()} from {member.user.get_full_name()}',
                    amount=amount,
                    member=member,
                    created_by=request.user,
                    status='completed'
                )
                
                # Process payment
                success_message = handle_payment_by_type(transaction, payment_type, reference_id, amount)
                
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'transaction_id': transaction.transaction_id,
                    'redirect_url': f'/transactions/{transaction.pk}/'
                })
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def get_member_financial_data(request, member_id):
    """Get member's financial data for payment processing"""
    try:
        member = get_object_or_404(Member, pk=member_id)
        
        # Get savings accounts
        savings_accounts = list(
            member.savings_accounts.filter(is_active=True).values(
                'id', 'account_number', 'balance', 'product__name'
            )
        )
        
        # Get active loans
        active_loans = list(
            member.loans.filter(status='active').values(
                'id', 'loan_product__name', 'total_balance', 'monthly_payment'
            )
        )
        
        # Check registration fee status
        registration_fee_info = {
            'paid': member.registration_fee_paid,
            'amount': float(member.registration_fee_amount),
            'required': not member.registration_fee_paid
        }
        
        return JsonResponse({
            'success': True,
            'savings_accounts': savings_accounts,
            'active_loans': active_loans,
            'registration_fee': registration_fee_info,
            'member_name': member.user.get_full_name()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def financial_summary(request):
    """View comprehensive financial summary with real data"""
    # Date filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = timezone.now().replace(day=1).date()  # First day of current month
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Core financial metrics
    total_assets = Account.objects.filter(
        category__category_type='asset',
        is_active=True
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    total_liabilities = Account.objects.filter(
        category__category_type='liability',
        is_active=True
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    total_equity = Account.objects.filter(
        category__category_type='equity',
        is_active=True
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # Income and expenses for the period
    period_income = Transaction.objects.filter(
        transaction_type='income',
        transaction_date__date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    period_expenses = Transaction.objects.filter(
        transaction_type='expense',
        transaction_date__date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    net_income = period_income - period_expenses
    
    # Savings metrics
    total_savings_balance = SavingsAccount.objects.filter(
        is_active=True
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    savings_deposits_period = SavingsTransaction.objects.filter(
        transaction_type='deposit',
        created_at__date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Loan metrics
    total_loans_outstanding = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('total_balance'))['total'] or Decimal('0.00')
    
    loan_repayments_period = LoanRepayment.objects.filter(
        payment_date__range=[start_date, end_date]
    ).aggregate(total=Sum('payment_amount'))['total'] or Decimal('0.00')
    
    # Cash flow metrics
    cash_inflow_period = CashFlow.objects.filter(
        flow_type='inflow',
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    cash_outflow_period = CashFlow.objects.filter(
        flow_type='outflow',
        date__range=[start_date, end_date]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    net_cash_flow = cash_inflow_period - cash_outflow_period
    
    # Financial ratios
    current_ratio = total_assets / total_liabilities if total_liabilities > 0 else Decimal('0.00')
    equity_ratio = total_equity / total_assets if total_assets > 0 else Decimal('0.00')
    
    # Member engagement metrics
    active_members = Member.objects.filter(membership_status='active').count()
    members_with_savings = Member.objects.filter(
        savings_accounts__is_active=True
    ).distinct().count()
    members_with_loans = Member.objects.filter(
        loans__status='active'
    ).distinct().count()
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        # Balance Sheet
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        # Income Statement
        'period_income': period_income,
        'period_expenses': period_expenses,
        'net_income': net_income,
        # Savings
        'total_savings_balance': total_savings_balance,
        'savings_deposits_period': savings_deposits_period,
        # Loans
        'total_loans_outstanding': total_loans_outstanding,
        'loan_repayments_period': loan_repayments_period,
        # Cash Flow
        'cash_inflow_period': cash_inflow_period,
        'cash_outflow_period': cash_outflow_period,
        'net_cash_flow': net_cash_flow,
        # Ratios
        'current_ratio': round(current_ratio, 2),
        'equity_ratio': round(equity_ratio * 100, 2),
        # Member Metrics
        'active_members': active_members,
        'members_with_savings': members_with_savings,
        'members_with_loans': members_with_loans,
        'savings_penetration': round((members_with_savings / active_members * 100) if active_members > 0 else 0, 2),
        'loan_penetration': round((members_with_loans / active_members * 100) if active_members > 0 else 0, 2),
    }
    
    return render(request, 'transactions/financial_summary.html', context)

@login_required
def ajax_member_accounts(request, member_id):
    """Get member's accounts for AJAX requests"""
    try:
        member = get_object_or_404(Member, pk=member_id)
        
        # Get savings accounts
        savings_accounts = []
        for account in member.savings_accounts.filter(is_active=True):
            savings_accounts.append({
                'id': account.id,
                'account_number': account.account_number,
                'balance': str(account.balance),
                'product_name': account.product.name
            })
        
        # Get active loans
        active_loans = []
        for loan in member.loans.filter(status='active'):
            active_loans.append({
                'id': loan.id,
                'product_name': loan.loan_product.name,
                'balance': str(loan.total_balance),
                'monthly_payment': str(loan.monthly_payment or 0)
            })
        
        # Registration fee info
        registration_fee = {
            'paid': member.registration_fee_paid,
            'amount': str(member.registration_fee_amount),
            'required': not member.registration_fee_paid
        }
        
        return JsonResponse({
            'success': True,
            'member_name': member.user.get_full_name(),
            'savings_accounts': savings_accounts,
            'active_loans': active_loans,
            'registration_fee': registration_fee
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def bulk_transaction_processing(request):
    """Process multiple transactions at once"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transactions_data = data.get('transactions', [])
            
            if not transactions_data:
                return JsonResponse({'success': False, 'error': 'No transactions provided'})
            
            with db_transaction.atomic():
                created_transactions = []
                
                for txn_data in transactions_data:
                    member_id = txn_data.get('member_id')
                    payment_type = txn_data.get('payment_type')
                    amount = Decimal(str(txn_data.get('amount', '0')))
                    description = txn_data.get('description', '')
                    
                    if amount <= 0:
                        continue
                    
                    member = Member.objects.get(pk=member_id)
                    
                    # Create transaction
                    transaction = Transaction.objects.create(
                        transaction_type='income',
                        description=description or f'{payment_type} from {member.user.get_full_name()}',
                        amount=amount,
                        member=member,
                        created_by=request.user,
                        status='completed'
                    )
                    
                    # Process payment
                    handle_payment_by_type(transaction, payment_type, '', amount)
                    
                    created_transactions.append({
                        'transaction_id': transaction.transaction_id,
                        'member_name': member.user.get_full_name(),
                        'amount': str(amount)
                    })
                
                return JsonResponse({
                    'success': True,
                    'message': f'{len(created_transactions)} transactions processed successfully',
                    'transactions': created_transactions
                })
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return render(request, 'transactions/bulk_processing.html')
