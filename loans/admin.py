from django.contrib import admin
from .models import LoanProduct, Loan, LoanRepayment

class LoanRepaymentInline(admin.TabularInline):
    model = LoanRepayment
    extra = 0
    readonly_fields = ('reference_number', 'balance_before', 'balance_after', 'created_at')
    fields = ('amount', 'principal_amount', 'interest_amount', 'penalty_amount', 'payment_date', 'due_date', 'status')

class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'member', 'loan_product', 'requested_amount', 'approved_amount', 'status', 'application_date')
    list_filter = ('status', 'loan_product', 'application_date', 'approval_date')
    search_fields = ('loan_id', 'member__member_id', 'member__user__first_name', 'member__user__last_name')
    readonly_fields = ('loan_id', 'monthly_payment', 'expected_completion_date', 'total_amount_payable', 'total_interest', 'created_at', 'updated_at')
    inlines = [LoanRepaymentInline]
    
    fieldsets = (
        ('Loan Information', {
            'fields': ('member', 'loan_product', 'loan_id', 'status')
        }),
        ('Loan Details', {
            'fields': ('requested_amount', 'approved_amount', 'interest_rate', 'tenure_months', 'monthly_payment')
        }),
        ('Purpose & Guarantor', {
            'fields': ('purpose', 'guarantor_name', 'guarantor_phone', 'guarantor_address', 'guarantor_relationship')
        }),
        ('Dates', {
            'fields': ('application_date', 'approval_date', 'disbursement_date', 'expected_completion_date')
        }),
        ('Processing', {
            'fields': ('reviewed_by', 'approved_by', 'disbursed_by', 'approval_notes', 'rejection_reason')
        }),
        ('Balance Information', {
            'fields': ('principal_balance', 'interest_balance', 'total_balance')
        }),
        ('Calculated Fields', {
            'fields': ('total_amount_payable', 'total_interest'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def total_amount_payable(self, obj):
        return obj.total_amount_payable
    total_amount_payable.short_description = 'Total Amount Payable'
    
    def total_interest(self, obj):
        return obj.total_interest
    total_interest.short_description = 'Total Interest'

class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'minimum_amount', 'maximum_amount', 'interest_rate', 'maximum_tenure_months', 'is_active')
    list_filter = ('is_active', 'requires_guarantor')
    search_fields = ('name', 'description')

class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'loan', 'amount', 'payment_date', 'due_date', 'status')
    list_filter = ('status', 'payment_date', 'due_date')
    search_fields = ('reference_number', 'loan__loan_id', 'loan__member__member_id')
    readonly_fields = ('reference_number', 'created_at', 'updated_at', 'is_late')
    
    def is_late(self, obj):
        return obj.is_late
    is_late.short_description = 'Late Payment'
    is_late.boolean = True

admin.site.register(LoanProduct, LoanProductAdmin)
admin.site.register(Loan, LoanAdmin)
admin.site.register(LoanRepayment, LoanRepaymentAdmin)
