from django import forms
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from members.models import Member, MembershipType
from savings.models import SavingsProduct
from loans.models import LoanProduct
from transactions.models import AccountCategory
from datetime import date, timedelta

class FinancialReportForm(forms.Form):
    REPORT_TYPES = [
        ('balance_sheet', 'Balance Sheet'),
        ('income_statement', 'Income Statement'),
        ('cash_flow', 'Cash Flow Statement'),
        ('trial_balance', 'Trial Balance'),
        ('general_ledger', 'General Ledger'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Type"
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    account_category = forms.ModelChoiceField(
        queryset=AccountCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current financial year
        today = date.today()
        if today.month >= 4:  # Financial year starts in April
            fy_start = date(today.year, 4, 1)
            fy_end = date(today.year + 1, 3, 31)
        else:
            fy_start = date(today.year - 1, 4, 1)
            fy_end = date(today.year, 3, 31)
        
        self.fields['start_date'].initial = fy_start
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Report Configuration',
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                ),
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                'account_category'
            ),
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary btn-lg'),
                HTML('<button type="button" class="btn btn-outline-info btn-lg ms-2" onclick="setQuickDateRange()">Quick Ranges</button>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date must be before end date.")

        return cleaned_data

class MembershipReportForm(forms.Form):
    REPORT_TYPES = [
        ('member_list', 'Member Directory'),
        ('membership_statistics', 'Membership Statistics'),
        ('member_financial_summary', 'Member Financial Summary'),
        ('inactive_members', 'Inactive Members Report'),
        ('new_members', 'New Members Report'),
        ('member_contribution_history', 'Member Contribution History'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Type"
    )
    membership_type = forms.ModelChoiceField(
        queryset=MembershipType.objects.all(),
        required=False,
        empty_label="All Membership Types",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    membership_status = forms.ChoiceField(
        choices=[('', 'All Status')] + Member.MEMBERSHIP_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_joined_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Joined From"
    )
    date_joined_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Joined To"
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Membership Report Configuration',
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                ),
                Row(
                    Column('membership_type', css_class='col-md-6'),
                    Column('membership_status', css_class='col-md-6'),
                ),
                Row(
                    Column('date_joined_from', css_class='col-md-6'),
                    Column('date_joined_to', css_class='col-md-6'),
                )
            ),
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary btn-lg')
            )
        )

class SavingsReportForm(forms.Form):
    REPORT_TYPES = [
        ('savings_summary', 'Savings Summary'),
        ('savings_transactions', 'Savings Transactions'),
        ('member_savings_statement', 'Member Savings Statement'),
        ('dormant_accounts', 'Dormant Accounts'),
        ('high_balance_accounts', 'High Balance Accounts'),
        ('savings_growth', 'Savings Growth Analysis'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Type"
    )
    savings_product = forms.ModelChoiceField(
        queryset=SavingsProduct.objects.filter(is_active=True),
        required=False,
        empty_label="All Savings Products",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(membership_status='active'),
        required=False,
        empty_label="All Members",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    min_balance = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0'}),
        label="Minimum Balance Filter"
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current month
        today = date.today()
        first_day = today.replace(day=1)
        self.fields['start_date'].initial = first_day
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Savings Report Configuration',
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                ),
                Row(
                    Column('savings_product', css_class='col-md-6'),
                    Column('member', css_class='col-md-6'),
                ),
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                Row(
                    Column('min_balance', css_class='col-md-6'),
                )
            ),
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary btn-lg')
            )
        )

class LoanReportForm(forms.Form):
    REPORT_TYPES = [
        ('loan_portfolio', 'Loan Portfolio Summary'),
        ('loan_performance', 'Loan Performance Analysis'),
        ('member_loan_statement', 'Member Loan Statement'),
        ('overdue_loans', 'Overdue Loans Report'),
        ('loan_disbursements', 'Loan Disbursements'),
        ('loan_repayments', 'Loan Repayments'),
        ('defaulted_loans', 'Defaulted Loans'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Type"
    )
    loan_product = forms.ModelChoiceField(
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        empty_label="All Loan Products",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(membership_status='active'),
        required=False,
        empty_label="All Members",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    loan_status = forms.MultipleChoiceField(
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('defaulted', 'Defaulted'),
            ('rejected', 'Rejected'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current year
        today = date.today()
        year_start = date(today.year, 1, 1)
        self.fields['start_date'].initial = year_start
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Loan Report Configuration',
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                ),
                Row(
                    Column('loan_product', css_class='col-md-6'),
                    Column('member', css_class='col-md-6'),
                ),
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                'loan_status'
            ),
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary btn-lg')
            )
        )

