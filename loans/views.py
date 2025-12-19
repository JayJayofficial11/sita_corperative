from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction # Import transaction
from django.db.models import Q, Sum, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Loan, LoanProduct, LoanRepayment
from .forms import LoanApplicationForm, LoanApprovalForm, LoanRejectionForm, LoanRepaymentForm, LoanSearchForm
from members.models import Member
from savings.models import SavingsAccount, SavingsTransaction
from decimal import Decimal
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

def set_loan_collateral(member, loan):
    """Set member's existing savings as collateral for the loan"""
    try:
        savings_account = SavingsAccount.objects.get(member=member)
        
        if savings_account.balance > 0:
            # Set existing balance as collateral
            savings_account.set_collateral(savings_account.balance)
            
            # Create a transaction record for collateral
            SavingsTransaction.objects.create(
                savings_account=savings_account,
                transaction_type='collateral',
                amount=savings_account.balance,
                balance_before=savings_account.balance,
                balance_after=savings_account.balance,
                description=f'Collateral set for loan {loan.loan_id}',
                processed_by=None,
                related_loan=loan,
                is_loan_repayment=False
            )
            
            return True
    except SavingsAccount.DoesNotExist:
        pass
    return False

def process_loan_repayment_from_deposit(member, loan, amount, deposit_transaction):
    """Process loan repayment from member's new deposit with flexible allocation"""
    try:
        savings_account = SavingsAccount.objects.get(member=member)
        
        if not savings_account.has_active_loan:
            return False, "Member has no active loan"
        
        if amount <= 0:
            return False, "Invalid deposit amount"
        
        # Use actual loan balances (these are updated during disbursement)
        interest_remaining = loan.interest_balance
        principal_remaining = loan.principal_balance
        total_outstanding = interest_remaining + principal_remaining
        
        # Calculate how much to use for loan repayment
        loan_repayment_amount = min(amount, total_outstanding)
        remaining_for_savings = amount - loan_repayment_amount
        
        # Allocate loan repayment: Interest first, then principal
        interest_payment = min(loan_repayment_amount, interest_remaining)
        principal_payment = min(loan_repayment_amount - interest_payment, principal_remaining)
        
        # If there is a repayment portion, create a savings transaction to reflect repayment
        if loan_repayment_amount > 0:
            SavingsTransaction.objects.create(
                savings_account=savings_account,
                transaction_type='loan_repayment',
                amount=loan_repayment_amount,
                balance_before=savings_account.balance,
                balance_after=savings_account.balance - loan_repayment_amount,
                description=f'Auto loan repayment from deposit for {loan.loan_id} - Interest: ₦{interest_payment:,.2f}, Principal: ₦{principal_payment:,.2f}',
                processed_by=None,
                related_loan=loan,
                is_loan_repayment=True,
                repayment_principal=principal_payment,
                repayment_interest=interest_payment
            )
            # Subtract only the loan repayment amount from savings balance (remaining stays as savings)
            savings_account.balance = savings_account.balance - loan_repayment_amount
            savings_account.update_available_balance()
            savings_account.save()

            # Adjust the original deposit transaction to reflect only the remaining amount that stays as savings
            if deposit_transaction and deposit_transaction.transaction_type in ['compulsory', 'voluntary']:
                original_before = deposit_transaction.balance_before
                deposit_transaction.amount = remaining_for_savings
                deposit_transaction.balance_after = original_before + remaining_for_savings
                deposit_transaction.description = (deposit_transaction.description or '') + \
                    f" (Auto-split: ₦{loan_repayment_amount:,.2f} applied to loan, ₦{remaining_for_savings:,.2f} kept as savings)"
                deposit_transaction.save()
        
        # Create loan repayment record (only if there was actual loan repayment)
        if loan_repayment_amount > 0:
            repayment = LoanRepayment.objects.create(
                loan=loan,
                amount=loan_repayment_amount,
                principal_amount=principal_payment,
                interest_amount=interest_payment,
                balance_before=loan.total_balance,
                balance_after=loan.total_balance - loan_repayment_amount,
                due_date=timezone.now().date(),
                processed_by=None,
                notes=f'Flexible repayment from deposit - Interest: ₦{interest_payment:,.2f}, Principal: ₦{principal_payment:,.2f}'
            )
        
        # Update loan balances (only if there was actual loan repayment)
        if loan_repayment_amount > 0:
            loan.principal_balance -= principal_payment
            loan.interest_balance -= interest_payment
            loan.total_balance -= loan_repayment_amount
        
        # Check if loan is fully paid
        if loan_repayment_amount > 0:
            if loan.total_balance <= 0:
                loan.status = 'completed'
                loan.save()
                # Clear collateral
                savings_account.clear_collateral()
            else:
                loan.save()
        
        # Prepare success message
        if loan_repayment_amount > 0 and remaining_for_savings > 0:
            # Both loan repayment and savings addition
            message = f"Successfully repaid ₦{loan_repayment_amount:,.2f} to loan and added ₦{remaining_for_savings:,.2f} to savings"
        elif loan_repayment_amount > 0:
            # Only loan repayment
            message = f"Successfully repaid ₦{loan_repayment_amount:,.2f} to loan"
        else:
            # Only savings addition (no loan repayment needed)
            message = f"Added ₦{remaining_for_savings:,.2f} to savings (loan already paid off)"
        
        return True, message
        
    except SavingsAccount.DoesNotExist:
        return False, "Member has no savings account"
    except Exception as e:
        return False, f"Repayment failed: {str(e)}"

