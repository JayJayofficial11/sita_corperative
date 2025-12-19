"""
Management command to create default loan products for the cooperative.
"""
from django.core.management.base import BaseCommand
from loans.models import LoanProduct
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create default loan products for the cooperative'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing loan products if they exist',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']

        # Define loan products
        loan_products = [
            {
                'name': 'Personal Loan',
                'description': 'Personal loan for individual members to meet personal financial needs such as education, medical expenses, home improvements, or other personal requirements. Flexible repayment terms with competitive interest rates. No maximum amount limit.',
                'minimum_amount': Decimal('10000.00'),
                'maximum_amount': Decimal('999999999.99'),  # Essentially unlimited (999 million - more than enough for any practical loan)
                'interest_rate': Decimal('10.00'),  # 10% annual interest
                'maximum_tenure_months': 22,
                'requires_guarantor': True,
                'is_active': True,
            },
            {
                'name': 'Business Loan',
                'description': 'Business loan designed for members who want to start or expand their business ventures. Ideal for small business owners, entrepreneurs, and traders. No maximum amount limit with flexible repayment options.',
                'minimum_amount': Decimal('50000.00'),
                'maximum_amount': Decimal('999999999.99'),  # Essentially unlimited (999 million - more than enough for any practical loan)
                'interest_rate': Decimal('10.00'),  # 10% annual interest
                'maximum_tenure_months': 22,
                'requires_guarantor': True,
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for product_data in loan_products:
            name = product_data['name']
            
            try:
                product, created = LoanProduct.objects.get_or_create(
                    name=name,
                    defaults=product_data
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created loan product: {name}')
                    )
                    created_count += 1
                else:
                    if overwrite:
                        # Update existing product
                        for key, value in product_data.items():
                            setattr(product, key, value)
                        product.save()
                        self.stdout.write(
                            self.style.WARNING(f'↻ Updated loan product: {name}')
                        )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'⊘ Skipped (already exists): {name}')
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error creating {name}: {str(e)}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Completed! Created: {created_count}, Updated: {updated_count}'
        ))