class CustomReportForm(forms.Form):
    report_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Report Name"
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )
    data_sources = forms.MultipleChoiceField(
        choices=[
            ('members', 'Members'),
            ('savings', 'Savings'),
            ('loans', 'Loans'),
            ('transactions', 'Transactions'),
            ('accounts', 'Chart of Accounts'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Data Sources"
    )
    date_range_required = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Requires Date Range"
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    columns = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5, 
            'class': 'form-control',
            'placeholder': 'Enter column names separated by commas (e.g., Member Name, Balance, Date Joined)'
        }),
        label="Report Columns",
        help_text="Specify the columns you want in your custom report"
    )
    filters = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'class': 'form-control',
            'placeholder': 'Enter any specific filters or conditions'
        }),
        required=False,
        label="Additional Filters"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Custom Report Configuration',
                'report_name',
                'description',
                'data_sources',
                'date_range_required',
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                'columns',
                'filters'
            ),
            FormActions(
                Submit('submit', 'Generate Custom Report', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'reports:dashboard\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class ReportScheduleForm(forms.Form):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]

    report_type = forms.ChoiceField(
        choices=FinancialReportForm.REPORT_TYPES + [
            ('membership_summary', 'Membership Summary'),
            ('savings_summary', 'Savings Summary'),
            ('loan_summary', 'Loan Summary'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Report Type"
    )
    frequency = forms.ChoiceField(
        choices=FREQUENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    email_recipients = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'class': 'form-control',
            'placeholder': 'Enter email addresses separated by commas'
        }),
        label="Email Recipients",
        help_text="Email addresses to send the scheduled reports"
    )
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Enable Schedule",
        initial=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Schedule Configuration',
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('frequency', css_class='col-md-6'),
                ),
                'email_recipients',
                'is_active'
            ),
            FormActions(
                Submit('submit', 'Schedule Report', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'reports:dashboard\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean_email_recipients(self):
        emails = self.cleaned_data.get('email_recipients', '')
        email_list = [email.strip() for email in emails.split(',') if email.strip()]
        
        if not email_list:
            raise ValidationError("At least one email address is required.")
        
        # Basic email validation
        from django.core.validators import EmailValidator
        validator = EmailValidator()
        for email in email_list:
            try:
                validator(email)
            except ValidationError:
                raise ValidationError(f"Invalid email address: {email}")
        
        return ','.join(email_list)

class AuditReportForm(forms.Form):
    AUDIT_TYPES = [
        ('transaction_audit', 'Transaction Audit Trail'),
        ('user_activity', 'User Activity Log'),
        ('data_changes', 'Data Changes Log'),
        ('login_history', 'Login History'),
        ('system_errors', 'System Errors'),
    ]

    audit_type = forms.ChoiceField(
        choices=AUDIT_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Audit Report Type"
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    user_filter = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filter by username'}),
        label="User Filter"
    )
    severity = forms.ChoiceField(
        choices=[
            ('', 'All Levels'),
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default to last 30 days
        today = date.today()
        month_ago = today - timedelta(days=30)
        self.fields['start_date'].initial = month_ago
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Audit Report Configuration',
                Row(
                    Column('audit_type', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                ),
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                Row(
                    Column('user_filter', css_class='col-md-6'),
                    Column('severity', css_class='col-md-6'),
                )
            ),
            FormActions(
                Submit('submit', 'Generate Audit Report', css_class='btn btn-warning btn-lg')
            )
        )

class PerformanceMetricsForm(forms.Form):
    METRIC_TYPES = [
        ('financial_health', 'Financial Health Metrics'),
        ('member_engagement', 'Member Engagement Metrics'),
        ('growth_metrics', 'Growth Metrics'),
        ('risk_metrics', 'Risk Assessment Metrics'),
        ('operational_efficiency', 'Operational Efficiency'),
    ]

    metric_type = forms.ChoiceField(
        choices=METRIC_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Metrics Type"
    )
    comparison_period = forms.ChoiceField(
        choices=[
            ('month_over_month', 'Month over Month'),
            ('quarter_over_quarter', 'Quarter over Quarter'),
            ('year_over_year', 'Year over Year'),
            ('custom', 'Custom Period'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    include_charts = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include Charts and Graphs",
        initial=True
    )
    format = forms.ChoiceField(
        choices=[('html', 'View Online'), ('pdf', 'Download PDF'), ('excel', 'Download Excel')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='html'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default to current quarter
        today = date.today()
        quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        self.fields['start_date'].initial = quarter_start
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Performance Metrics Configuration',
                Row(
                    Column('metric_type', css_class='col-md-6'),
                    Column('comparison_period', css_class='col-md-6'),
                ),
                Row(
                    Column('start_date', css_class='col-md-6'),
                    Column('end_date', css_class='col-md-6'),
                ),
                Row(
                    Column('include_charts', css_class='col-md-6'),
                    Column('format', css_class='col-md-6'),
                )
            ),
            FormActions(
                Submit('submit', 'Generate Metrics Report', css_class='btn btn-info btn-lg')
            )
        )