def process_loan_repayment_from_savings(member, loan, amount):
    """Process loan repayment from member's new savings with flexible allocation"""
    try:
        savings_account = SavingsAccount.objects.get(member=member)
        
        if not savings_account.has_active_loan:
            return False, "Member has no active loan"
        
        # Get amount available for repayment (new savings only)
        available_for_repayment = savings_account.get_loan_repayment_amount()
        
        if available_for_repayment <= 0:
            return False, "No new savings available for loan repayment"
        
        # Use the minimum of requested amount and available amount
        repayment_amount = min(amount, available_for_repayment)
        
        if repayment_amount <= 0:
            return False, "Insufficient new savings for repayment"
        
        # Use actual loan balances (these are updated during disbursement)
        interest_remaining = loan.interest_balance
        principal_remaining = loan.principal_balance
        
        # Allocate payment: Interest first, then principal
        interest_payment = min(repayment_amount, interest_remaining)
        principal_payment = min(repayment_amount - interest_payment, principal_remaining)
        
        # Create savings transaction for loan repayment
        SavingsTransaction.objects.create(
            savings_account=savings_account,
            transaction_type='loan_repayment',
            amount=repayment_amount,
            balance_before=savings_account.balance,
            balance_after=savings_account.balance - repayment_amount,
            description=f'Flexible loan repayment for {loan.loan_id} - Interest: ₦{interest_payment:,.2f}, Principal: ₦{principal_payment:,.2f}',
            processed_by=None,
            related_loan=loan,
            is_loan_repayment=True,
            repayment_principal=principal_payment,
            repayment_interest=interest_payment
        )
        
        # Update savings balance
        savings_account.balance -= repayment_amount
        savings_account.update_available_balance()
        savings_account.save()
        
        # Create loan repayment record
        repayment = LoanRepayment.objects.create(
            loan=loan,
            amount=repayment_amount,
            principal_amount=principal_payment,
            interest_amount=interest_payment,
            balance_before=loan.total_balance,
            balance_after=loan.total_balance - repayment_amount,
            due_date=timezone.now().date(),
            processed_by=None,
            notes=f'Flexible repayment from savings - Interest: ₦{interest_payment:,.2f}, Principal: ₦{principal_payment:,.2f}'
        )
        
        # Update loan balances
        loan.principal_balance -= principal_payment
        loan.interest_balance -= interest_payment
        loan.total_balance -= repayment_amount
        
        # Check if loan is fully paid
        if loan.total_balance <= 0:
            loan.status = 'completed'
            loan.save()
            # Clear collateral
            savings_account.clear_collateral()
        else:
            loan.save()
        
        # Determine phase for user feedback
        phase = "Interest Phase" if interest_remaining > 0 else "Principal Phase"
        
        return True, f"Successfully repaid ₦{repayment_amount:,.2f} from savings ({phase})"
        
    except SavingsAccount.DoesNotExist:
        return False, "Member has no savings account"
    except Exception as e:
        return False, f"Repayment failed: {str(e)}"

def allocate_savings_to_loan(member, loan):
    """Legacy function - now redirects to new repayment system"""
    return process_loan_repayment_from_savings(member, loan, Decimal('999999999'))

@login_required
def dashboard(request):
    """Loan management dashboard"""
    # Summary statistics
    total_loans = Loan.objects.count()
    active_loans = Loan.objects.filter(status='active').count()
    pending_applications = Loan.objects.filter(status='pending').count()
    total_disbursed = Loan.objects.filter(status__in=['active', 'completed']).aggregate(
        total=Sum('approved_amount')
    )['total'] or 0
    total_outstanding = Loan.objects.filter(status='active').aggregate(
        total=Sum('total_balance')
    )['total'] or 0
    
    # Recent activities
    recent_applications = Loan.objects.filter(status='pending').order_by('-created_at')[:5]
    recent_repayments = LoanRepayment.objects.order_by('-payment_date')[:5]
    
    # Charts data
    loan_status_data = list(Loan.objects.values('status').annotate(count=Count('id')))
    
    context = {
        'total_loans': total_loans,
        'active_loans': active_loans,
        'pending_applications': pending_applications,
        'total_disbursed': total_disbursed,
        'total_outstanding': total_outstanding,
        'recent_applications': recent_applications,
        'recent_repayments': recent_repayments,
        'loan_status_data': json.dumps(loan_status_data),
    }
    return render(request, 'loans/dashboard.html', context)

