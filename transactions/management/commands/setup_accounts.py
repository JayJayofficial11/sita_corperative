from django.core.management.base import BaseCommand
from transactions.models import AccountCategory, Account

class Command(BaseCommand):
    help = 'Set up basic chart of accounts for the cooperative'

    def handle(self, *args, **options):
        self.stdout.write('Setting up chart of accounts...')
        
        # Create account categories
        categories_data = [
            {'name': 'Assets', 'code': '1', 'category_type': 'asset'},
            {'name': 'Liabilities', 'code': '2', 'category_type': 'liability'},
            {'name': 'Equity', 'code': '3', 'category_type': 'equity'},
            {'name': 'Income', 'code': '4', 'category_type': 'income'},
            {'name': 'Expenses', 'code': '5', 'category_type': 'expense'},
        ]
        
        categories = {}
        for cat_data in categories_data:
            category, created = AccountCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data
            )
            categories[cat_data['category_type']] = category
            if created:
                self.stdout.write(f'Created category: {category.name}')
        
        # Create basic accounts
        accounts_data = [
            # Assets
            {'code': '1000', 'name': 'Cash', 'category': categories['asset']},
            {'code': '1100', 'name': 'Bank Account', 'category': categories['asset']},
            {'code': '1200', 'name': 'Loans Receivable', 'category': categories['asset']},
            {'code': '1300', 'name': 'Fixed Assets', 'category': categories['asset']},
            
            # Liabilities
            {'code': '2000', 'name': 'Member Savings', 'category': categories['liability']},
            {'code': '2100', 'name': 'Accounts Payable', 'category': categories['liability']},
            {'code': '2200', 'name': 'Accrued Expenses', 'category': categories['liability']},
            
            # Equity
            {'code': '3000', 'name': 'Share Capital', 'category': categories['equity']},
            {'code': '3100', 'name': 'Retained Earnings', 'category': categories['equity']},
            {'code': '3200', 'name': 'Reserves', 'category': categories['equity']},
            
            # Income
            {'code': '4000', 'name': 'Interest Income', 'category': categories['income']},
            {'code': '4100', 'name': 'Service Charges', 'category': categories['income']},
            {'code': '4200', 'name': 'Other Income', 'category': categories['income']},
            
            # Expenses
            {'code': '5000', 'name': 'Administrative Expenses', 'category': categories['expense']},
            {'code': '5100', 'name': 'Interest Expense', 'category': categories['expense']},
            {'code': '5200', 'name': 'Operating Expenses', 'category': categories['expense']},
        ]
        
        for acc_data in accounts_data:
            account, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults=acc_data
            )
            if created:
                self.stdout.write(f'Created account: {account.name} ({account.code})')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully set up chart of accounts!')
        )
