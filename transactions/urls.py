from django.urls import path
from . import views
from . import money_views

app_name = 'transactions'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('list/', views.transaction_list, name='list'),
    path('add/', views.add_transaction, name='add'),
    path('quick/', views.quick_transaction, name='quick'),
    path('journal/', views.journal_entry, name='journal'),
    path('accounts/', views.accounts_list, name='accounts'),
    path('accounts/create/', views.create_account, name='create_account'),
    path('accounts/<int:pk>/edit/', views.edit_account, name='edit_account'),
    path('accounts/<int:pk>/ledger/', views.account_ledger, name='account_ledger'),
    path('cash-flow/', views.cash_flow_view, name='cash_flow'),
    path('cash-flow/create/', views.create_cash_flow, name='create_cash_flow'),
    path('statements/', views.financial_statements, name='statements'),
    path('reconciliation/', views.bank_reconciliation, name='reconciliation'),
    path('bulk-upload/', views.bulk_upload, name='bulk_upload'),
    
    # Enhanced transaction views
    path('member-payment/', money_views.process_member_payment, name='member_payment'),
    path('member-payment/ajax/', money_views.member_payment_ajax, name='member_payment_ajax'),
    path('member/<int:member_id>/accounts/', money_views.ajax_member_accounts, name='member_accounts'),
    path('financial-summary/', money_views.financial_summary, name='financial_summary'),
    path('bulk-process/', money_views.bulk_transaction_processing, name='bulk_process'),
    
    path('<int:pk>/', views.transaction_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_transaction, name='edit'),
    path('<int:pk>/delete/', views.delete_transaction, name='delete'),
    path('<int:pk>/undo/', views.undo_transaction, name='undo'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
]