@login_required
def loan_applications(request):
    """List all loan applications with search and filter"""
    # Handle approval/rejection actions
    if request.method == 'POST':
        action = request.POST.get('action')
        loan_id = request.POST.get('loan_id')

        # Debug: Log the POST data
        print(f"DEBUG: POST data received - Action: {action}, Loan ID: {loan_id}")
        print(f"DEBUG: All POST data: {dict(request.POST)}")

        try:
            loan = Loan.objects.get(pk=loan_id)
            print(f"DEBUG: Found loan: {loan.loan_id}")

            if action == 'approve':
                # Approve with specified amount and fixed 10% interest
                if loan.status == 'pending':
                    approved_amount = Decimal(request.POST.get('approved_amount', 0))
                    approval_notes = request.POST.get('approval_notes', '')

                    if approved_amount > 0:
                        loan.approved_amount = approved_amount
                        loan.interest_rate = Decimal('10.00')  # Fixed 10%
                        loan.tenure_months = 22  # Fixed 22 months
                        loan.status = 'approved'
                        loan.approved_by = request.user
                        loan.approval_date = timezone.now()
                        loan.approval_notes = approval_notes or f'Approved for ₦{approved_amount:,.2f} with fixed 10% interest rate'
                        loan.save()

                        print(f"DEBUG: Loan {loan.loan_id} approved for ₦{approved_amount:,.2f}")
                        messages.success(request, f'Loan {loan.loan_id} approved for ₦{approved_amount:,.2f}!')
                    else:
                        print(f"DEBUG: Invalid approved amount")
                        messages.error(request, 'Please provide a valid approved amount.')
                else:
                    print(f"DEBUG: Loan is not pending")
                    messages.error(request, 'This loan cannot be approved.')
            elif action == 'reject':
                rejection_reason = request.POST.get('rejection_reason', '')
                if loan.status == 'pending':
                    loan.status = 'rejected'
                    loan.rejected_by = request.user
                    loan.rejection_date = timezone.now()
                    loan.rejection_reason = rejection_reason or 'Rejected by management'
                    loan.save()
                    messages.warning(request, f'Loan {loan.loan_id} rejected!')
                else:
                    messages.error(request, 'This loan cannot be rejected.')
        except Exception as e:
            messages.error(request, f'Error processing loan application: {str(e)}')
        return redirect('loans:applications')
        
    form = LoanSearchForm(request.GET or None)

    loans = Loan.objects.all().order_by('-created_at')

    if form.is_valid():
        search = form.cleaned_data.get('search')
        status = form.cleaned_data.get('status')
        loan_product = form.cleaned_data.get('loan_product')
        amount_min = form.cleaned_data.get('amount_min')
        amount_max = form.cleaned_data.get('amount_max')

        if search:
            loans = loans.filter(
                Q(member__user__first_name__icontains=search) |
                Q(member__user__last_name__icontains=search) |
                Q(loan_id__icontains=search)
            )
        if status:
            loans = loans.filter(status=status)
        if loan_product:
            loans = loans.filter(loan_product=loan_product)
        if amount_min:
            loans = loans.filter(requested_amount__gte=amount_min)
        if amount_max:
            loans = loans.filter(requested_amount__lte=amount_max)

    # Calculate statistics
    pending_applications = loans.filter(status='pending').count()
    approved_applications = loans.filter(status='approved').count()
    rejected_applications = loans.filter(status='rejected').count()
    total_requested = loans.aggregate(total=Sum('requested_amount'))['total'] or 0

    paginator = Paginator(loans, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'loans/applications.html', {
        'search_form': form,
        'page_obj': page_obj,
        'loans': page_obj,
        'applications': page_obj,  # For template compatibility
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'total_requested': total_requested,
        'is_paginated': page_obj.has_other_pages()
    })

@login_required
def apply_for_loan(request):
    """Create new loan application with enhanced eligibility checks"""
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            try:
                loan = form.save(commit=False)
                
                # Check eligibility using new rules
                can_apply, message = loan.check_eligibility()
                if not can_apply:
                    messages.error(request, f'Loan application rejected: {message}')
                    return render(request, 'loans/apply.html', {'form': form})
                
                # Set the interest rate to 10% (fixed)
                loan.interest_rate = Decimal('10.00')
                
                # Set tenure to 22 months (20 + 2 for interest)
                loan.tenure_months = 22
                
                loan.save()
                messages.success(request, f'Loan application {loan.loan_id} submitted successfully!')
                return redirect('loans:applications')
            except Exception as e:
                messages.error(request, f'Error submitting loan application: {str(e)}')
                return render(request, 'loans/apply.html', {'form': form})
    else:
        form = LoanApplicationForm()
    
    return render(request, 'loans/apply.html', {'form': form})

