from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

class AccountCategory(models.Model):
    """Chart of accounts categories"""
    
    CATEGORY_TYPES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    class Meta:
        verbose_name = 'Account Category'
        verbose_name_plural = 'Account Categories'
        ordering = ['code']

class Account(models.Model):
    """Individual accounts in the chart of accounts"""
    
    category = models.ForeignKey(AccountCategory, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def account_type(self):
        return self.category.category_type
    
    class Meta:
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'
        ordering = ['code']

class Transaction(models.Model):
    """General ledger transactions"""
    
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    transaction_id = models.CharField(max_length=20, unique=True, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    
    # Reference to related records
    member = models.ForeignKey('members.Member', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    loan = models.ForeignKey('loans.Loan', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_transactions')
    savings_account = models.ForeignKey('savings.SavingsAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='related_transactions')
    
    # Processing Information
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_transactions')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transactions')
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            # Generate unique transaction ID
            import uuid
            self.transaction_id = f'TXN{timezone.now().strftime("%Y%m%d")}{str(uuid.uuid4())[:8].upper()}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.transaction_id} - {self.description} - {self.amount}"
    
    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-transaction_date']

class TransactionEntry(models.Model):
    """Double-entry bookkeeping entries for each transaction"""
    
    ENTRY_TYPES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.transaction.transaction_id} - {self.account.code} - {self.entry_type} - {self.amount}"
    
    class Meta:
        verbose_name = 'Transaction Entry'
        verbose_name_plural = 'Transaction Entries'
        ordering = ['-created_at']

class CashFlow(models.Model):
    """Cash flow tracking for the cooperative"""
    
    FLOW_TYPES = [
        ('inflow', 'Cash Inflow'),
        ('outflow', 'Cash Outflow'),
    ]
    
    date = models.DateField(default=timezone.now)
    flow_type = models.CharField(max_length=10, choices=FLOW_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    category = models.ForeignKey(AccountCategory, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.date} - {self.get_flow_type_display()} - {self.amount}"
    
    class Meta:
        verbose_name = 'Cash Flow'
        verbose_name_plural = 'Cash Flows'
        ordering = ['-date']
