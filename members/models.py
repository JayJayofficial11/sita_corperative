from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
import uuid

User = get_user_model()

class Member(models.Model):
    """Member profile extending the User model"""
    
    @classmethod
    def regular_members(cls):
        """Return queryset of regular members (excluding admin/staff users)"""
        return cls.objects.exclude(
            user__is_superuser=True
        ).exclude(
            user__is_staff=True
        )
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]
    
    MEMBERSHIP_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ]
    
    # Primary Information
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    member_id = models.CharField(max_length=20, unique=True, editable=False)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES)
    
    # Contact Information
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    emergency_contact_name = models.CharField(max_length=100)
    emergency_contact_phone = models.CharField(max_length=17)
    
    # Employment Information
    occupation = models.CharField(max_length=100)
    employer = models.CharField(max_length=100, blank=True)
    monthly_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monthly savings commitment amount")
    
    # Membership Information
    membership_status = models.CharField(max_length=20, choices=MEMBERSHIP_STATUS_CHOICES, default='active')
    date_joined = models.DateField(default=timezone.now)
    entrance_date = models.DateField(default=timezone.now, help_text="Date when member joined the cooperative")
    registration_fee_paid = models.BooleanField(default=False)
    registration_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Guarantor Information
    guarantor_name = models.CharField(max_length=100, blank=True)
    guarantor_phone = models.CharField(max_length=17, blank=True)
    guarantor_address = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.member_id:
            # Generate unique member ID
            year = timezone.now().year
            last_member = Member.objects.filter(
                member_id__startswith=f'COOP{year}'
            ).order_by('member_id').last()
            
            if last_member:
                last_number = int(last_member.member_id[-4:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.member_id = f'COOP{year}{new_number:04d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.member_id} - {self.user.get_full_name()}"
    
    @property
    def full_name(self):
        return self.user.get_full_name()
    
    @property
    def age(self):
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def maximum_loan_amount(self):
        """Calculate maximum loan amount based on total deposits × 2"""
        try:
            if hasattr(self, 'savings_account') and self.savings_account:
                # Get total deposits (compulsory + voluntary savings)
                total_deposits = self.savings_account.get_total_savings()
                return total_deposits * 2
            return Decimal('0.00')
        except:
            return Decimal('0.00')
    
    @property
    def total_interest_amount(self):
        """Calculate total interest amount (10% of maximum loan)"""
        return self.maximum_loan_amount * Decimal('0.10')
    
    @property
    def total_loan_repayment_amount(self):
        """Calculate total loan repayment amount (principal + interest)"""
        return self.maximum_loan_amount + self.total_interest_amount
    
    def get_outstanding_loan_amount(self):
        """Get total outstanding loan amount for this member"""
        from loans.models import Loan
        active_loans = Loan.objects.filter(
            member=self,
            status__in=['active', 'approved']
        )
        return sum(loan.outstanding_balance for loan in active_loans)
    
    def can_apply_for_loan(self, requested_amount):
        """Check if member can apply for a loan of the requested amount"""
        outstanding_amount = self.get_outstanding_loan_amount()
        total_after_loan = outstanding_amount + requested_amount
        
        # Check if total loans would exceed maximum (total deposits × 2)
        if total_after_loan > self.maximum_loan_amount:
            return False, f"Total loan amount would exceed maximum of ₦{self.maximum_loan_amount:,.2f} (2x your total deposits)"
        
        # Check 22-month repayment rule
        if not self.can_repay_within_22_months(requested_amount):
            return False, f"Cannot repay loan within 22 months with current monthly deposit of ₦{self.monthly_savings:,.2f}"
        
        # Check if member has paid 85% of outstanding loan (if any)
        if outstanding_amount > 0:
            from loans.models import Loan
            total_borrowed = sum(loan.approved_amount or loan.requested_amount for loan in Loan.objects.filter(
                member=self,
                status__in=['active', 'approved']
            ))
            total_paid = total_borrowed - outstanding_amount
            paid_percentage = (total_paid / total_borrowed) * 100 if total_borrowed > 0 else 0
            
            if paid_percentage < 85:
                return False, f"Must pay at least 85% of outstanding loan. Currently paid: {paid_percentage:.1f}%"
        
        return True, "Loan application approved"
    
    def can_repay_within_22_months(self, loan_amount):
        """Check if member can repay loan within 22 months based on monthly deposit"""
        if self.monthly_savings <= 0:
            return False
        
        # Calculate total amount to repay (principal + 10% interest)
        total_to_repay = loan_amount * Decimal('1.10')
        
        # Calculate if monthly deposit can cover this in 22 months
        required_monthly_payment = total_to_repay / 22
        
        return self.monthly_savings >= required_monthly_payment
    
    def get_loan_progress(self):
        """Get detailed loan progress information for member dashboard"""
        from loans.models import Loan
        active_loans = Loan.objects.filter(
            member=self,
            status__in=['active', 'approved']
        )
        
        if not active_loans.exists():
            return {
                'has_active_loan': False,
                'total_borrowed': Decimal('0.00'),
                'total_interest': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'remaining_balance': Decimal('0.00'),
                'interest_paid': Decimal('0.00'),
                'principal_paid': Decimal('0.00'),
                'interest_remaining': Decimal('0.00'),
                'principal_remaining': Decimal('0.00'),
                'progress_percentage': 0,
                'interest_progress_percentage': 0,
                'principal_progress_percentage': 0
            }
        
        loan = active_loans.first()  # Assuming one active loan at a time
        total_borrowed = loan.approved_amount or loan.requested_amount
        total_interest = total_borrowed * Decimal('0.10')
        total_to_repay = total_borrowed + total_interest
        
        # Calculate amounts paid
        repayments = loan.repayments.filter(status='completed')
        total_paid = sum(rep.amount for rep in repayments)
        interest_paid = sum(rep.interest_amount for rep in repayments)
        principal_paid = sum(rep.principal_amount for rep in repayments)
        
        # Calculate remaining amounts
        remaining_balance = total_to_repay - total_paid
        interest_remaining = total_interest - interest_paid
        principal_remaining = total_borrowed - principal_paid
        
        # Calculate progress percentages
        progress_percentage = (total_paid / total_to_repay * 100) if total_to_repay > 0 else 0
        interest_progress_percentage = (interest_paid / total_interest * 100) if total_interest > 0 else 0
        principal_progress_percentage = (principal_paid / total_borrowed * 100) if total_borrowed > 0 else 0
        
        return {
            'has_active_loan': True,
            'loan_id': loan.loan_id,
            'total_borrowed': total_borrowed,
            'total_interest': total_interest,
            'total_to_repay': total_to_repay,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance,
            'interest_paid': interest_paid,
            'principal_paid': principal_paid,
            'interest_remaining': interest_remaining,
            'principal_remaining': principal_remaining,
            'progress_percentage': round(float(progress_percentage), 2),
            'interest_progress_percentage': round(float(interest_progress_percentage), 2),
            'principal_progress_percentage': round(float(principal_progress_percentage), 2),
            'is_interest_phase': interest_remaining > 0,
            'is_principal_phase': interest_remaining <= 0 and principal_remaining > 0,
            'is_completed': remaining_balance <= 0
        }
    
    class Meta:
        verbose_name = 'Member'
        verbose_name_plural = 'Members'
        ordering = ['-created_at']

class MembershipType(models.Model):
    """Different types of membership (Regular, Premium, etc.)"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_contribution = models.DecimalField(max_digits=10, decimal_places=2)
    benefits = models.TextField(help_text="List of benefits for this membership type")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Membership Type'
        verbose_name_plural = 'Membership Types'
