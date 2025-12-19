from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from .models import Account, AccountCategory, Transaction, TransactionEntry, CashFlow
from members.models import Member
from decimal import Decimal

User = get_user_model()

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'code', 'category', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1001'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('code', css_class='col-md-6'),
            ),
            'category',
            'description',
            'is_active',
            FormActions(
                Submit('submit', 'Save Account', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:accounts\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if Account.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Account code already exists.")
        return code

class AccountCategoryForm(forms.ModelForm):
    class Meta:
        model = AccountCategory
        fields = ['name', 'code', 'category_type', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('code', css_class='col-md-6'),
            ),
            'category_type',
            'description',
            FormActions(
                Submit('submit', 'Save Category', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:accounts\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'description', 'amount', 'transaction_date']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'transaction_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('transaction_type', css_class='col-md-6'),
                Column('amount', css_class='col-md-6'),
            ),
            'transaction_date',
            'description',
            FormActions(
                Submit('submit', 'Create Transaction', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class TransactionEntryForm(forms.ModelForm):
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Account"
    )

    class Meta:
        model = TransactionEntry
        fields = ['account', 'entry_type', 'amount', 'description']
        widgets = {
            'entry_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0.01'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount

class QuickTransactionForm(forms.Form):
    TRANSACTION_TYPES = [
        ('member_savings_deposit', 'Member Savings Deposit'),
        ('member_savings_withdrawal', 'Member Savings Withdrawal'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('share_capital_payment', 'Share Capital Payment'),
        ('membership_fee', 'Membership Fee'),
        ('dividend_payment', 'Dividend Payment'),
        ('expense', 'General Expense'),
        ('income', 'General Income'),
    ]

    transaction_type = forms.ChoiceField(
        choices=TRANSACTION_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Transaction Type"
    )
    member = forms.ModelChoiceField(
        queryset=Member.regular_members().filter(membership_status='active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Member (if applicable)"
    )
    amount = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0.01'}),
        max_digits=15,
        decimal_places=2
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        max_length=255
    )
    transaction_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Date when the transaction occurred"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'transaction_type',
            Row(
                Column('member', css_class='col-md-6'),
                Column('amount', css_class='col-md-6'),
            ),
            Row(
                Column('transaction_date', css_class='col-md-6'),
            ),
            'description',
            FormActions(
                Submit('submit', 'Process Transaction', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        member = cleaned_data.get('member')

        # Some transaction types require a member
        member_required_types = [
            'member_savings_deposit', 'member_savings_withdrawal',
            'loan_disbursement', 'loan_repayment',
            'share_capital_payment', 'membership_fee', 'dividend_payment'
        ]

        if transaction_type in member_required_types and not member:
            raise ValidationError("Member is required for this transaction type.")

        return cleaned_data

class CashFlowForm(forms.ModelForm):
    class Meta:
        model = CashFlow
        fields = ['flow_type', 'category', 'amount', 'description', 'date']
        widgets = {
            'flow_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('flow_type', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            Row(
                Column('amount', css_class='col-md-6'),
                Column('date', css_class='col-md-6'),
            ),
            'description',
            FormActions(
                Submit('submit', 'Record Cash Flow', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:cash_flow\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class TransactionSearchForm(forms.Form):
    TRANSACTION_TYPE_CHOICES = [
        ('', 'All Types'),
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by reference, description...'
        })
    )
    transaction_type = forms.ChoiceField(
        choices=TRANSACTION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_active=True),
        required=False,
        empty_label="All Accounts",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ModelChoiceField(
        queryset=AccountCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    amount_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Min Amount'})
    )
    amount_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Max Amount'})
    )

class BulkTransactionUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx'}),
        help_text="Upload CSV or Excel file with transaction data"
    )
    file_type = forms.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'file_type',
            'file',
            HTML('''
            <div class="alert alert-info mt-3">
                <h6>File Format Requirements:</h6>
                <ul class="mb-0">
                    <li><strong>Required Columns:</strong> Date, Description, Debit Account, Credit Account, Amount</li>
                    <li><strong>Date Format:</strong> YYYY-MM-DD</li>
                    <li><strong>Amount:</strong> Numeric value without currency symbols</li>
                    <li><strong>Accounts:</strong> Use account codes or names</li>
                </ul>
            </div>
            '''),
            FormActions(
                Submit('submit', 'Upload & Process', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class JournalEntryForm(forms.Form):
    reference_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-generated if left blank'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        max_length=255
    )
    transaction_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('reference_number', css_class='col-md-6'),
                Column('transaction_date', css_class='col-md-6'),
            ),
            'description',
            HTML('''
            <div id="journal-entries">
                <h5 class="mt-4">Journal Entries</h5>
                <div id="entry-forms">
                    <!-- Dynamic entry forms will be added here -->
                </div>
                <button type="button" id="add-entry" class="btn btn-outline-primary mt-2">
                    <i class="fas fa-plus"></i> Add Entry
                </button>
            </div>
            '''),
            FormActions(
                Submit('submit', 'Create Journal Entry', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class FinancialStatementFiltersForm(forms.Form):
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
    include_inactive = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Include Inactive Accounts"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current month
        from datetime import date
        today = date.today()
        first_day = today.replace(day=1)
        self.fields['start_date'].initial = first_day
        self.fields['end_date'].initial = today

        self.helper = FormHelper()
        self.helper.form_method = 'GET'
        self.helper.layout = Layout(
            Row(
                Column('start_date', css_class='col-md-3'),
                Column('end_date', css_class='col-md-3'),
                Column('account_category', css_class='col-md-3'),
                Column('include_inactive', css_class='col-md-3 d-flex align-items-end'),
            ),
            FormActions(
                Submit('submit', 'Generate Report', css_class='btn btn-primary'),
                HTML('<button type="button" class="btn btn-outline-secondary ms-2" onclick="window.print()">Print</button>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date must be before end date.")

        return cleaned_data

class BankReconciliationForm(forms.Form):
    bank_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(category__category_type='asset', name__icontains='bank'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Bank Account"
    )
    statement_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Bank Statement Date"
    )
    closing_balance = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
        label="Bank Statement Closing Balance",
        max_digits=15,
        decimal_places=2
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('bank_account', css_class='col-md-4'),
                Column('statement_date', css_class='col-md-4'),
                Column('closing_balance', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Start Reconciliation', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class BudgetForm(forms.Form):
    budget_year = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '2020', 'max': '2030'}),
        label="Budget Year"
    )
    category = forms.ModelChoiceField(
        queryset=AccountCategory.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Category"
    )
    budgeted_amount = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
        max_digits=15,
        decimal_places=2,
        label="Budgeted Amount"
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from datetime import date
        self.fields['budget_year'].initial = date.today().year

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('budget_year', css_class='col-md-6'),
                Column('category', css_class='col-md-6'),
            ),
            Row(
                Column('budgeted_amount', css_class='col-md-6'),
            ),
            'notes',
            FormActions(
                Submit('submit', 'Save Budget', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:budgets\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

class AssetDepreciationForm(forms.Form):
    asset_account = forms.ModelChoiceField(
        queryset=Account.objects.filter(category__name__icontains='asset'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Asset Account"
    )
    depreciation_method = forms.ChoiceField(
        choices=[
            ('straight_line', 'Straight Line'),
            ('declining_balance', 'Declining Balance'),
            ('sum_of_years', 'Sum of Years Digits')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    asset_cost = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
        max_digits=15,
        decimal_places=2
    )
    useful_life_years = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        label="Useful Life (Years)"
    )
    salvage_value = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0'}),
        max_digits=15,
        decimal_places=2,
        initial=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'asset_account',
            Row(
                Column('depreciation_method', css_class='col-md-6'),
                Column('useful_life_years', css_class='col-md-6'),
            ),
            Row(
                Column('asset_cost', css_class='col-md-6'),
                Column('salvage_value', css_class='col-md-6'),
            ),
            FormActions(
                Submit('submit', 'Calculate Depreciation', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'transactions:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )
