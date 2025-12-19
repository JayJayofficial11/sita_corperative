from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from .models import Loan, LoanProduct, LoanRepayment
from members.models import Member
from savings.models import SavingsAccount
from decimal import Decimal

User = get_user_model()

class LoanApplicationForm(forms.ModelForm):
    member = forms.ModelChoiceField(
        queryset=Member.regular_members().filter(membership_status='active'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Member"
    )

    class Meta:
        model = Loan
        fields = [
            'member', 'loan_product', 'requested_amount', 'purpose',
            'guarantor_name', 'guarantor_phone', 'guarantor_address', 'guarantor_relationship',
            'interest_rate', 'tenure_months'
        ]
        widgets = {
            'loan_product': forms.Select(attrs={'class': 'form-select'}),
            'requested_amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '1'}),
            'purpose': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'guarantor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'guarantor_relationship': forms.TextInput(attrs={'class': 'form-control'}),
            'interest_rate': forms.HiddenInput(),
            'tenure_months': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['loan_product'].queryset = LoanProduct.objects.filter(is_active=True)
        
        # Set default values for hidden fields
        self.fields['interest_rate'].initial = 10.00
        self.fields['tenure_months'].initial = 22
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Loan Details',
                Row(
                    Column('member', css_class='col-md-6'),
                    Column('loan_product', css_class='col-md-6'),
                ),
                'requested_amount',
                'purpose',
                'interest_rate',
                'tenure_months'
            ),
            Fieldset(
                'Guarantor Information',
                Row(
                    Column('guarantor_name', css_class='col-md-6'),
                    Column('guarantor_phone', css_class='col-md-6'),
                ),
                Row(
                    Column('guarantor_relationship', css_class='col-md-6'),
                ),
                'guarantor_address'
            ),
            FormActions(
                Submit('submit', 'Submit Application', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'loans:applications\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        loan_product = cleaned_data.get('loan_product')
        requested_amount = cleaned_data.get('requested_amount')

        if member and loan_product and requested_amount:
            # Check if amount is within product limits
            if requested_amount < loan_product.minimum_amount:
                raise ValidationError(f"Minimum loan amount is ₦{loan_product.minimum_amount}")
            if requested_amount > loan_product.maximum_amount:
                raise ValidationError(f"Maximum loan amount is ₦{loan_product.maximum_amount}")

            # Check new eligibility rules
            can_apply, message = member.can_apply_for_loan(requested_amount)
            if not can_apply:
                raise ValidationError(message)

            # Check for existing pending loans
            if Loan.objects.filter(member=member, status__in=['pending', 'under_review', 'approved']).exists():
                raise ValidationError("Member already has a pending loan application.")

        return cleaned_data

    def save(self, commit=True):
        loan = super().save(commit=False)
        loan.interest_rate = loan.loan_product.interest_rate
        
        if commit:
            loan.save()
        return loan

class LoanApprovalForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['approved_amount', 'interest_rate', 'tenure_months', 'approval_notes']
        widgets = {
            'approved_amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
            'interest_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'max': '100'}),
            'tenure_months': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'approval_notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def clean_approved_amount(self):
        approved_amount = self.cleaned_data.get('approved_amount')
        if approved_amount and approved_amount <= 0:
            raise ValidationError("Approved amount must be greater than zero.")
        return approved_amount

class LoanRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=True,
        help_text="Please provide a clear reason for rejecting this loan application."
    )

class LoanRepaymentForm(forms.ModelForm):
    loan = forms.ModelChoiceField(
        queryset=Loan.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Loan"
    )

    class Meta:
        model = LoanRepayment
        fields = ['loan', 'amount', 'payment_method', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '0.01'}),
            'payment_method': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Cash, Bank Transfer'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'loan',
            Row(
                Column('amount', css_class='col-md-6'),
                Column('payment_method', css_class='col-md-6'),
            ),
            'notes',
            FormActions(
                Submit('submit', 'Process Repayment', css_class='btn btn-success btn-lg'),
                HTML('<a href="{% url \'loans:active\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        return amount

    def save(self, commit=True):
        repayment = super().save(commit=False)
        loan = repayment.loan
        
        repayment.balance_before = loan.total_balance
        repayment.principal_amount = min(repayment.amount, loan.principal_balance)
        repayment.interest_amount = min(repayment.amount - repayment.principal_amount, loan.interest_balance)
        repayment.balance_after = loan.total_balance - repayment.amount
        repayment.processed_by = self.user
        
        if commit:
            repayment.save()
            # Update loan balances
            loan.principal_balance -= repayment.principal_amount
            loan.interest_balance -= repayment.interest_amount
            loan.total_balance = loan.principal_balance + loan.interest_balance
            
            if loan.total_balance <= 0:
                loan.status = 'completed'
            
            loan.save()
        
        return repayment

class LoanSearchForm(forms.Form):
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by member name, loan ID...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Loan.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    loan_product = forms.ModelChoiceField(
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        empty_label="All Products",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    amount_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Min Amount'})
    )
    amount_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'placeholder': 'Max Amount'})
    )