@login_required
def loan_detail(request, pk):
    """View loan details"""
    loan = get_object_or_404(Loan, pk=pk)
    repayments = LoanRepayment.objects.filter(loan=loan).order_by('-payment_date')
    
    # Calculate totals for the template
    total_principal = sum(rep.principal_amount for rep in repayments)
    total_interest = sum(rep.interest_amount for rep in repayments)
    total_payments = sum(rep.amount for rep in repayments)
    
    return render(request, 'loans/detail.html', {
        'loan': loan,
        'repayments': repayments,
        'total_principal': total_principal,
        'total_interest': total_interest,
        'total_payments': total_payments
    })

@login_required
def loan_details_ajax(request, pk):
    """AJAX endpoint for loan details"""
    try:
        loan = get_object_or_404(Loan, pk=pk)
        
        # Get loan progress information
        loan_progress = loan.member.get_loan_progress()
        
        # Calculate progress percentages
        total_interest = loan.total_interest
        total_principal = loan.approved_amount or loan.requested_amount
        
        interest_paid = sum(rep.interest_amount for rep in loan.repayments.filter(status='completed'))
        principal_paid = sum(rep.principal_amount for rep in loan.repayments.filter(status='completed'))
        
        interest_progress = (interest_paid / total_interest * 100) if total_interest > 0 else 0
        principal_progress = (principal_paid / total_principal * 100) if total_principal > 0 else 0
        
        return JsonResponse({
            'success': True,
            'loan': {
                'id': loan.id,
                'loan_id': loan.loan_id,
                'total_balance': float(loan.total_balance),
                'interest_balance': float(loan.interest_balance),
                'principal_balance': float(loan.principal_balance),
                'interest_progress': round(interest_progress, 2),
                'principal_progress': round(principal_progress, 2),
                'status': loan.status,
                'member_name': loan.member.user.get_full_name()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error fetching loan details: {str(e)}'
    })

@login_required
def disburse_loan(request, pk):
    """Disburse approved loan"""
    from django.db.models import Sum
    loan = get_object_or_404(Loan, pk=pk)
    
    # Only check loan status on POST requests (when actually trying to disburse)
    if request.method == 'POST':
        print(f"DEBUG: Loan status check - Status: {loan.status}, Required: 'approved'")
        if loan.status != 'approved':
            error_message = 'This loan cannot be disbursed.'
            print(f"DEBUG: Loan status error - {error_message}")
            messages.error(request, error_message)

            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })

            return redirect('loans:detail', pk=pk)

    # Get statistics for the disbursement center
    pending_loans = Loan.objects.filter(status='approved')
    pending_disbursement = pending_loans.count()
    disbursed_today = Loan.objects.filter(
        disbursement_date__date=timezone.now().date(),
        status='active'
    ).count()
    pending_amount = pending_loans.aggregate(total=Sum('approved_amount'))['total'] or 0
    
    if request.method == 'POST':
        print(f"DEBUG: Disbursing loan {loan.pk} - Status: {loan.status}")
        try:
            with transaction.atomic():
                from transactions.models import Transaction, TransactionEntry, Account, AccountCategory
                from decimal import Decimal
                from django.db.models import Sum # Moved to top of function

                # Check if cooperative has enough balance for disbursement
                # Use the same calculation as dashboard for accurate balance
                print("DEBUG: Calculating cooperative balance...")

                # Calculate available balance for disbursement (same as dashboard)
                from savings.models import SavingsAccount
                from members.models import Member

                # 1. Total member savings
                total_member_savings = SavingsAccount.objects.aggregate(
                    total=Sum('balance')
                )['total'] or Decimal('0')

                # 2. Total disbursed loans (money already given out)
                total_disbursed_loans = Loan.objects.filter(
                    status='active'
                ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')

                # 3. Loan interest earned
                loan_interest_earned = LoanRepayment.objects.aggregate(
                    total=Sum('interest_amount')
                )['total'] or Decimal('0')

                # 4. Registration fees
                registration_fees = Member.regular_members().aggregate(
                    total=Sum('registration_fee_amount')
                )['total'] or Decimal('0')

                # 5. Other income
                other_income = Transaction.objects.filter(
                    transaction_type='income'
                ).exclude(description__icontains='registration').aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')

                # 6. Calculate total expenses from transactions
                total_expenses = Transaction.objects.filter(
                    transaction_type='expense',
                    status='completed'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                # Available balance for new loans = Member savings - Disbursed loans + Other income - Expenses
                # Expenses reduce the available balance
                available_balance = (
                    total_member_savings -
                    total_disbursed_loans +
                    loan_interest_earned +
                    registration_fees +
                    other_income -
                    total_expenses  # Subtract expenses from available balance
                )

                print(f"DEBUG: Available balance breakdown:")
                print(f"  - Member savings: ₦{total_member_savings:,.2f}")
                print(f"  - Disbursed loans: -₦{total_disbursed_loans:,.2f}")
                print(f"  - Interest earned: +₦{loan_interest_earned:,.2f}")
                print(f"  - Registration fees: +₦{registration_fees:,.2f}")
                print(f"  - Other income: +₦{other_income:,.2f}")
                print(f"  - Total expenses: -₦{total_expenses:,.2f}")
                print(f"  - AVAILABLE: ₦{available_balance:,.2f}")
                print(f"  - REQUIRED: ₦{loan.approved_amount:,.2f}")

                if available_balance < loan.approved_amount:
                    error_message = f'Insufficient available balance. Available: ₦{available_balance:,.2f}, Required: ₦{loan.approved_amount:,.2f}'
                    print(f"DEBUG: Insufficient balance - {error_message}")
                    messages.error(request, error_message)

                    # Handle AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': error_message
                        })

                    return redirect('loans:detail', pk=pk)

                # IMPORTANT: Only use approved_amount for disbursement (never requested_amount)
                # The approved_amount is the actual amount being disbursed
                if not loan.approved_amount:
                    error_message = 'Loan must have an approved amount before disbursement.'
                    messages.error(request, error_message)
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'message': error_message})
                    return redirect('loans:detail', pk=pk)
                
                # Calculate loan details using new system (10% interest added immediately)
                # Use ONLY approved_amount - never requested_amount
                loan.principal_balance = loan.approved_amount
                loan.interest_balance = loan.principal_balance * Decimal('0.10')  # 10% of principal
                loan.total_balance = loan.principal_balance + loan.interest_balance
                loan.status = 'active'
                loan.disbursed_by = request.user
                loan.disbursement_date = timezone.now()
                loan.save()
                print(f"DEBUG: Loan {loan.pk} disbursed successfully - Status: {loan.status}")
                print(f"DEBUG: Disbursed amount: ₦{loan.approved_amount:,.2f} (NOT requested: ₦{loan.requested_amount:,.2f})")

                # IMPORTANT: Do NOT add any money to member's savings account during disbursement
                # The loan amount is given to the member in cash/transfer, NOT added to their savings
                # Interest (10%) is part of the loan balance they owe, NOT added to their savings
                # Only set existing savings as collateral (if any exists) - this does NOT add money
                
                # Get member's savings account balance BEFORE any operations
                try:
                    savings_account = SavingsAccount.objects.get(member=loan.member)
                    balance_before = savings_account.balance
                except SavingsAccount.DoesNotExist:
                    balance_before = Decimal('0.00')
                    savings_account = None
                
                # Set existing savings as collateral (if any exists) - this does NOT add money
                collateral_set = set_loan_collateral(loan.member, loan)
                if collateral_set:
                    messages.info(request, f'Member\'s existing savings of ₦{loan.member.savings_account.balance:,.2f} set as collateral.')
                else:
                    messages.warning(request, 'Member has no existing savings to set as collateral.')
                
                # Verify that no money was added to savings (balance should be same or less, never more)
                if savings_account:
                    savings_account.refresh_from_db()
                    if savings_account.balance > balance_before:
                        error_message = f'ERROR: Savings balance increased during disbursement! This should not happen. Balance before: ₦{balance_before:,.2f}, After: ₦{savings_account.balance:,.2f}'
                        print(f"DEBUG: {error_message}")
                        messages.error(request, error_message)

                # Create transaction entries for disbursement
                try:
                    # Get or create cooperative account for transactions
                    print("DEBUG: Creating cooperative account for transactions...")
                    cooperative_account, created = Account.objects.get_or_create(
                        code='COOP001',
                        defaults={
                            'name': 'Cooperative Main Account',
                            'category': AccountCategory.objects.get_or_create(
                                code='1000',
                                defaults={
                                    'name': 'Cash and Bank',
                                    'category_type': 'asset'
                                }
                            )[0],
                            'balance': Decimal('0.00')
                        }
                    )
                    print(f"DEBUG: Cooperative account created: {created}, ID: {cooperative_account.id}")

                    # Get or create loan receivable account
                    print("DEBUG: Creating loan receivable account...")
                    loan_account, created = Account.objects.get_or_create(
                        code='1200',
                        defaults={
                            'name': 'Loans Receivable',
                            'category': AccountCategory.objects.get_or_create(
                                code='1200',
                                defaults={
                                    'name': 'Loans Receivable',
                                    'category_type': 'asset'
                                }
                            )[0],
                            'balance': Decimal('0.00')
                        }
                    )
                    print(f"DEBUG: Loan account created: {created}, ID: {loan_account.id}")

                    # Create disbursement transaction
                    # IMPORTANT: Use ONLY approved_amount, never requested_amount
                    print("DEBUG: Creating disbursement transaction...")
                    print(f"DEBUG: Transaction amount will be: ₦{loan.approved_amount:,.2f} (approved amount)")
                    disbursement_transaction = Transaction.objects.create(
                        transaction_type='transfer',
                        description=f'Loan disbursement for {loan.loan_id} - {loan.member.user.get_full_name()} (Approved: ₦{loan.approved_amount:,.2f})',
                        amount=loan.approved_amount,  # Use ONLY approved_amount
                        created_by=request.user,
                        status='completed'
                    )
                    print(f"DEBUG: Transaction created with ID: {disbursement_transaction.id}")

                    # Create journal entries: Debit Loans Receivable, Credit Cooperative Account
                    print("DEBUG: Creating journal entries...")
                    TransactionEntry.objects.create(
                        transaction=disbursement_transaction,
                        account=loan_account,
                        entry_type='debit',
                        amount=loan.approved_amount,
                        description=f'Loan disbursement - {loan.loan_id}'
                    )
                    print("DEBUG: Debit entry created")

                    TransactionEntry.objects.create(
                        transaction=disbursement_transaction,
                        account=cooperative_account,
                        entry_type='credit',
                        amount=loan.approved_amount,
                        description=f'Cash payment for loan - {loan.loan_id}'
                    )
                    print("DEBUG: Credit entry created")

                    # Update account balances manually (since signals might not work for existing transactions)
                    print("DEBUG: Updating account balances...")
                    loan_account.balance += loan.approved_amount
                    loan_account.save()
                    print(f"DEBUG: Loan account balance updated to: {loan_account.balance}")

                    cooperative_account.balance -= loan.approved_amount
                    cooperative_account.save()
                    print(f"DEBUG: Cooperative account balance updated to: {cooperative_account.balance}")

                except Exception as e:
                    print(f"Error creating transaction entries: {str(e)}")
                    error_message = f'Error creating transaction entries: {str(e)}'
                    messages.error(request, error_message)

                    # Handle AJAX requests
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': error_message
                        })

                    return redirect('loans:detail', pk=pk)

                messages.success(request, f'Loan {loan.loan_id} disbursed successfully! Amount: ₦{loan.approved_amount:,.2f}')

                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Loan {loan.loan_id} disbursed successfully! Amount: ₦{loan.approved_amount:,.2f}',
                        'redirect_url': reverse('loans:applications')
                    })

                return redirect('loans:applications')

        except Exception as e:
            error_message = f'Error disbursing loan: {str(e)}'
            messages.error(request, error_message)

            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })

            return redirect('loans:detail', pk=pk)

    return render(request, 'loans/disburse.html', {
        'loan': loan,
        'approved_loans': pending_loans,
        'pending_disbursement': pending_disbursement,
        'disbursed_today': disbursed_today,
        'pending_amount': pending_amount
    })

