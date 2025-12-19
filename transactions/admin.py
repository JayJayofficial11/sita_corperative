from django.contrib import admin
from .models import AccountCategory, Account, Transaction, TransactionEntry, CashFlow

class TransactionEntryInline(admin.TabularInline):
    model = TransactionEntry
    extra = 2
    fields = ('account', 'entry_type', 'amount', 'description')

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'description', 'amount', 'transaction_type', 'transaction_date', 'status')
    list_filter = ('transaction_type', 'status', 'transaction_date')
    search_fields = ('transaction_id', 'description', 'member__member_id')
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    inlines = [TransactionEntryInline]
    ordering = ('-transaction_date',)

class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'balance', 'is_active')
    list_filter = ('category__category_type', 'is_active')
    search_fields = ('code', 'name', 'category__name')
    readonly_fields = ('created_at', 'updated_at')

class AccountCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category_type', 'is_active')
    list_filter = ('category_type', 'is_active')
    search_fields = ('code', 'name')

class CashFlowAdmin(admin.ModelAdmin):
    list_display = ('date', 'flow_type', 'amount', 'description', 'category')
    list_filter = ('flow_type', 'date', 'category')
    search_fields = ('description', 'category__name')
    ordering = ('-date',)

admin.site.register(AccountCategory, AccountCategoryAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(CashFlow, CashFlowAdmin)
