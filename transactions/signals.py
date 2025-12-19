from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Transaction, TransactionEntry, Account, AccountCategory
from decimal import Decimal

@receiver(post_save, sender=Transaction)
def create_transaction_entries(sender, instance, created, **kwargs):
    """Automatically create double-entry bookkeeping entries for transactions"""
    if created and instance.status == 'completed':
        with transaction.atomic():
            # Get or create the main cooperative account
            cooperative_account, _ = Account.objects.get_or_create(
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
                    'description': 'Main cooperative account for all transactions'
                }
            )
            
            # Get or create income/expense accounts based on transaction type
            if instance.transaction_type == 'income':
                income_account, _ = Account.objects.get_or_create(
                    code='INC001',
                    defaults={
                        'name': 'General Income',
                        'category': AccountCategory.objects.get_or_create(
                            code='4000',
                            defaults={
                                'name': 'Income',
                                'category_type': 'income'
                            }
                        )[0],
                        'description': 'General income account'
                    }
                )
                
                # Create entries: Debit Cooperative Account, Credit Income Account
                TransactionEntry.objects.create(
                    transaction=instance,
                    account=cooperative_account,
                    entry_type='debit',
                    amount=instance.amount,
                    description=f"Income: {instance.description}"
                )
                
                TransactionEntry.objects.create(
                    transaction=instance,
                    account=income_account,
                    entry_type='credit',
                    amount=instance.amount,
                    description=f"Income: {instance.description}"
                )
                
            elif instance.transaction_type == 'expense':
                expense_account, _ = Account.objects.get_or_create(
                    code='EXP001',
                    defaults={
                        'name': 'General Expenses',
                        'category': AccountCategory.objects.get_or_create(
                            code='5000',
                            defaults={
                                'name': 'Expenses',
                                'category_type': 'expense'
                            }
                        )[0],
                        'description': 'General expenses account'
                    }
                )
                
                # Create entries: Debit Expense Account, Credit Cooperative Account
                TransactionEntry.objects.create(
                    transaction=instance,
                    account=expense_account,
                    entry_type='debit',
                    amount=instance.amount,
                    description=f"Expense: {instance.description}"
                )
                
                TransactionEntry.objects.create(
                    transaction=instance,
                    account=cooperative_account,
                    entry_type='credit',
                    amount=instance.amount,
                    description=f"Expense: {instance.description}"
                )
                
            
            # Update account balances
            update_account_balances(instance)

def update_account_balances(transaction):
    """Update account balances based on transaction entries"""
    entries = TransactionEntry.objects.filter(transaction=transaction)
    
    for entry in entries:
        account = entry.account
        if entry.entry_type == 'debit':
            if account.category.category_type in ['asset', 'expense']:
                account.balance += entry.amount
            else:  # liability, equity, income
                account.balance -= entry.amount
        else:  # credit
            if account.category.category_type in ['asset', 'expense']:
                account.balance -= entry.amount
            else:  # liability, equity, income
                account.balance += entry.amount
        
        account.save()
