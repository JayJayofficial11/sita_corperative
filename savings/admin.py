from django.contrib import admin
from .models import SavingsAccount, SavingsTransaction, SavingsProduct

class SavingsTransactionInline(admin.TabularInline):
    model = SavingsTransaction
    extra = 0
    readonly_fields = ('reference_number', 'balance_before', 'balance_after', 'created_at')
    fields = ('transaction_type', 'amount', 'description', 'transaction_date', 'status', 'processed_by')

class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'member', 'balance', 'status', 'date_opened')
    list_filter = ('status', 'date_opened')
    search_fields = ('account_number', 'member__member_id', 'member__user__first_name', 'member__user__last_name')
    readonly_fields = ('account_number', 'created_at', 'updated_at')
    inlines = [SavingsTransactionInline]
    
    fieldsets = (
        ('Account Information', {
            'fields': ('member', 'account_number', 'status')
        }),
        ('Balance Information', {
            'fields': ('balance', 'minimum_balance', 'interest_rate')
        }),
        ('Dates', {
            'fields': ('date_opened', 'date_closed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

class SavingsTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'savings_account', 'transaction_type', 'amount', 'transaction_date', 'status')
    list_filter = ('transaction_type', 'status', 'transaction_date')
    search_fields = ('reference_number', 'savings_account__account_number', 'savings_account__member__member_id')
    readonly_fields = ('reference_number', 'created_at', 'updated_at')
    ordering = ('-transaction_date',)

class SavingsProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'minimum_balance', 'interest_rate', 'withdrawal_limit', 'is_compulsory', 'is_active')
    list_filter = ('is_compulsory', 'is_active')
    search_fields = ('name', 'description')

admin.site.register(SavingsAccount, SavingsAccountAdmin)
admin.site.register(SavingsTransaction, SavingsTransactionAdmin)
admin.site.register(SavingsProduct, SavingsProductAdmin)
