from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from .models import SavingsAccount, SavingsTransaction, SavingsProduct
from members.models import Member

User = get_user_model()

class SavingsDepositForm(forms.ModelForm):
    member = forms.ModelChoiceField(
        queryset=Member.regular_members().filter(membership_status='active'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Member"
    )

    class Meta:
        model = SavingsTransaction
        fields = ['member', 'transaction_type', 'amount', 'description']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0.01'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter transaction types for deposits
        self.fields['transaction_type'].choices = [
            ('compulsory', 'Compulsory Savings'),
            ('voluntary', 'Voluntary Savings'),
            ('interest', 'Interest Payment'),
        ]
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('member', css_class='col-md-6'),
                Column('transaction_type', css_class='col-md-6'),
            ),
            Row(
                Column('amount', css_class='col-md-6'),
            ),
            'description',
            FormActions(
                Submit('submit', 'Record Deposit', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'savings:accounts\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount

    def save(self, commit=True):
        transaction = super().save(commit=False)
        member = self.cleaned_data['member']
        
        # Get or create savings account
        savings_account, created = SavingsAccount.objects.get_or_create(
            member=member,
            defaults={'balance': 0}
        )
        
        from decimal import Decimal
        transaction.savings_account = savings_account
        transaction.balance_before = Decimal(str(savings_account.balance))
        transaction.balance_after = Decimal(str(savings_account.balance)) + Decimal(str(transaction.amount))
        transaction.processed_by = self.user
        
        if commit:
            transaction.save()
            # Update account balance
            savings_account.balance = transaction.balance_after
            savings_account.update_available_balance()
            savings_account.save()
            
            # Check if member has active loan and redirect new savings to repayment
            if savings_account.has_active_loan:
                from loans.models import Loan
                from decimal import Decimal
                active_loan = Loan.objects.filter(
                    member=member, 
                    status='active'
                ).first()
                
                if active_loan and active_loan.total_balance > 0:
                    # Process loan repayment directly with the full deposit amount
                    from loans.views import process_loan_repayment_from_deposit
                    success, message = process_loan_repayment_from_deposit(
                        member, active_loan, transaction.amount, transaction
                    )
                    if success:
                        # Update the transaction description to reflect what happened
                        transaction.description += f' (Auto-processed: {message})'
                        transaction.save()
        
        return transaction

class SavingsWithdrawalForm(forms.ModelForm):
    member = forms.ModelChoiceField(
        queryset=Member.regular_members().filter(membership_status='active'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Member"
    )

    class Meta:
        model = SavingsTransaction
        fields = ['member', 'amount', 'description']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0.01'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'member',
            'amount',
            'description',
            FormActions(
                Submit('submit', 'Process Withdrawal', css_class='btn btn-warning btn-lg'),
                HTML('<a href="{% url \'savings:accounts\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        amount = cleaned_data.get('amount')

        if member and amount:
            try:
                savings_account = SavingsAccount.objects.get(member=member)
                if not savings_account.can_withdraw(amount):
                    if savings_account.has_active_loan:
                        raise ValidationError(f"Insufficient available balance for withdrawal. Available: ₦{savings_account.available_balance:,.2f} (₦{savings_account.collateral_amount:,.2f} held as collateral)")
                    else:
                        raise ValidationError("Insufficient balance for withdrawal.")
                if amount < savings_account.minimum_balance:
                    raise ValidationError(f"Amount cannot be less than minimum balance of ₦{savings_account.minimum_balance}")
            except SavingsAccount.DoesNotExist:
                raise ValidationError("Member does not have a savings account.")

        return cleaned_data

    def save(self, commit=True):
        transaction = super().save(commit=False)
        member = self.cleaned_data['member']
        savings_account = SavingsAccount.objects.get(member=member)
        
        transaction.savings_account = savings_account
        from decimal import Decimal
        transaction.transaction_type = 'withdrawal'
        transaction.balance_before = Decimal(str(savings_account.balance))
        transaction.balance_after = Decimal(str(savings_account.balance)) - Decimal(str(transaction.amount))
        transaction.processed_by = self.user
        
        if commit:
            transaction.save()
            # Update account balance
            savings_account.balance = transaction.balance_after
            savings_account.update_available_balance()
            savings_account.save()
            
            # Create a Transaction record for recent transactions and transaction history
            from transactions.models import Transaction
            Transaction.objects.create(
                transaction_type='expense',
                description=f'Member withdrawal - {member.user.get_full_name()}: {transaction.description}',
                amount=transaction.amount,
                transaction_date=transaction.transaction_date,
                status='completed',
                member=member,
                savings_account=savings_account,
                created_by=self.user,
                notes=f'Savings withdrawal transaction ID: {transaction.id}'
            )
        
        return transaction

class SavingsAccountForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = ['member', 'minimum_balance', 'interest_rate', 'status']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'minimum_balance': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'interest_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '100'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class SavingsProductForm(forms.ModelForm):
    class Meta:
        model = SavingsProduct
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'minimum_balance': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'interest_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '100'}),
            'withdrawal_limit': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'is_compulsory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class SavingsSearchForm(forms.Form):
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by member name, account number...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + SavingsAccount.ACCOUNT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    balance_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Min Balance'})
    )
    balance_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Max Balance'})
    )