@login_required
def process_loan_repayment_from_savings(request, pk):
    """Process loan repayment from member's savings account"""
    from django.db import transaction
    if request.method == 'POST':
        try:
            with transaction.atomic():
                loan = get_object_or_404(Loan, pk=pk)
                amount_to_repay = Decimal(request.POST.get('amount'))
                
                if amount_to_repay <= 0:
                    return JsonResponse({'success': False, 'message': 'Invalid repayment amount.'})
        
        except SavingsAccount.DoesNotExist:
            return False, "Member has no savings account"
        except Exception as e:
            return False, f"Repayment failed: {str(e)}"

@login_required
def loan_repayments(request):
    """Process loan repayment"""
    if request.method == 'POST':
        form = LoanRepaymentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                repayment = form.save(commit=False)
                loan = repayment.loan
                
                # Calculate repayment breakdown using new flexible system
                repayment.balance_before = loan.total_balance
                
                # Get current repayment totals
                completed_repayments = loan.repayments.filter(status='completed')
                interest_paid = sum(rep.interest_amount for rep in completed_repayments)
                principal_paid = sum(rep.principal_amount for rep in completed_repayments)
                
                # Use actual loan balances (these are updated during disbursement)
                interest_remaining = loan.interest_balance
                principal_remaining = loan.principal_balance
                
                # Allocate payment: Interest first, then principal
                repayment.interest_amount = min(repayment.amount, interest_remaining)
                repayment.principal_amount = min(repayment.amount - repayment.interest_amount, principal_remaining)
                repayment.balance_after = loan.total_balance - repayment.amount
                repayment.processed_by = request.user
                repayment.save()
                
                # Update loan balances
                loan.principal_balance -= repayment.principal_amount
                loan.interest_balance -= repayment.interest_amount
                loan.total_balance = loan.principal_balance + loan.interest_balance
                
                if loan.total_balance <= 0:
                    loan.status = 'completed'
                
                loan.save()
                
                # Auto-allocate member savings to loan repayment if loan is active
                if loan.status == 'active':
                    allocate_savings_to_loan(loan.member, loan)
                
                # Create transaction entries for repayment
                try:
                    from transactions.models import Transaction, TransactionEntry, Account
                    
                    # Get or create accounts
                    cash_account, created = Account.objects.get_or_create(
                        code='1000',
                        defaults={'name': 'Cash', 'category_id': 1, 'balance': 0}
                    )
                    
                    loan_account, created = Account.objects.get_or_create(
                        code='1200',
                        defaults={'name': 'Loans Receivable', 'category_id': 1, 'balance': 0}
                    )
                    
                    interest_income_account, created = Account.objects.get_or_create(
                        code='4000',
                        defaults={'name': 'Interest Income', 'category_id': 4, 'balance': 0}
                    )
                    
                    # Create repayment transaction
                    repayment_transaction = Transaction.objects.create(
                        transaction_type='income',
                        description=f'Loan repayment for {loan.loan_id}',
                        amount=repayment.amount,
                        created_by=request.user,
                        status='completed'
                    )
                    
                    # Create journal entries
                    TransactionEntry.objects.create(
                        transaction=repayment_transaction,
                        account=cash_account,
                        debit_amount=repayment.amount,
                        credit_amount=0,
                        description=f'Cash received for loan repayment - {loan.loan_id}'
                    )
                    
                    if repayment.principal_amount > 0:
                        TransactionEntry.objects.create(
                            transaction=repayment_transaction,
                            account=loan_account,
                            debit_amount=0,
                            credit_amount=repayment.principal_amount,
                            description=f'Principal repayment - {loan.loan_id}'
                        )
                    
                    if repayment.interest_amount > 0:
                        TransactionEntry.objects.create(
                            transaction=repayment_transaction,
                            account=interest_income_account,
                            debit_amount=0,
                            credit_amount=repayment.interest_amount,
                            description=f'Interest income - {loan.loan_id}'
                        )
                    
                    # Update account balances
                    cash_account.balance += repayment.amount
                    cash_account.save()
                    loan_account.balance -= repayment.principal_amount
                    loan_account.save()
                    interest_income_account.balance += repayment.interest_amount
                    interest_income_account.save()
                    
                except Exception as e:
                    print(f"Error creating repayment transaction entries: {str(e)}")
                
                messages.success(request, f'Repayment of ₦{repayment.amount:,.2f} processed successfully!')
                return redirect('loans:detail', pk=loan.pk)
                
            except Exception as e:
                messages.error(request, f'Error processing repayment: {str(e)}')
    else:
        form = LoanRepaymentForm(user=request.user)
    
    return render(request, 'loans/repayments.html', {'form': form})

