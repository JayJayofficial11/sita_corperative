from django.urls import path
from . import views

app_name = 'savings'

urlpatterns = [
    path('accounts/', views.savings_accounts, name='accounts'),
    path('deposit/', views.record_deposit, name='deposit'),
    path('withdraw/', views.process_withdrawal, name='withdraw'),
    path('reports/', views.savings_reports, name='reports'),
    path('account/<int:pk>/', views.account_detail, name='account_detail'),
    path('detail/<int:pk>/', views.account_detail, name='detail'),
    path('member/<int:member_id>/', views.member_savings, name='member_savings'),
    path('<int:pk>/export/', views.export_transactions, name='export_transactions'),
    path('transactions/<int:pk>/undo/', views.undo_savings_transaction, name='undo_transaction'),
]
