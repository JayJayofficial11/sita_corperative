from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

class SavingsAccount(models.Model):
    """Individual member's savings account"""
    
    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('frozen', 'Frozen'),
        ('closed', 'Closed'),
    ]
    
    member = models.OneToOneField('members.Member', on_delete=models.CASCADE, related_name='savings_account')
    account_number = models.CharField(max_length=20, unique=True, editable=False)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='active')
    minimum_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Annual interest rate percentage")
    date_opened = models.DateField(default=timezone.now)
    date_closed = models.DateField(null=True, blank=True)
    
    # Loan repayment tracking
    collateral_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, help_text="Amount held as collateral for active loans")
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, help_text="Amount available for withdrawal (balance - collateral)")
    has_active_loan = models.BooleanField(default=False, help_text="Whether member has an active loan")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.account_number:
            # Generate unique account number
            year = timezone.now().year
            last_account = SavingsAccount.objects.filter(
                account_number__startswith=f'SAV{year}'
            ).order_by('account_number').last()
            
            if last_account:
                last_number = int(last_account.account_number[-6:])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.account_number = f'SAV{year}{new_number:06d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.account_number} - {self.member.user.get_full_name()}"
    
    def get_total_savings(self):
        """Get total savings including compulsory and voluntary"""
        return self.savings_transactions.filter(
            transaction_type__in=['compulsory', 'voluntary']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    def get_compulsory_savings(self):
        """Get total compulsory savings"""
        return self.savings_transactions.filter(
            transaction_type='compulsory'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    def get_voluntary_savings(self):
        """Get total voluntary savings"""
        return self.savings_transactions.filter(
            transaction_type='voluntary'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    def update_available_balance(self):
        """Update available balance based on collateral"""
        from decimal import Decimal
        self.available_balance = Decimal(str(self.balance)) - Decimal(str(self.collateral_amount))
        self.save(update_fields=['available_balance'])
    
    def set_collateral(self, amount):
        """Set collateral amount for loan"""
        from decimal import Decimal
        self.collateral_amount = Decimal(str(amount))
        self.has_active_loan = True
        self.update_available_balance()
        self.save()
    
    def clear_collateral(self):
        """Clear collateral when loan is completed"""
        self.collateral_amount = Decimal('0.00')
        self.has_active_loan = False
        self.update_available_balance()
        self.save()
    
    def can_withdraw(self, amount):
        """Check if member can withdraw specified amount"""
        return self.available_balance >= amount
    
    def get_loan_repayment_amount(self):
        """Get amount available for loan repayment (new savings only)"""
        if not self.has_active_loan:
            return Decimal('0.00')
        
        # Return the amount above collateral (new savings)
        return max(Decimal('0.00'), self.balance - self.collateral_amount)
    
    class Meta:
        verbose_name = 'Savings Account'
        verbose_name_plural = 'Savings Accounts'
        ordering = ['-created_at']

class SavingsTransaction(models.Model):
    """Individual savings transactions"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('compulsory', 'Compulsory Savings'),
        ('voluntary', 'Voluntary Savings'),
        ('withdrawal', 'Withdrawal'),
        ('interest', 'Interest Payment'),
        ('penalty', 'Penalty'),
        ('loan_repayment', 'Loan Repayment'),
        ('collateral', 'Collateral (Pre-loan Savings)'),
    ]
    
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    savings_account = models.ForeignKey(SavingsAccount, on_delete=models.CASCADE, related_name='savings_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    transaction_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default='completed')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_savings')
    
    # Loan repayment tracking
    related_loan = models.ForeignKey('loans.Loan', on_delete=models.SET_NULL, null=True, blank=True, related_name='savings_repayments')
    is_loan_repayment = models.BooleanField(default=False, help_text="Whether this transaction is for loan repayment")
    repayment_principal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Principal amount repaid")
    repayment_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Interest amount repaid")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Generate unique reference number
            import uuid
            self.reference_number = f'SVG{timezone.now().strftime("%Y%m%d")}{str(uuid.uuid4())[:8].upper()}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.reference_number} - {self.get_transaction_type_display()} - {self.amount}"
    
    class Meta:
        verbose_name = 'Savings Transaction'
        verbose_name_plural = 'Savings Transactions'
        ordering = ['-transaction_date']

class SavingsProduct(models.Model):
    """Different savings products offered by the cooperative"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    minimum_balance = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate percentage")
    withdrawal_limit = models.DecimalField(max_digits=10, decimal_places=2, help_text="Maximum withdrawal per month")
    is_compulsory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Savings Product'
        verbose_name_plural = 'Savings Products'
