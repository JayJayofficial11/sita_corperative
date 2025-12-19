from django.db import models
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from dateutil.relativedelta import relativedelta

User = get_user_model()

class LoanProduct(models.Model):
    """Different loan products offered by the cooperative"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    minimum_amount = models.DecimalField(max_digits=12, decimal_places=2)
    maximum_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate percentage")
    maximum_tenure_months = models.PositiveIntegerField(help_text="Maximum loan tenure in months")
    requires_guarantor = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Loan Product'
        verbose_name_plural = 'Loan Products'

class Loan(models.Model):
    """Loan applications and management"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('written_off', 'Written Off'),
    ]
    
    member = models.ForeignKey('members.Member', on_delete=models.CASCADE, related_name='loans')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.CASCADE)
    loan_id = models.CharField(max_length=20, unique=True, editable=False)
    
    # Loan Details
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tenure_months = models.PositiveIntegerField()
    monthly_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Status and Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    application_date = models.DateTimeField(default=timezone.now)
    approval_date = models.DateTimeField(null=True, blank=True)
    disbursement_date = models.DateTimeField(null=True, blank=True)
    expected_completion_date = models.DateField(null=True, blank=True)
    
    # Purpose and Guarantor
    purpose = models.TextField()
    guarantor_name = models.CharField(max_length=100, blank=True)
    guarantor_phone = models.CharField(max_length=17, blank=True)
    guarantor_address = models.TextField(blank=True)
    guarantor_relationship = models.CharField(max_length=100, blank=True)
    
    # Processing Information
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_loans')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans')
    disbursed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='disbursed_loans')
    
    # Balances
    principal_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    interest_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Comments
    approval_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.loan_id:
            # Generate unique loan ID
            year = timezone.now().year
            last_loan = Loan.objects.filter(
                loan_id__startswith=f'LN{year}'
            ).order_by('loan_id').last()
            
            if last_loan:
                last_number = int(last_loan.loan_id[-6:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.loan_id = f'LN{year}{new_number:06d}'
        
        # Calculate monthly payment if approved amount is set
        if self.approved_amount and self.tenure_months and not self.monthly_payment:
            monthly_rate = self.interest_rate / 100 / 12
            if monthly_rate > 0:
                self.monthly_payment = (
                    self.approved_amount * monthly_rate * (1 + monthly_rate) ** self.tenure_months
                ) / ((1 + monthly_rate) ** self.tenure_months - 1)
            else:
                self.monthly_payment = self.approved_amount / self.tenure_months
        
        # Set expected completion date
        if self.disbursement_date and not self.expected_completion_date:
            self.expected_completion_date = (self.disbursement_date + relativedelta(months=self.tenure_months)).date()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.loan_id} - {self.member.user.get_full_name()} - {self.requested_amount}"
    
    @property
    def total_amount_payable(self):
        """Calculate total amount to be paid including interest (10% added immediately)"""
        principal = self.approved_amount or self.requested_amount
        # Interest is 10% of principal, added immediately
        interest_amount = principal * Decimal('0.10')
        return principal + interest_amount
    
    @property
    def total_interest(self):
        """Calculate total interest payable (10% of principal)"""
        principal = self.approved_amount or self.requested_amount
        return principal * Decimal('0.10')
    
    @property
    def interest_payment_months(self):
        """Interest payment is flexible - no fixed months"""
        return 0  # Interest paid as available
    
    @property
    def total_repayment_months(self):
        """Maximum repayment period (22 months)"""
        return 22
    
    @property
    def monthly_principal_payment(self):
        """Flexible principal payment based on member's monthly deposit"""
        principal = self.approved_amount or self.requested_amount
        # This is now calculated dynamically based on member's monthly savings
        return principal / 22  # Minimum required monthly payment
    
    @property
    def monthly_interest_payment(self):
        """Interest payment is flexible - paid as available"""
        return self.total_interest  # Total interest to be paid
    
    @property
    def outstanding_balance(self):
        """Calculate outstanding balance"""
        if self.status not in ['active', 'approved']:
            return 0
        
        # Use the actual stored balance (updated during disbursement and repayments)
        return self.total_balance
    
    @property
    def is_overdue(self):
        """Check if loan is overdue"""
        if self.expected_completion_date and self.status == 'active':
            return timezone.now().date() > self.expected_completion_date
        return False
    
    def check_eligibility(self):
        """Check if member is eligible for this loan amount"""
        return self.member.can_apply_for_loan(self.requested_amount)
    
    def get_repayment_schedule(self):
        """Get flexible repayment schedule based on member's monthly deposit"""
        principal = self.approved_amount or self.requested_amount
        total_interest = self.total_interest
        total_to_repay = principal + total_interest
        
        # Get member's monthly deposit
        member_monthly_deposit = self.member.monthly_savings
        
        schedule = []
        remaining_interest = total_interest
        remaining_principal = principal
        current_month = 1
        
        # Phase 1: Pay interest first (as much as possible each month)
        while remaining_interest > 0 and current_month <= 22:
            interest_payment = min(member_monthly_deposit, remaining_interest)
            principal_payment = Decimal('0.00')
            
            if member_monthly_deposit > remaining_interest:
                # If monthly deposit exceeds remaining interest, pay some principal too
                principal_payment = min(member_monthly_deposit - remaining_interest, remaining_principal)
            
            remaining_interest -= interest_payment
            remaining_principal -= principal_payment
            
            schedule.append({
                'month': current_month,
                'principal_payment': principal_payment,
                'interest_payment': interest_payment,
                'total_payment': interest_payment + principal_payment,
                'remaining_balance': remaining_interest + remaining_principal,
                'phase': 'Interest Phase' if remaining_interest > 0 else 'Principal Phase'
            })
            
            current_month += 1
        
        # Phase 2: Pay principal (remaining months)
        while remaining_principal > 0 and current_month <= 22:
            principal_payment = min(member_monthly_deposit, remaining_principal)
            remaining_principal -= principal_payment
            
            schedule.append({
                'month': current_month,
                'principal_payment': principal_payment,
                'interest_payment': Decimal('0.00'),
                'total_payment': principal_payment,
                'remaining_balance': remaining_principal,
                'phase': 'Principal Phase'
            })
            
            current_month += 1
        
        return schedule
    
    class Meta:
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'
        ordering = ['-application_date']

class LoanRepayment(models.Model):
    """Loan repayment transactions"""
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    payment_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='completed')
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    
    payment_method = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_repayments')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            import uuid
            self.reference_number = f'REP{timezone.now().strftime("%Y%m%d")}{str(uuid.uuid4())[:8].upper()}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.loan.loan_id} - {self.amount}"
    
    @property
    def is_late(self):
        """Check if payment was made after due date"""
        return self.payment_date.date() > self.due_date
    
    class Meta:
        verbose_name = 'Loan Repayment'
        verbose_name_plural = 'Loan Repayments'
        ordering = ['-payment_date']
