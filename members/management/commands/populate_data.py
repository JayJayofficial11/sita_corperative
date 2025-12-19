from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from members.models import Member, MembershipType
from savings.models import SavingsAccount, SavingsProduct, SavingsTransaction
from loans.models import LoanProduct
from transactions.models import AccountCategory, Account
from datetime import date
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate the database with initial data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Starting data population...')

        # Create Account Categories
        categories_data = [
            {'name': 'Cash and Bank', 'code': 'CASH', 'category_type': 'asset'},
            {'name': 'Member Savings', 'code': 'MSAV', 'category_type': 'liability'},
            {'name': 'Loans Receivable', 'code': 'LOAN', 'category_type': 'asset'},
            {'name': 'Registration Fees', 'code': 'RFEE', 'category_type': 'income'},
            {'name': 'Interest Income', 'code': 'IINC', 'category_type': 'income'},
            {'name': 'Operating Expenses', 'code': 'OPEX', 'category_type': 'expense'},
            {'name': 'Member Equity', 'code': 'MEQU', 'category_type': 'equity'},
        ]

        for cat_data in categories_data:
            category, created = AccountCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data
            )
            if created:
                self.stdout.write(f'Created category: {category.name}')

        # Create Accounts
        accounts_data = [
            {'name': 'Cash in Hand', 'code': 'CASH001', 'category_code': 'CASH'},
            {'name': 'Bank Account', 'code': 'BANK001', 'category_code': 'CASH'},
            {'name': 'Member Compulsory Savings', 'code': 'MSAV001', 'category_code': 'MSAV'},
            {'name': 'Member Voluntary Savings', 'code': 'MSAV002', 'category_code': 'MSAV'},
            {'name': 'Loans Outstanding', 'code': 'LOAN001', 'category_code': 'LOAN'},
            {'name': 'Registration Fee Income', 'code': 'RFEE001', 'category_code': 'RFEE'},
            {'name': 'Loan Interest Income', 'code': 'IINC001', 'category_code': 'IINC'},
            {'name': 'Office Expenses', 'code': 'OPEX001', 'category_code': 'OPEX'},
            {'name': 'Share Capital', 'code': 'MEQU001', 'category_code': 'MEQU'},
        ]

        for acc_data in accounts_data:
            category = AccountCategory.objects.get(code=acc_data['category_code'])
            account, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults={
                    'name': acc_data['name'],
                    'category': category
                }
            )
            if created:
                self.stdout.write(f'Created account: {account.name}')

        # Create Membership Types
        membership_types_data = [
            {
                'name': 'Regular Membership',
                'description': 'Standard membership with basic benefits',
                'registration_fee': Decimal('5000.00'),
                'monthly_contribution': Decimal('2000.00'),
                'benefits': 'Access to loans, savings, and basic services'
            },
            {
                'name': 'Premium Membership',
                'description': 'Premium membership with enhanced benefits',
                'registration_fee': Decimal('10000.00'),
                'monthly_contribution': Decimal('5000.00'),
                'benefits': 'Higher loan limits, better interest rates, priority services'
            }
        ]

        for mt_data in membership_types_data:
            membership_type, created = MembershipType.objects.get_or_create(
                name=mt_data['name'],
                defaults=mt_data
            )
            if created:
                self.stdout.write(f'Created membership type: {membership_type.name}')

        # Create Savings Products
        savings_products_data = [
            {
                'name': 'Compulsory Savings',
                'description': 'Mandatory monthly savings for all members',
                'minimum_balance': Decimal('1000.00'),
                'interest_rate': Decimal('2.0'),
                'withdrawal_limit': Decimal('0.00'),
                'is_compulsory': True
            },
            {
                'name': 'Voluntary Savings',
                'description': 'Optional additional savings with higher interest',
                'minimum_balance': Decimal('500.00'),
                'interest_rate': Decimal('5.0'),
                'withdrawal_limit': Decimal('50000.00'),
                'is_compulsory': False
            },
            {
                'name': 'Target Savings',
                'description': 'Goal-oriented savings for specific purposes',
                'minimum_balance': Decimal('1000.00'),
                'interest_rate': Decimal('6.0'),
                'withdrawal_limit': Decimal('25000.00'),
                'is_compulsory': False
            }
        ]

        for sp_data in savings_products_data:
            savings_product, created = SavingsProduct.objects.get_or_create(
                name=sp_data['name'],
                defaults=sp_data
            )
            if created:
                self.stdout.write(f'Created savings product: {savings_product.name}')

        # Create Loan Products
        loan_products_data = [
            {
                'name': 'Personal Loan',
                'description': 'Short-term personal loans for members',
                'minimum_amount': Decimal('10000.00'),
                'maximum_amount': Decimal('500000.00'),
                'interest_rate': Decimal('12.0'),
                'maximum_tenure_months': 12,
                'requires_guarantor': True
            },
            {
                'name': 'Business Loan',
                'description': 'Medium-term loans for business purposes',
                'minimum_amount': Decimal('50000.00'),
                'maximum_amount': Decimal('2000000.00'),
                'interest_rate': Decimal('15.0'),
                'maximum_tenure_months': 24,
                'requires_guarantor': True
            },
            {
                'name': 'Emergency Loan',
                'description': 'Quick access loans for emergencies',
                'minimum_amount': Decimal('5000.00'),
                'maximum_amount': Decimal('100000.00'),
                'interest_rate': Decimal('18.0'),
                'maximum_tenure_months': 6,
                'requires_guarantor': False
            }
        ]

        for lp_data in loan_products_data:
            loan_product, created = LoanProduct.objects.get_or_create(
                name=lp_data['name'],
                defaults=lp_data
            )
            if created:
                self.stdout.write(f'Created loan product: {loan_product.name}')

        # Create some test users and members
        test_users_data = [
            {
                'username': 'manager1',
                'email': 'manager@coop.com',
                'first_name': 'John',
                'last_name': 'Manager',
                'role': 'manager'
            },
            {
                'username': 'staff1', 
                'email': 'staff@coop.com',
                'first_name': 'Jane',
                'last_name': 'Staff',
                'role': 'staff'
            },
            {
                'username': 'member1',
                'email': 'member1@coop.com', 
                'first_name': 'Alice',
                'last_name': 'Johnson',
                'role': 'member'
            },
            {
                'username': 'member2',
                'email': 'member2@coop.com',
                'first_name': 'Bob',
                'last_name': 'Smith', 
                'role': 'member'
            }
        ]

        for user_data in test_users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'role': user_data['role'],
                    'is_verified': True
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'Created user: {user.username}')

                # Create member profile for member users
                if user.role == 'member':
                    member, member_created = Member.objects.get_or_create(
                        user=user,
                        defaults={
                            'date_of_birth': date(1990, 1, 1),
                            'gender': 'M' if user.first_name == 'Bob' else 'F',
                            'marital_status': 'single',
                            'address': '123 Main Street',
                            'city': 'Lagos',
                            'state': 'Lagos',
                            'postal_code': '100001',
                            'emergency_contact_name': 'Emergency Contact',
                            'emergency_contact_phone': '+2348012345678',
                            'occupation': 'Software Developer',
                            'employer': 'Tech Company',
                            'monthly_savings': Decimal('150000.00'),
                            'registration_fee_paid': True,
                            'registration_fee_amount': Decimal('5000.00'),
                        }
                    )
                    if member_created:
                        self.stdout.write(f'Created member profile for: {user.get_full_name()}')
                        
                        # Create savings account
                        savings_account, savings_created = SavingsAccount.objects.get_or_create(
                            member=member,
                            defaults={
                                'balance': Decimal('50000.00'),
                                'minimum_balance': Decimal('1000.00'),
                                'interest_rate': Decimal('5.0')
                            }
                        )
                        if savings_created:
                            self.stdout.write(f'Created savings account for: {user.get_full_name()}')

        self.stdout.write(
            self.style.SUCCESS('Successfully populated initial data!')
        )
        self.stdout.write('You can now login with:')
        self.stdout.write('- Admin: jay / 123')
        self.stdout.write('- Manager: manager1 / password123')
        self.stdout.write('- Staff: staff1 / password123')
        self.stdout.write('- Member: member1 / password123')
