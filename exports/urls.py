from django.urls import path
from . import views

app_name = 'exports'

urlpatterns = [
    # Members exports
    path('members/excel/', views.export_members_excel, name='members_excel'),
    path('members/csv/', views.export_members_csv, name='members_csv'),
    
    # Savings exports
    path('savings/excel/', views.export_savings_excel, name='savings_excel'),
    
    # Loans exports
    path('loans/excel/', views.export_loans_excel, name='loans_excel'),
    
    # Transactions exports
    path('transactions/excel/', views.export_transactions_excel, name='transactions_excel'),
    
    # Financial summary
    path('financial-summary/excel/', views.export_financial_summary_excel, name='financial_summary_excel'),
    
    # Custom/dynamic export
    path('custom/', views.export_custom_report, name='custom_export'),
]
