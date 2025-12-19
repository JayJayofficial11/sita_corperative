"""
Management command to clear all data from the cooperative management system.
This preserves the database structure but removes all records.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

# Import all models
from transactions.models import Transaction, TransactionEntry, Account, AccountCategory, CashFlow
from savings.models import SavingsAccount, SavingsTransaction, SavingsProduct
from loans.models import Loan, LoanRepayment, LoanProduct
from members.models import Member, MembershipType

User = get_user_model()


class Command(BaseCommand):
    help = 'Clear all data from the cooperative management system (preserves database structure)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-users',
            action='store_true',
            help='Keep user accounts (only clear member profiles)',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        keep_users = options['keep_users']
        confirm = options['confirm']

        if not confirm:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  WARNING: This will delete ALL data from the cooperative management system!\n'
                'This includes:\n'
                '  - All transactions and transaction entries\n'
                '  - All savings accounts and savings transactions\n'
                '  - All loans and loan repayments\n'
                '  - All members and member profiles\n'
                '  - All accounts and account categories\n'
                '  - All cash flow records\n'
            ))
            
            if not keep_users:
                self.stdout.write(self.style.WARNING(
                    '  - All user accounts (except superusers)\n'
                ))
            
            response = input('\nAre you sure you want to proceed? (yes/no): ')
            if response.lower() not in ['yes', 'y']:
                self.stdout.write(self.style.SUCCESS('Operation cancelled.'))
                return

        self.stdout.write(self.style.WARNING('\nStarting data cleanup...\n'))

        try:
            with transaction.atomic():
                # Delete in order to respect foreign key constraints
                
                # 1. Delete transaction-related data
                self.stdout.write('Deleting transaction entries...')
                TransactionEntry.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted transaction entries'))
                
                self.stdout.write('Deleting transactions...')
                Transaction.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted transactions'))
                
                self.stdout.write('Deleting cash flow records...')
                CashFlow.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted cash flow records'))
                
                # 2. Delete savings-related data
                self.stdout.write('Deleting savings transactions...')
                SavingsTransaction.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted savings transactions'))
                
                self.stdout.write('Deleting savings accounts...')
                SavingsAccount.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted savings accounts'))
                
                self.stdout.write('Deleting savings products...')
                SavingsProduct.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted savings products'))
                
                # 3. Delete loan-related data
                self.stdout.write('Deleting loan repayments...')
                LoanRepayment.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted loan repayments'))
                
                self.stdout.write('Deleting loans...')
                Loan.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted loans'))
                
                self.stdout.write('Deleting loan products...')
                LoanProduct.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted loan products'))
                
                # 4. Delete member-related data
                self.stdout.write('Deleting members...')
                Member.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted members'))
                
                self.stdout.write('Deleting membership types...')
                MembershipType.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted membership types'))
                
                # 5. Delete account-related data
                self.stdout.write('Deleting accounts...')
                Account.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted accounts'))
                
                self.stdout.write('Deleting account categories...')
                AccountCategory.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted account categories'))
                
                # 6. Delete users (if not keeping them)
                if not keep_users:
                    self.stdout.write('Deleting user accounts (except superusers)...')
                    deleted_count = User.objects.filter(is_superuser=False).delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {deleted_count} user accounts'))
                else:
                    self.stdout.write(self.style.SUCCESS('  ✓ Kept user accounts'))

                self.stdout.write(self.style.SUCCESS('\n✅ All data cleared successfully!'))
                self.stdout.write(self.style.SUCCESS('The database structure is preserved and ready for fresh data.\n'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error clearing data: {str(e)}'))
            raise

