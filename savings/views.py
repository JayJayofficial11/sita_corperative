from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from .models import SavingsAccount, SavingsTransaction, SavingsProduct
from .forms import SavingsSearchForm, SavingsDepositForm, SavingsWithdrawalForm
from members.models import Member

@login_required
def savings_accounts(request):
    """List all savings accounts with search and statistics"""
    # Get all accounts initially
    accounts = SavingsAccount.objects.select_related('member__user').all()
    
    # Handle search
    search_form = SavingsSearchForm(request.GET)
    if search_form.is_valid():
        if search_form.cleaned_data['search']:
            search_term = search_form.cleaned_data['search']
            accounts = accounts.filter(
                Q(member__user__first_name__icontains=search_term) |
                Q(member__user__last_name__icontains=search_term) |
                Q(account_number__icontains=search_term)
            )
        
        if search_form.cleaned_data['status']:
            accounts = accounts.filter(status=search_form.cleaned_data['status'])
        
        if search_form.cleaned_data['balance_min']:
            accounts = accounts.filter(balance__gte=search_form.cleaned_data['balance_min'])
        
        if search_form.cleaned_data['balance_max']:
            accounts = accounts.filter(balance__lte=search_form.cleaned_data['balance_max'])
    
    # Order accounts
    accounts = accounts.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(accounts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    active_accounts_count = SavingsAccount.objects.filter(status='active').count()
    total_balance = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or 0
    
    # New accounts this month
    current_month = datetime.now().replace(day=1)
    new_accounts_count = SavingsAccount.objects.filter(created_at__gte=current_month).count()
    
    context = {
        'accounts': page_obj,
        'search_form': search_form,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'active_accounts_count': active_accounts_count,
        'total_balance': total_balance,
        'new_accounts_count': new_accounts_count,
    }
    return render(request, 'savings/accounts.html', context)

@login_required
def record_deposit(request):
    """Record savings deposit"""
    if request.method == 'POST':
        form = SavingsDepositForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                transaction = form.save()
                messages.success(request, f'Deposit of ₦{transaction.amount:,.2f} recorded successfully!')
                return redirect('savings:accounts')
            except Exception as e:
                messages.error(request, f'Deposit failed: {str(e)}')
    else:
        form = SavingsDepositForm(user=request.user)
    
    context = {
        'form': form,
        'current_date': datetime.now().date(),
        'current_time': datetime.now().time(),
    }
    return render(request, 'savings/deposit.html', context)

@login_required
def process_withdrawal(request):
    """Process savings withdrawal"""
    if request.method == 'POST':
        form = SavingsWithdrawalForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                transaction = form.save()
                messages.success(request, f'Withdrawal of ₦{transaction.amount:,.2f} processed successfully!')
                return redirect('savings:accounts')
            except Exception as e:
                messages.error(request, f'Withdrawal failed: {str(e)}')
    else:
        form = SavingsWithdrawalForm(user=request.user)
    
    context = {
        'form': form,
        'current_date': datetime.now().date(),
        'current_time': datetime.now().time(),
    }
    return render(request, 'savings/withdraw.html', context)

@login_required
def savings_reports(request):
    """Savings reports"""
    return render(request, 'savings/reports.html')

@login_required
def account_detail(request, pk):
    """Savings account detail view"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    context = {'account': account}
    return render(request, 'savings/detail.html', context)

@login_required
def member_savings(request, member_id):
    """View all savings accounts for a specific member"""
    member = get_object_or_404(Member, pk=member_id)
    accounts = SavingsAccount.objects.filter(member=member).order_by('-created_at')
    
    # Calculate totals
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or 0
    active_accounts = accounts.filter(status='active').count()
    
    # Get recent transactions
    recent_transactions = SavingsTransaction.objects.filter(
        savings_account__member=member
    ).order_by('-transaction_date')[:10]
    
    context = {
        'member': member,
        'accounts': accounts,
        'total_balance': total_balance,
        'active_accounts': active_accounts,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'savings/member_savings.html', context)

@login_required
def export_transactions(request, pk):
    """Export transactions for a specific savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    transactions = SavingsTransaction.objects.filter(savings_account=account).order_by('-transaction_date')
    
    # Simple JSON export for now - could be enhanced to support PDF/Excel
    transaction_data = []
    for transaction in transactions:
        transaction_data.append({
            'date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'type': transaction.transaction_type,
            'amount': float(transaction.amount),
            'balance_after': float(transaction.balance_after),
            'description': transaction.description,
            'reference': transaction.reference_number,
        })
    
    response_data = {
        'account_number': account.account_number,
        'member': account.member.user.get_full_name(),
        'current_balance': float(account.balance),
        'transactions': transaction_data,
        'export_date': datetime.now().isoformat(),
    }
    
    response = JsonResponse(response_data)
    response['Content-Disposition'] = f'attachment; filename="savings_transactions_{account.account_number}.json"'
    return response

@login_required
def undo_savings_transaction(request, pk):
    """Undo a recent savings transaction (for duplicate submissions)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})
    
    try:
        transaction = get_object_or_404(SavingsTransaction, pk=pk)
        
        # Check if transaction is recent (within last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        if transaction.transaction_date < timezone.now() - timedelta(hours=24):
            return JsonResponse({'success': False, 'error': 'Transaction is too old to undo'})
        
        # Check if transaction is completed
        if transaction.status != 'completed':
            return JsonResponse({'success': False, 'error': 'Cannot undo incomplete transaction'})
        
        # Reverse the transaction effect on the account balance
        savings_account = transaction.savings_account
        
        if transaction.transaction_type in ['compulsory', 'voluntary', 'deposit']:
            # Reverse a deposit - subtract from balance
            savings_account.balance -= transaction.amount
        elif transaction.transaction_type == 'withdrawal':
            # Reverse a withdrawal - add back to balance
            savings_account.balance += transaction.amount
        
        # Update available balance
        savings_account.update_available_balance()
        savings_account.save()
        
        # Delete the transaction
        transaction.delete()
        
        return JsonResponse({'success': True, 'message': 'Transaction undone successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
