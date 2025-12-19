from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .forms import (
    FinancialReportForm, MembershipReportForm, SavingsReportForm,
    LoanReportForm, CustomReportForm, ReportScheduleForm,
    AuditReportForm, PerformanceMetricsForm
)
from members.models import Member, MembershipType
from savings.models import SavingsAccount, SavingsTransaction, SavingsProduct
from loans.models import Loan, LoanProduct, LoanRepayment
from transactions.models import Account, AccountCategory, Transaction, CashFlow
from decimal import Decimal
import json
from datetime import date, timedelta, datetime
from io import BytesIO
import xlsxwriter

@login_required
def dashboard(request):
    """Comprehensive Reports Dashboard with Integrity Tracking"""
    from decimal import Decimal
    
    # Get date range for current period
    today = timezone.now().date()
    current_month = today.replace(day=1)
    current_year = today.replace(month=1, day=1)
    
    # Use unified financial calculations from transactions/views
    from transactions.views import calculate_balance_sheet_data
    from datetime import datetime
    
    # Get current year data for consistency
    start_date = timezone.make_aware(datetime(2025, 1, 1))
    end_date = timezone.make_aware(datetime(2025, 12, 31, 23, 59, 59))
    financial_data = calculate_balance_sheet_data(start_date, end_date, 'Year 2025')
    
    # Comprehensive Financial Overview - use unified calculations
    total_members = financial_data['total_members']
    total_savings = financial_data['total_member_savings']
    total_loans_outstanding = financial_data['outstanding_loans']
    total_disbursed = financial_data['active_loans']
    
    # Income Sources (Money In) - use unified calculations
    registration_fees = financial_data['registration_fees_earned']
    loan_interest_earned = financial_data['loan_interest_earned']
    other_income = financial_data['other_income']
    
    total_income = financial_data['total_revenue']
    
    # Expenses (Money Out) - use unified calculations
    loan_disbursements = total_disbursed
    operational_expenses = financial_data['total_expenses_amount']
    
    total_expenses = financial_data['total_expenses_amount']
    
    # Net Position - use unified calculation
    net_position = financial_data['net_profit']
    
    # Available Cash - use unified calculation
    available_cash = financial_data['available_balance']
    
    # Monthly Activity - use regular members only
    current_month_dt = timezone.make_aware(datetime.combine(current_month, datetime.min.time()))
    
    monthly_savings = SavingsTransaction.objects.filter(
        transaction_date__gte=current_month_dt,
        transaction_type='deposit',
        savings_account__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    monthly_loans = Loan.objects.filter(
        disbursement_date__gte=current_month_dt,
        member__in=Member.regular_members()
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    monthly_transactions = Transaction.objects.filter(
        created_at__date__gte=current_month,
        member__in=Member.regular_members()
    ).count()
    
    # Integrity Checks
    savings_vs_loans_ratio = (total_savings / total_disbursed * 100) if total_disbursed > 0 else 0
    income_vs_expenses_ratio = (total_income / total_expenses * 100) if total_expenses > 0 else 0
    
    # Recent Activity for Transparency - use regular members only
    recent_transactions = Transaction.objects.filter(
        status='completed',
        member__in=Member.regular_members()
    ).order_by('-created_at')[:10]
    
    recent_loans = Loan.objects.filter(
        status__in=['approved', 'active'],
        member__in=Member.regular_members()
    ).order_by('-application_date')[:5]
    
    # Transaction History for Transparency - use regular members only
    transaction_history = Transaction.objects.filter(
        status='completed',
        member__in=Member.regular_members()
    ).select_related('created_by').order_by('-created_at')[:20]
    
    # Loan Disbursement History - use regular members only
    loan_disbursements_history = Loan.objects.filter(
        status__in=['active', 'completed'],
        disbursement_date__isnull=False,
        member__in=Member.regular_members()
    ).select_related('member__user', 'disbursed_by').order_by('-disbursement_date')[:10]
    
    context = {
        'total_members': total_members,
        'total_savings': total_savings,
        'total_loans_outstanding': total_loans_outstanding,
        'total_disbursed': total_disbursed,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_position': net_position,
        'available_cash': available_cash,
        'registration_fees': registration_fees,
        'loan_interest_earned': loan_interest_earned,
        'other_income': other_income,
        'loan_disbursements': loan_disbursements,
        'operational_expenses': operational_expenses,
        'monthly_savings': monthly_savings,
        'monthly_loans': monthly_loans,
        'monthly_transactions': monthly_transactions,
        'savings_vs_loans_ratio': savings_vs_loans_ratio,
        'income_vs_expenses_ratio': income_vs_expenses_ratio,
        'recent_transactions': recent_transactions,
        'recent_loans': recent_loans,
        'transaction_history': transaction_history,
        'loan_disbursements_history': loan_disbursements_history,
    }
    return render(request, 'reports/dashboard.html', context)

@login_required
def financial_reports(request):
    """Generate financial reports"""
    if request.method == 'POST':
        form = FinancialReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            format_type = form.cleaned_data['format']
            
            # Generate report data based on type
            if report_type == 'balance_sheet':
                report_data = generate_balance_sheet(start_date, end_date)
            elif report_type == 'income_statement':
                report_data = generate_income_statement(start_date, end_date)
            elif report_type == 'cash_flow':
                report_data = generate_cash_flow_statement(start_date, end_date)
            elif report_type == 'trial_balance':
                report_data = generate_trial_balance(start_date, end_date)
            else:
                report_data = generate_general_ledger(start_date, end_date)
            
            if format_type == 'pdf':
                return generate_pdf_report(report_data, report_type)
            elif format_type == 'excel':
                return generate_excel_report(report_data, report_type)
            else:
                return render(request, 'reports/financial_report.html', {
                    'report_data': report_data,
                    'report_type': report_type,
                    'period': f'{start_date} to {end_date}'
                })
    else:
        form = FinancialReportForm()
    
    return render(request, 'reports/financial_reports.html', {'form': form})

@login_required
def membership_reports(request):
    """Generate membership reports"""
    if request.method == 'POST':
        form = MembershipReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            membership_type = form.cleaned_data.get('membership_type')
            membership_status = form.cleaned_data.get('membership_status')
            format_type = form.cleaned_data['format']
            
            # Filter members based on criteria - use regular members only
            members = Member.regular_members()
            if membership_type:
                members = members.filter(membership_type=membership_type)
            if membership_status:
                members = members.filter(membership_status=membership_status)
            
            report_data = {
                'members': members,
                'total_count': members.count(),
                'report_type': report_type
            }
            
            if format_type == 'pdf':
                return generate_pdf_report(report_data, report_type)
            elif format_type == 'excel':
                return generate_excel_report(report_data, report_type)
            else:
                return render(request, 'reports/membership_report.html', {
                    'report_data': report_data
                })
    else:
        form = MembershipReportForm()
    
    return render(request, 'reports/membership_reports.html', {'form': form})

@login_required
def savings_reports(request):
    """Generate savings reports"""
    if request.method == 'POST':
        form = SavingsReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            savings_product = form.cleaned_data.get('savings_product')
            member = form.cleaned_data.get('member')
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            format_type = form.cleaned_data['format']
            
            # Generate savings report data
            savings_accounts = SavingsAccount.objects.all()
            if savings_product:
                savings_accounts = savings_accounts.filter(product=savings_product)
            if member:
                savings_accounts = savings_accounts.filter(member=member)
            
            transactions = SavingsTransaction.objects.filter(
                transaction_date__range=[start_date, end_date]
            )
            
            report_data = {
                'savings_accounts': savings_accounts,
                'transactions': transactions,
                'total_balance': savings_accounts.aggregate(total=Sum('balance'))['total'] or 0,
                'period': f'{start_date} to {end_date}',
                'report_type': report_type
            }
            
            if format_type == 'pdf':
                return generate_pdf_report(report_data, report_type)
            elif format_type == 'excel':
                return generate_excel_report(report_data, report_type)
            else:
                return render(request, 'reports/savings_report.html', {
                    'report_data': report_data
                })
    else:
        form = SavingsReportForm()
    
    return render(request, 'reports/savings_reports.html', {'form': form})

@login_required
def loan_reports(request):
    """Generate loan reports"""
    if request.method == 'POST':
        form = LoanReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            loan_product = form.cleaned_data.get('loan_product')
            member = form.cleaned_data.get('member')
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            format_type = form.cleaned_data['format']
            
            # Generate loan report data
            loans = Loan.objects.filter(
                created_at__range=[start_date, end_date]
            )
            if loan_product:
                loans = loans.filter(loan_product=loan_product)
            if member:
                loans = loans.filter(member=member)
            
            report_data = {
                'loans': loans,
                'total_disbursed': loans.filter(status__in=['active', 'completed']).aggregate(
                    total=Sum('approved_amount')
                )['total'] or 0,
                'total_outstanding': loans.filter(status='active').aggregate(
                    total=Sum('total_balance')
                )['total'] or 0,
                'period': f'{start_date} to {end_date}',
                'report_type': report_type
            }
            
            if format_type == 'pdf':
                return generate_pdf_report(report_data, report_type)
            elif format_type == 'excel':
                return generate_excel_report(report_data, report_type)
            else:
                return render(request, 'reports/loan_report.html', {
                    'report_data': report_data
                })
    else:
        form = LoanReportForm()
    
    return render(request, 'reports/loan_reports.html', {'form': form})

@login_required
def custom_reports(request):
    """Generate custom reports"""
    if request.method == 'POST':
        form = CustomReportForm(request.POST)
        if form.is_valid():
            # Process custom report generation
            messages.success(request, 'Custom report generated successfully!')
            return render(request, 'reports/custom_report_result.html', {
                'form_data': form.cleaned_data
            })
    else:
        form = CustomReportForm()
    
    return render(request, 'reports/custom_reports.html', {'form': form})

@login_required
def audit_reports(request):
    """Generate audit reports"""
    if request.method == 'POST':
        form = AuditReportForm(request.POST)
        if form.is_valid():
            # Generate audit report
            audit_type = form.cleaned_data['audit_type']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            
            report_data = {
                'audit_type': audit_type,
                'period': f'{start_date} to {end_date}',
                'transactions': Transaction.objects.filter(
                    created_at__range=[start_date, end_date]
                ).order_by('-created_at')
            }
            
            return render(request, 'reports/audit_report.html', {
                'report_data': report_data
            })
    else:
        form = AuditReportForm()
    
    return render(request, 'reports/audit_reports.html', {'form': form})

@login_required
def performance_metrics(request):
    """Generate performance metrics"""
    if request.method == 'POST':
        form = PerformanceMetricsForm(request.POST)
        if form.is_valid():
            # Calculate performance metrics
            metric_type = form.cleaned_data['metric_type']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            
            metrics_data = calculate_performance_metrics(metric_type, start_date, end_date)
            
            return render(request, 'reports/performance_metrics_result.html', {
                'metrics_data': metrics_data,
                'metric_type': metric_type,
                'period': f'{start_date} to {end_date}'
            })
    else:
        form = PerformanceMetricsForm()
    
    return render(request, 'reports/performance_metrics.html', {'form': form})

@login_required
def balance_sheet(request):
    """Generate balance sheet with date filtering"""
    # Get date filter from request
    as_of_date = request.GET.get('as_of_date', timezone.now().date())
    if isinstance(as_of_date, str):
        from datetime import datetime
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
    
    include_pending = request.GET.get('include_pending', False)
    
    # Get current balances for all account types
    assets = Account.objects.filter(category__category_type='asset', is_active=True)
    liabilities = Account.objects.filter(category__category_type='liability', is_active=True)
    equity = Account.objects.filter(category__category_type='equity', is_active=True)
    
    # Calculate totals
    total_assets = sum(account.balance for account in assets)
    total_liabilities = sum(account.balance for account in liabilities)
    total_equity = sum(account.balance for account in equity)
    
    # Add member savings as assets
    total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or 0
    
    # Add loan portfolio as assets (outstanding loans)
    total_loans_outstanding = Loan.objects.filter(
        status__in=['active', 'approved']
    ).aggregate(total=Sum('total_balance'))['total'] or 0
    
    # Add cash and bank balances
    cash_accounts = Account.objects.filter(
        category__category_type='asset',
        name__icontains='cash'
    ).aggregate(total=Sum('balance'))['total'] or 0
    
    bank_accounts = Account.objects.filter(
        category__category_type='asset',
        name__icontains='bank'
    ).aggregate(total=Sum('balance'))['total'] or 0
    
    # Calculate total assets including member savings and loans
    total_assets_with_savings = total_assets + total_savings + total_loans_outstanding
    
    # Calculate member equity (savings - loans)
    member_equity = total_savings - total_loans_outstanding
    
    # Add pending transactions if requested
    pending_amount = 0
    if include_pending:
        pending_transactions = Transaction.objects.filter(
            status='pending',
            created_at__date__lte=as_of_date
        ).aggregate(total=Sum('amount'))['total'] or 0
        pending_amount = pending_transactions
    
    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'total_savings': total_savings,
        'total_loans_outstanding': total_loans_outstanding,
        'total_assets_with_savings': total_assets_with_savings,
        'member_equity': member_equity,
        'cash_accounts': cash_accounts,
        'bank_accounts': bank_accounts,
        'pending_amount': pending_amount,
        'as_of_date': as_of_date,
        'include_pending': include_pending,
    }
    return render(request, 'reports/balance_sheet.html', context)

@login_required
def monthly_reports(request):
    """Monthly reports with month filtering"""
    # Get month filter from request
    selected_month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    if selected_month:
        year, month = map(int, selected_month.split('-'))
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    else:
        start_date = timezone.now().date().replace(day=1)
        end_date = timezone.now().date()
    
    # Calculate monthly statistics - use UTC timezone for consistency
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), timezone.utc)
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), timezone.utc)
    
    monthly_savings_deposits = SavingsTransaction.objects.filter(
        transaction_type__in=['voluntary', 'collateral'],
        transaction_date__range=[start_datetime, end_datetime],
        savings_account__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_savings_withdrawals = SavingsTransaction.objects.filter(
        transaction_type='withdrawal',
        transaction_date__range=[start_datetime, end_datetime],
        savings_account__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_loan_disbursements = Loan.objects.filter(
        disbursement_date__range=[start_datetime, end_datetime],
        member__in=Member.regular_members()
    ).aggregate(total=Sum('approved_amount'))['total'] or 0
    
    monthly_loan_repayments = LoanRepayment.objects.filter(
        payment_date__range=[start_datetime, end_datetime],
        loan__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_transactions = Transaction.objects.filter(
        transaction_date__date__range=[start_date, end_date]
    ).count()
    
    # Member statistics
    new_members = Member.regular_members().filter(
        date_joined__range=[start_date, end_date]
    ).count()
    
    active_members = Member.regular_members().filter(
        membership_status='active'
    ).count()
    
    # Daily breakdown for the month
    daily_breakdown = []
    current_date = start_date
    while current_date <= end_date:
        # Use UTC timezone for consistent filtering
        day_start_dt = timezone.make_aware(datetime.combine(current_date, datetime.min.time()), timezone.utc)
        day_end_dt = timezone.make_aware(datetime.combine(current_date, datetime.max.time()), timezone.utc)
        
        # Get all savings deposits (voluntary, collateral only - compulsory are not deposits)
        day_deposits = SavingsTransaction.objects.filter(
            transaction_type__in=['voluntary', 'collateral'],
            transaction_date__range=[day_start_dt, day_end_dt],
            savings_account__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        day_withdrawals = SavingsTransaction.objects.filter(
            transaction_type='withdrawal',
            transaction_date__range=[day_start_dt, day_end_dt],
            savings_account__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        day_loans = Loan.objects.filter(
            disbursement_date__range=[day_start_dt, day_end_dt],
            member__in=Member.regular_members()
        ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
        
        day_repayments = LoanRepayment.objects.filter(
            payment_date__range=[day_start_dt, day_end_dt],
            loan__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        daily_breakdown.append({
            'date': current_date,
            'deposits': day_deposits,
            'withdrawals': day_withdrawals,
            'net_savings': day_deposits - day_withdrawals,
            'loans': day_loans,
            'repayments': day_repayments,
        })
        
        current_date += timedelta(days=1)
    
    # Generate available years (current year and 5 years back)
    current_year = timezone.now().year
    available_years = list(range(current_year - 5, current_year + 1))
    context = {
        'selected_month': selected_month,
        'selected_year': year,
        'selected_month_obj': start_date,
        'start_date': start_date,
        'end_date': end_date,
        'monthly_savings_deposits': monthly_savings_deposits,
        'monthly_savings_withdrawals': monthly_savings_withdrawals,
        'monthly_loan_disbursements': monthly_loan_disbursements,
        'monthly_loan_repayments': monthly_loan_repayments,
        'monthly_transactions': monthly_transactions,
        'new_members': new_members,
        'active_members': active_members,
        'daily_breakdown': daily_breakdown,
        'available_years': available_years,
    }
    return render(request, 'reports/monthly.html', context)

@login_required
def annual_reports(request):
    """Annual reports with year filtering"""
    # Get year filter from request
    selected_year = request.GET.get('year', timezone.now().year)
    if selected_year:
        selected_year = int(selected_year)
        start_date = date(selected_year, 1, 1)
        end_date = date(selected_year, 12, 31)
    else:
        selected_year = timezone.now().year
        start_date = date(selected_year, 1, 1)
        end_date = date(selected_year, 12, 31)
    
    # Calculate annual statistics - use UTC timezone for consistency
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), timezone.utc)
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), timezone.utc)
    
    annual_savings_deposits = SavingsTransaction.objects.filter(
        transaction_type__in=['voluntary', 'collateral'],
        transaction_date__range=[start_datetime, end_datetime],
        savings_account__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    annual_savings_withdrawals = SavingsTransaction.objects.filter(
        transaction_type='withdrawal',
        transaction_date__range=[start_datetime, end_datetime],
        savings_account__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    annual_loan_disbursements = Loan.objects.filter(
        disbursement_date__range=[start_datetime, end_datetime],
        member__in=Member.regular_members()
    ).aggregate(total=Sum('approved_amount'))['total'] or 0
    
    annual_loan_repayments = LoanRepayment.objects.filter(
        payment_date__range=[start_datetime, end_datetime],
        loan__member__in=Member.regular_members()
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    annual_transactions = Transaction.objects.filter(
        transaction_date__date__range=[start_date, end_date]
    ).count()
    
    # Member statistics
    new_members_annual = Member.regular_members().filter(
        date_joined__range=[start_date, end_date]
    ).count()
    
    total_members = Member.regular_members().count()
    
    # Monthly breakdown for the year
    monthly_breakdown = []
    for month in range(1, 13):
        month_start = date(selected_year, month, 1)
        if month == 12:
            month_end = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        # Use UTC timezone for consistent filtering
        month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()), timezone.utc)
        month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()), timezone.utc)
        
        # Get comprehensive monthly data (voluntary, collateral only - compulsory are not deposits)
        month_deposits = SavingsTransaction.objects.filter(
            transaction_type__in=['voluntary', 'collateral'],
            transaction_date__range=[month_start_dt, month_end_dt],
            savings_account__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        month_withdrawals = SavingsTransaction.objects.filter(
            transaction_type='withdrawal',
            transaction_date__range=[month_start_dt, month_end_dt],
            savings_account__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        month_loans = Loan.objects.filter(
            disbursement_date__range=[month_start_dt, month_end_dt],
            member__in=Member.regular_members()
        ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0.00')
        
        month_repayments = LoanRepayment.objects.filter(
            payment_date__range=[month_start_dt, month_end_dt],
            loan__member__in=Member.regular_members()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        monthly_breakdown.append({
            'month': month,
            'month_name': month_start.strftime('%B'),
            'deposits': month_deposits,
            'withdrawals': month_withdrawals,
            'net_savings': month_deposits - month_withdrawals,
            'loans': month_loans,
            'repayments': month_repayments,
        })
    
    # Generate available years (current year and 5 years back)
    current_year = timezone.now().year
    available_years = list(range(current_year - 5, current_year + 1))
    
    context = {
        'selected_year': selected_year,
        'start_date': start_date,
        'end_date': end_date,
        'annual_savings_deposits': annual_savings_deposits,
        'annual_savings_withdrawals': annual_savings_withdrawals,
        'annual_loan_disbursements': annual_loan_disbursements,
        'annual_loan_repayments': annual_loan_repayments,
        'annual_transactions': annual_transactions,
        'new_members_annual': new_members_annual,
        'total_members': total_members,
        'monthly_breakdown': monthly_breakdown,
        'available_years': available_years,
    }
    return render(request, 'reports/annual.html', context)

@login_required
def export_data(request):
    """Export data"""
    return render(request, 'reports/export.html')

# Helper functions for report generation
def generate_balance_sheet(start_date, end_date):
    """Generate balance sheet data"""
    return {
        'assets': Account.objects.filter(category__category_type='asset', is_active=True),
        'liabilities': Account.objects.filter(category__category_type='liability', is_active=True),
        'equity': Account.objects.filter(category__category_type='equity', is_active=True),
    }

def generate_income_statement(start_date, end_date):
    """Generate income statement data"""
    return {
        'income': Account.objects.filter(category__category_type='income', is_active=True),
        'expenses': Account.objects.filter(category__category_type='expense', is_active=True),
    }

def generate_cash_flow_statement(start_date, end_date):
    """Generate cash flow statement data"""
    cash_flows = CashFlow.objects.filter(
        date__range=[start_date, end_date]
    )
    return {
        'operating_activities': cash_flows.filter(flow_type='inflow'),
        'investing_activities': cash_flows.filter(flow_type='outflow'),
        'financing_activities': cash_flows.filter(flow_type='inflow'),
    }

def generate_trial_balance(start_date, end_date):
    """Generate trial balance data"""
    accounts = Account.objects.filter(is_active=True).order_by('code')
    return {'accounts': accounts}

def generate_general_ledger(start_date, end_date):
    """Generate general ledger data"""
    accounts = Account.objects.filter(is_active=True).order_by('code')
    return {'accounts': accounts}

def calculate_performance_metrics(metric_type, start_date, end_date):
    """Calculate performance metrics"""
    if metric_type == 'financial_health':
        return {
            'total_assets': Account.objects.filter(category__category_type='asset').aggregate(
                total=Sum('balance')
            )['total'] or 0,
            'total_liabilities': Account.objects.filter(category__category_type='liability').aggregate(
                total=Sum('balance')
            )['total'] or 0,
            'loan_portfolio_size': Loan.objects.filter(status='active').aggregate(
                total=Sum('total_balance')
            )['total'] or 0,
        }
    elif metric_type == 'member_engagement':
        return {
            'active_members': Member.regular_members().filter(membership_status='active').count(),
            'new_members': Member.regular_members().filter(
                date_joined__range=[start_date, end_date]
            ).count(),
            'savings_participation': SavingsAccount.objects.filter(
                balance__gt=0
            ).count(),
        }
    else:
        return {}

def generate_pdf_report(report_data, report_type):
    """Generate PDF report"""
    # This would use a PDF library like ReportLab
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
    
    # TODO: Implement PDF generation
    response.write(b'PDF generation not yet implemented')
    return response

def generate_excel_report(report_data, report_type):
    """Generate Excel report"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet(report_type.title())
    
    # TODO: Implement Excel generation based on report type
    worksheet.write(0, 0, f'{report_type.title()} Report')
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xlsx"'
    return response

@login_required
def process_export(request):
    """Process export request"""
    if request.method == 'POST':
        export_type = request.POST.get('export_type')
        format_type = request.POST.get('format')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        # TODO: Implement actual export processing
        # For now, return success response
        return JsonResponse({'success': True, 'message': 'Export queued successfully'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def preview_export(request):
    """Preview export data"""
    export_type = request.GET.get('type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # TODO: Generate preview data based on export type
    preview_data = {'message': 'Preview functionality coming soon'}
    
    return render(request, 'reports/preview.html', {
        'preview_data': preview_data,
        'export_type': export_type
    })

@login_required
def get_template(request):
    """Get export template configuration"""
    template_id = request.GET.get('id')
    
    # TODO: Implement template retrieval
    return JsonResponse({
        'success': True,
        'template': {
            'type': 'member_list',
            'format': 'excel'
        }
    })

@login_required
def edit_template(request):
    """Edit export template"""
    template_id = request.GET.get('id')
    
    # TODO: Implement template editing
    return render(request, 'reports/edit_template.html', {
        'template_id': template_id
    })

@login_required
def retry_export(request):
    """Retry failed export"""
    if request.method == 'POST':
        # TODO: Implement export retry logic
        return JsonResponse({'success': True, 'message': 'Export retry initiated'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def delete_export(request):
    """Delete export entry"""
    if request.method == 'POST':
        # TODO: Implement export deletion logic
        return JsonResponse({'success': True, 'message': 'Export deleted'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def export_status(request):
    """Check export status for updates"""
    # TODO: Implement status checking logic
    return JsonResponse({'has_updates': False})

@login_required
def member_report(request, member_id):
    """Generate comprehensive report for a single member"""
    from members.models import Member
    from savings.models import SavingsAccount, SavingsTransaction
    from loans.models import Loan, LoanRepayment
    from transactions.models import Transaction
    from django.db.models import Sum
    
    member = get_object_or_404(Member, pk=member_id)
    
    # Get all member data
    try:
        savings_account = SavingsAccount.objects.get(member=member)
        savings_transactions = SavingsTransaction.objects.filter(
            savings_account=savings_account
        ).order_by('-transaction_date')
        current_savings_balance = savings_account.balance
    except SavingsAccount.DoesNotExist:
        savings_account = None
        savings_transactions = []
        current_savings_balance = 0
    
    # Get loan information
    member_loans = Loan.objects.filter(member=member).order_by('-application_date')
    loan_repayments = LoanRepayment.objects.filter(
        loan__member=member
    ).order_by('-payment_date')
    
    # Calculate loan statistics
    total_loans_disbursed = member_loans.filter(
        status__in=['active', 'completed']
    ).aggregate(total=Sum('approved_amount'))['total'] or 0
    
    current_loan_balance = member_loans.filter(
        status='active'
    ).aggregate(total=Sum('total_balance'))['total'] or 0
    
    total_repayments = loan_repayments.aggregate(total=Sum('amount'))['total'] or 0
    total_interest_paid = loan_repayments.aggregate(total=Sum('interest_amount'))['total'] or 0
    
    # Get general transactions
    general_transactions = Transaction.objects.filter(
        member=member
    ).order_by('-transaction_date')
    
    context = {
        'member': member,
        'savings_account': savings_account,
        'savings_transactions': savings_transactions,
        'current_savings_balance': current_savings_balance,
        'member_loans': member_loans,
        'loan_repayments': loan_repayments,
        'total_loans_disbursed': total_loans_disbursed,
        'current_loan_balance': current_loan_balance,
        'total_repayments': total_repayments,
        'total_interest_paid': total_interest_paid,
        'general_transactions': general_transactions,
        'report_date': timezone.now().date(),
    }
    
    return render(request, 'reports/member_report.html', context)

@login_required
def all_members_excel(request):
    """Export all members data to Excel"""
    from members.models import Member
    from savings.models import SavingsAccount
    from loans.models import Loan
    from django.db.models import Sum
    import xlsxwriter
    from io import BytesIO
    
    # Create Excel file in memory
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('All Members Report')
    
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#366092',
        'font_color': 'white',
        'border': 1
    })
    
    currency_format = workbook.add_format({'num_format': '₦#,##0.00'})
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
    
    # Headers
    headers = [
        'Member ID', 'Full Name', 'Email', 'Phone', 'Status',
        'Date Joined', 'Savings Balance', 'Total Loans Disbursed',
        'Current Loan Balance', 'Total Repayments', 'Total Interest Paid'
    ]
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # Get all members with their data
    members = Member.regular_members().select_related('user')
    
    row = 1
    for member in members:
        # Get savings balance
        try:
            savings_account = SavingsAccount.objects.get(member=member)
            savings_balance = savings_account.balance
        except SavingsAccount.DoesNotExist:
            savings_balance = 0
        
        # Get loan statistics
        member_loans = Loan.objects.filter(member=member)
        total_loans_disbursed = member_loans.filter(
            status__in=['active', 'completed']
        ).aggregate(total=Sum('approved_amount'))['total'] or 0
        
        current_loan_balance = member_loans.filter(
            status='active'
        ).aggregate(total=Sum('total_balance'))['total'] or 0
        
        total_repayments = LoanRepayment.objects.filter(
            loan__member=member
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_interest_paid = LoanRepayment.objects.filter(
            loan__member=member
        ).aggregate(total=Sum('interest_amount'))['total'] or 0
        
        # Write member data
        worksheet.write(row, 0, member.member_id)
        worksheet.write(row, 1, member.user.get_full_name())
        worksheet.write(row, 2, member.user.email)
        worksheet.write(row, 3, member.emergency_contact_phone)
        worksheet.write(row, 4, member.get_membership_status_display())
        worksheet.write(row, 5, member.date_joined, date_format)
        worksheet.write(row, 6, savings_balance, currency_format)
        worksheet.write(row, 7, total_loans_disbursed, currency_format)
        worksheet.write(row, 8, current_loan_balance, currency_format)
        worksheet.write(row, 9, total_repayments, currency_format)
        worksheet.write(row, 10, total_interest_paid, currency_format)
        
        row += 1
    
    # Auto-fit columns
    for col in range(len(headers)):
        worksheet.set_column(col, col, 15)
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="all_members_report.xlsx"'
    return response

@login_required
def transaction_history(request):
    """Comprehensive transaction history with transparency"""
    from decimal import Decimal
    
    # Get filter parameters
    transaction_type = request.GET.get('type', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Base queryset
    transactions = Transaction.objects.filter(status='completed').select_related('created_by')
    
    # Apply filters
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    if start_date:
        transactions = transactions.filter(created_at__date__gte=start_date)
    
    if end_date:
        transactions = transactions.filter(created_at__date__lte=end_date)
    
    # Order by most recent
    transactions = transactions.order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    transaction_count = transactions.count()
    
    # Transaction type breakdown
    type_breakdown = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')
    
    context = {
        'page_obj': page_obj,
        'transactions': page_obj,
        'total_amount': total_amount,
        'transaction_count': transaction_count,
        'type_breakdown': type_breakdown,
        'transaction_type': transaction_type,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'reports/transaction_history.html', context)

@login_required
def unified_reports(request):
    """Unified comprehensive reports page"""
    from django.db.models import Q, Count
    from decimal import Decimal
    
    # Get current date info
    now = timezone.now()
    current_month = now.date().replace(day=1)
    current_year = now.year
    
    # Date filtering
    selected_month = request.GET.get('month', current_month.month)
    selected_year = request.GET.get('year', current_year)
    
    try:
        selected_month = int(selected_month)
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_month = current_month.month
        selected_year = current_year
    
    # Calculate date ranges
    month_start = date(selected_year, selected_month, 1)
    if selected_month == 12:
        month_end = date(selected_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(selected_year, selected_month + 1, 1) - timedelta(days=1)
    
    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year, 12, 31)
    
    # Convert to timezone-aware datetimes
    month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
    month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
    year_start_dt = timezone.make_aware(datetime.combine(year_start, datetime.min.time()))
    year_end_dt = timezone.make_aware(datetime.combine(year_end, datetime.max.time()))
    
    # === FINANCIAL OVERVIEW ===
    # Total member savings (from savings accounts)
    total_savings = SavingsAccount.objects.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0')
    
    # Total outstanding loans (money owed to cooperative)
    total_outstanding_loans = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('total_balance'))['total'] or Decimal('0')
    
    # Total disbursed loans (money given out)
    total_disbursed_loans = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    # Total loan interest earned (from repayments)
    total_interest_earned = LoanRepayment.objects.aggregate(
        total=Sum('interest_amount')
    )['total'] or Decimal('0')
    
    # Registration fees collected
    total_registration_fees = Member.regular_members().aggregate(
        total=Sum('registration_fee_amount')
    )['total'] or Decimal('0')
    
    # Other income from transactions
    other_income = Transaction.objects.filter(
        transaction_type='income'
    ).exclude(description__icontains='registration').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    # Calculate total expenses from transactions
    total_expenses = Transaction.objects.filter(
        transaction_type='expense',
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # TOTAL COOPERATIVE BALANCE = All money the cooperative has
    # Expenses reduce the cooperative balance
    total_cooperative_balance = (
        total_savings + 
        total_outstanding_loans + 
        total_interest_earned + 
        total_registration_fees + 
        other_income -
        total_expenses  # Subtract expenses from balance
    )
    
    # AVAILABLE BALANCE = Money available for new loans (savings - disbursed loans)
    available_balance = total_savings - total_disbursed_loans
    
    # === MONTHLY STATISTICS ===
    monthly_savings = SavingsTransaction.objects.filter(
        transaction_type='deposit',
        transaction_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    monthly_loans = Loan.objects.filter(
        disbursement_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    monthly_repayments = LoanRepayment.objects.filter(
        payment_date__range=[month_start_dt, month_end_dt]
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # === MEMBER STATISTICS ===
    total_members = Member.regular_members().count()
    active_members = Member.regular_members().filter(membership_status='active').count()
    new_members_month = Member.regular_members().filter(
        date_joined__range=[month_start_dt, month_end_dt]
    ).count()
    
    # === LOAN STATISTICS ===
    total_loans = Loan.objects.count()
    active_loans = Loan.objects.filter(status='active').count()
    pending_loans = Loan.objects.filter(status='pending').count()
    approved_loans = Loan.objects.filter(status='approved').count()
    overdue_loans = Loan.objects.filter(
        status='active',
        expected_completion_date__lt=now.date()
    ).count()
    
    # === SAVINGS STATISTICS ===
    total_savings_accounts = SavingsAccount.objects.count()
    active_savings_accounts = SavingsAccount.objects.filter(status='active').count()
    
    # === RECENT ACTIVITY ===
    recent_transactions = Transaction.objects.select_related(
        'member', 'created_by'
    ).order_by('-created_at')[:10]
    
    recent_loans = Loan.objects.select_related('member').order_by('-created_at')[:5]
    recent_savings = SavingsTransaction.objects.select_related(
        'account__member'
    ).order_by('-transaction_date')[:5]
    
    # Loan repayment analysis
    total_loan_repayments = LoanRepayment.objects.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Automatic repayments from savings
    automatic_repayments = SavingsTransaction.objects.filter(
        is_loan_repayment=True
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Members with active loans
    members_with_loans = Member.regular_members().filter(
        loans__status='active'
    ).distinct().count()
    
    # Collateral amounts held
    total_collateral = SavingsAccount.objects.filter(
        has_active_loan=True
    ).aggregate(
        total=Sum('collateral_amount')
    )['total'] or Decimal('0.00')
    
    # === BALANCE SHEET DATA ===
    # Assets
    cash_accounts = Account.objects.filter(
        category__name__icontains='asset',
        code__startswith='1'
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0')
    
    loan_receivables = Account.objects.filter(
        code='1200'
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0')
    
    total_assets = cash_accounts + loan_receivables + total_savings
    
    # Liabilities
    total_liabilities = Decimal('0')  # No liabilities in current setup
    
    # Equity
    member_equity = total_assets - total_liabilities
    
    # === MONTHLY BREAKDOWN FOR CHART ===
    monthly_breakdown = []
    for month in range(1, 13):
        month_start_chart = date(selected_year, month, 1)
        if month == 12:
            month_end_chart = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_chart = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        month_start_dt_chart = timezone.make_aware(datetime.combine(month_start_chart, datetime.min.time()))
        month_end_dt_chart = timezone.make_aware(datetime.combine(month_end_chart, datetime.max.time()))
        
        month_savings = SavingsTransaction.objects.filter(
            transaction_type='deposit',
            transaction_date__range=[month_start_dt_chart, month_end_dt_chart]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        month_loans = Loan.objects.filter(
            disbursement_date__range=[month_start_dt_chart, month_end_dt_chart]
        ).aggregate(total=Sum('approved_amount'))['total'] or 0
        
        monthly_breakdown.append({
            'month': month,
            'month_name': month_start_chart.strftime('%b'),
            'savings': float(month_savings),
            'loans': float(month_loans)
        })
    
    context = {
        # Financial Overview
        'total_cooperative_balance': total_cooperative_balance,
        'available_balance': available_balance,
        'total_savings': total_savings,
        'total_outstanding_loans': total_outstanding_loans,
        'total_disbursed_loans': total_disbursed_loans,
        'total_interest_earned': total_interest_earned,
        'total_registration_fees': total_registration_fees,
        'other_income': other_income,
        
        # Monthly Statistics
        'monthly_savings': monthly_savings,
        'monthly_loans': monthly_loans,
        'monthly_repayments': monthly_repayments,
        
        # Member Statistics
        'total_members': total_members,
        'active_members': active_members,
        'new_members_month': new_members_month,
        
        # Loan Statistics
        'total_loans': total_loans,
        'active_loans': active_loans,
        'pending_loans': pending_loans,
        'approved_loans': approved_loans,
        'overdue_loans': overdue_loans,
        
        # Savings Statistics
        'total_savings_accounts': total_savings_accounts,
        'active_savings_accounts': active_savings_accounts,
        
        # Balance Sheet
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'member_equity': member_equity,
        'cash_accounts': cash_accounts,
        'loan_receivables': loan_receivables,
        
        # Recent Activity
        'recent_transactions': recent_transactions,
        'recent_loans': recent_loans,
        'recent_savings': recent_savings,
        
    # Loan Repayment Information
    'total_loan_repayments': total_loan_repayments,
    'automatic_repayments': automatic_repayments,
    'members_with_loans': members_with_loans,
    'total_collateral': total_collateral,
    
    # Chart Data
    'monthly_breakdown': monthly_breakdown,
    
    # Filters
    'selected_month': selected_month,
    'selected_year': selected_year,
    'current_year': current_year,
    'month_choices': [(i, date(selected_year, i, 1).strftime('%B')) for i in range(1, 13)],
    'year_choices': list(range(current_year - 5, current_year + 2)),
    }
    
    return render(request, 'reports/unified_reports.html', context)

@login_required
def detailed_analytics(request):
    """Detailed analytics and deep-dive reports"""
    from django.db.models import Q, Count, Avg
    from decimal import Decimal
    
    # Get current date info
    now = timezone.now()
    current_month = now.date().replace(day=1)
    current_year = now.year
    
    # Date filtering
    selected_month = request.GET.get('month', current_month.month)
    selected_year = request.GET.get('year', current_year)
    
    try:
        selected_month = int(selected_month)
        selected_year = int(selected_year)
    except (ValueError, TypeError):
        selected_month = current_month.month
        selected_year = current_year
    
    # Calculate date ranges
    month_start = date(selected_year, selected_month, 1)
    if selected_month == 12:
        month_end = date(selected_year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(selected_year, selected_month + 1, 1) - timedelta(days=1)
    
    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year, 12, 31)
    
    # Convert to timezone-aware datetimes
    month_start_dt = timezone.make_aware(datetime.combine(month_start, datetime.min.time()))
    month_end_dt = timezone.make_aware(datetime.combine(month_end, datetime.max.time()))
    year_start_dt = timezone.make_aware(datetime.combine(year_start, datetime.min.time()))
    year_end_dt = timezone.make_aware(datetime.combine(year_end, datetime.max.time()))
    
    # === MEMBER ANALYTICS ===
    # Member growth over time
    member_growth = []
    for month in range(1, 13):
        month_start_growth = date(selected_year, month, 1)
        if month == 12:
            month_end_growth = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_growth = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        month_start_dt_growth = timezone.make_aware(datetime.combine(month_start_growth, datetime.min.time()))
        month_end_dt_growth = timezone.make_aware(datetime.combine(month_end_growth, datetime.max.time()))
        
        new_members = Member.regular_members().filter(
            date_joined__range=[month_start_dt_growth, month_end_dt_growth]
        ).count()
        
        member_growth.append({
            'month': month,
            'month_name': month_start_growth.strftime('%b'),
            'new_members': new_members
        })
    
    # Member demographics
    total_members = Member.regular_members().count()
    active_members = Member.regular_members().filter(membership_status='active').count()
    inactive_members = total_members - active_members
    
    # Member age groups
    young_members = Member.regular_members().filter(
        date_of_birth__gte=date(selected_year - 30, 1, 1)
    ).count()
    middle_members = Member.regular_members().filter(
        date_of_birth__range=[date(selected_year - 50, 1, 1), date(selected_year - 30, 12, 31)]
    ).count()
    senior_members = Member.regular_members().filter(
        date_of_birth__lt=date(selected_year - 50, 1, 1)
    ).count()
    
    # === SAVINGS ANALYTICS ===
    # Savings performance by month
    savings_performance = []
    for month in range(1, 13):
        month_start_savings = date(selected_year, month, 1)
        if month == 12:
            month_end_savings = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_savings = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        month_start_dt_savings = timezone.make_aware(datetime.combine(month_start_savings, datetime.min.time()))
        month_end_dt_savings = timezone.make_aware(datetime.combine(month_end_savings, datetime.max.time()))
        
        deposits = SavingsTransaction.objects.filter(
            transaction_type='deposit',
            transaction_date__range=[month_start_dt_savings, month_end_dt_savings]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        withdrawals = SavingsTransaction.objects.filter(
            transaction_type='withdrawal',
            transaction_date__range=[month_start_dt_savings, month_end_dt_savings]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        savings_performance.append({
            'month': month,
            'month_name': month_start_savings.strftime('%b'),
            'deposits': float(deposits),
            'withdrawals': float(withdrawals),
            'net': float(deposits - withdrawals)
        })
    
    # Top savers
    top_savers = SavingsAccount.objects.select_related('member').order_by('-balance')[:10]
    
    # === LOAN ANALYTICS ===
    # Loan performance by month
    loan_performance = []
    for month in range(1, 13):
        month_start_loans = date(selected_year, month, 1)
        if month == 12:
            month_end_loans = date(selected_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end_loans = date(selected_year, month + 1, 1) - timedelta(days=1)
        
        month_start_dt_loans = timezone.make_aware(datetime.combine(month_start_loans, datetime.min.time()))
        month_end_dt_loans = timezone.make_aware(datetime.combine(month_end_loans, datetime.max.time()))
        
        disbursements = Loan.objects.filter(
            disbursement_date__range=[month_start_dt_loans, month_end_dt_loans]
        ).aggregate(total=Sum('approved_amount'))['total'] or 0
        
        repayments = LoanRepayment.objects.filter(
            payment_date__range=[month_start_dt_loans, month_end_dt_loans]
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        loan_performance.append({
            'month': month,
            'month_name': month_start_loans.strftime('%b'),
            'disbursements': float(disbursements),
            'repayments': float(repayments),
            'net': float(disbursements - repayments)
        })
    
    # Loan status distribution
    loan_status_dist = Loan.objects.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('approved_amount')
    ).order_by('-count')
    
    # Top borrowers
    top_borrowers = Loan.objects.select_related('member').order_by('-approved_amount')[:10]
    
    # === FINANCIAL HEALTH INDICATORS ===
    # Liquidity ratio (Cash / Total Assets)
    total_cash = Account.objects.filter(
        code__startswith='1'
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0')
    
    total_assets = Account.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0')
    liquidity_ratio = (total_cash / total_assets * 100) if total_assets > 0 else 0
    
    # Loan to savings ratio
    total_loans_outstanding = Loan.objects.filter(
        status='active'
    ).aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0')
    loan_to_savings_ratio = (total_loans_outstanding / total_savings * 100) if total_savings > 0 else 0
    
    # === TRANSACTION ANALYTICS ===
    # Transaction volume by type
    transaction_volume = Transaction.objects.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')
    
    # Daily transaction patterns
    daily_patterns = []
    for day in range(1, 8):  # Monday to Sunday
        day_transactions = Transaction.objects.filter(
            created_at__week_day=day
        ).count()
        daily_patterns.append({
            'day': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][day-1],
            'count': day_transactions
        })
    
    # === RISK ANALYSIS ===
    # Overdue loans analysis
    overdue_loans = Loan.objects.filter(
        status='active',
        expected_completion_date__lt=now.date()
    ).select_related('member')
    
    overdue_amount = overdue_loans.aggregate(total=Sum('approved_amount'))['total'] or Decimal('0')
    
    # High-risk members (multiple overdue loans)
    high_risk_members = Member.regular_members().annotate(
        overdue_count=Count('loans', filter=Q(loans__status='active', loans__expected_completion_date__lt=now.date()))
    ).filter(overdue_count__gte=2)
    
    context = {
        # Member Analytics
        'member_growth': member_growth,
        'total_members': total_members,
        'active_members': active_members,
        'inactive_members': inactive_members,
        'young_members': young_members,
        'middle_members': middle_members,
        'senior_members': senior_members,
        
        # Savings Analytics
        'savings_performance': savings_performance,
        'top_savers': top_savers,
        
        # Loan Analytics
        'loan_performance': loan_performance,
        'loan_status_dist': loan_status_dist,
        'top_borrowers': top_borrowers,
        
        # Financial Health
        'liquidity_ratio': liquidity_ratio,
        'loan_to_savings_ratio': loan_to_savings_ratio,
        'total_cash': total_cash,
        'total_assets': total_assets,
        
        # Transaction Analytics
        'transaction_volume': transaction_volume,
        'daily_patterns': daily_patterns,
        
        # Risk Analysis
        'overdue_loans': overdue_loans,
        'overdue_amount': overdue_amount,
        'high_risk_members': high_risk_members,
        
        # Filters
        'selected_month': selected_month,
        'selected_year': selected_year,
        'current_year': current_year,
        'month_choices': [(i, date(selected_year, i, 1).strftime('%B')) for i in range(1, 13)],
        'year_choices': list(range(current_year - 5, current_year + 2)),
    }
    
    return render(request, 'reports/detailed_analytics.html', context)