@login_required
def active_loans(request):
    """List active loans"""
    # Include both 'active' and 'approved' loans as they are considered active
    loans = Loan.objects.filter(status__in=['active', 'approved']).order_by('-disbursement_date', '-application_date')
    
    # Get statistics
    total_active_loans = loans.count()
    total_disbursed = loans.aggregate(total=Sum('approved_amount'))['total'] or 0
    total_outstanding = loans.aggregate(total=Sum('total_balance'))['total'] or 0
    
    paginator = Paginator(loans, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'loans/active.html', {
        'loans': page_obj,
        'total_active_loans': total_active_loans,
        'total_disbursed': total_disbursed,
        'total_outstanding': total_outstanding,
        'is_paginated': page_obj.has_other_pages()
    })

@login_required
def calculate_loan_ajax(request):
    """AJAX endpoint for loan calculation using new flexible rules"""
    if request.method == 'GET':
        amount = Decimal(request.GET.get('amount', 0))
        product_id = request.GET.get('product_id')
        
        try:
            product = LoanProduct.objects.get(pk=product_id)
            
            # New calculation: 10% interest added immediately
            interest_rate = Decimal('10.00')
            interest_amount = amount * Decimal('0.10')  # 10% of principal
            total_amount = amount + interest_amount
            tenure = 22  # Maximum 22 months
            
            # Get member's monthly deposit for flexible calculation
            member_id = request.GET.get('member_id')
            monthly_deposit = Decimal('0.00')
            if member_id:
                try:
                    from members.models import Member
                    member = Member.objects.get(pk=member_id)
                    monthly_deposit = member.monthly_savings
                except Member.DoesNotExist:
                    pass
            
            # Calculate flexible repayment schedule
            if monthly_deposit > 0:
                # Calculate how many months to pay interest
                interest_months = (interest_amount / monthly_deposit).quantize(Decimal('0.01'), rounding='ROUND_UP')
                # Calculate how many months to pay principal
                principal_months = (amount / monthly_deposit).quantize(Decimal('0.01'), rounding='ROUND_UP')
                total_months = min(interest_months + principal_months, 22)
            else:
                interest_months = 0
                principal_months = 22
                total_months = 22
            
            return JsonResponse({
                'interest_rate': float(interest_rate),
                'interest_amount': float(interest_amount),
                'total_amount': float(total_amount),
                'tenure': tenure,
                'monthly_deposit': float(monthly_deposit),
                'interest_months': float(interest_months),
                'principal_months': float(principal_months),
                'total_months': float(total_months),
                'repayment_schedule': {
                    'interest_months': float(interest_months),
                    'principal_months': float(principal_months),
                    'total_months': float(total_months),
                    'flexible': True
                }
            })
        except LoanProduct.DoesNotExist:
            return JsonResponse({'error': 'Loan product not found'}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def loan_reports(request):
    """Loan reports view"""
    return render(request, 'loans/reports.html')

@login_required
def loan_products(request):
    """Loan products management"""
    products = LoanProduct.objects.all()
    return render(request, 'loans/products.html', {'products': products})

@login_required
def loan_calculator(request):
    """Loan calculator"""
    products = LoanProduct.objects.all()
    return render(request, 'loans/calculator.html', {'products': products})

@login_required
def overdue_loans(request):
    """List overdue loans"""
    loans = Loan.objects.filter(status='active').order_by('-disbursement_date')
    return render(request, 'loans/overdue.html', {'loans': loans})


@login_required
def member_loans(request, member_id):
    """Member's loans"""
    member = get_object_or_404(Member, pk=member_id)
    loans = Loan.objects.filter(member=member).order_by('-created_at')
    return render(request, 'loans/member_loans.html', {
        'member': member,
        'loans': loans
    })

@login_required
def export_detail(request, pk):
    """Export loan detail"""
    loan = get_object_or_404(Loan, pk=pk)
    return render(request, 'loans/export_detail.html', {'loan': loan})

@login_required
def loan_data_ajax(request):
    """AJAX endpoint for loan data"""
    from django.http import JsonResponse
    loan_id = request.GET.get('id')
    if loan_id:
        try:
            loan = Loan.objects.get(pk=loan_id)
            # Get member name safely
            member_name = loan.member.user.get_full_name()
            if not member_name.strip():
                member_name = f"{loan.member.user.first_name} {loan.member.user.last_name}".strip()
            if not member_name.strip():
                member_name = loan.member.user.username
            
            data = {
                'id': loan.pk,
                'loan_id': loan.loan_id,
                'member_name': member_name,
                'requested_amount': float(loan.requested_amount),
                'approved_amount': float(loan.approved_amount) if loan.approved_amount else 0,
                'interest_rate': float(loan.interest_rate) if loan.interest_rate else 0,
                'tenure_months': loan.tenure_months,
                'status': loan.status,
            }
            return JsonResponse(data)
        except Loan.DoesNotExist:
            return JsonResponse({'error': 'Loan not found'}, status=404)
    return JsonResponse({'error': 'No loan ID provided'}, status=400)

@login_required
def disbursement_receipt(request):
    """Generate disbursement receipt"""
    from django.http import JsonResponse
    loan_id = request.GET.get('id')
    if loan_id:
        try:
            loan = Loan.objects.get(pk=loan_id)
            # Generate receipt data
            receipt_data = {
                'loan_id': loan.loan_id,
                'member_name': loan.member.user.get_full_name(),
                'member_id': loan.member.member_id,
                'disbursed_amount': float(loan.approved_amount) if loan.approved_amount else 0,
                'disbursement_date': loan.disbursement_date.strftime('%Y-%m-%d') if loan.disbursement_date else None,
                'interest_rate': float(loan.interest_rate) if loan.interest_rate else 0,
                'tenure_months': loan.tenure_months,
                'status': loan.status,
            }
            return JsonResponse(receipt_data)
        except Loan.DoesNotExist:
            return JsonResponse({'error': 'Loan not found'}, status=404)
    return JsonResponse({'error': 'No loan ID provided'}, status=400)

@login_required
def bulk_disburse(request):
    """Handle bulk disbursement"""
    from django.http import JsonResponse
    if request.method == 'POST':
        try:
            # Handle bulk disbursement logic here
            # For now, return a simple response
            return JsonResponse({'status': 'success', 'message': 'Bulk disbursement processed'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
