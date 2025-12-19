from django.urls import path
from . import views, views_clean

app_name = 'reports'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('financial/', views.financial_reports, name='financial'),
    path('membership/', views.membership_reports, name='membership'),
    path('savings/', views.savings_reports, name='savings'),
    path('loans/', views.loan_reports, name='loans'),
    path('custom/', views.custom_reports, name='custom'),
    path('audit/', views.audit_reports, name='audit'),
    path('metrics/', views.performance_metrics, name='metrics'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('monthly/', views.monthly_reports, name='monthly'),
    path('annual/', views.annual_reports, name='annual'),
    path('export/', views.export_data, name='export'),
    path('process-export/', views.process_export, name='process_export'),
    path('preview/', views.preview_export, name='preview'),
    path('get-template/', views.get_template, name='get_template'),
    path('edit-template/', views.edit_template, name='edit_template'),
    path('retry-export/', views.retry_export, name='retry_export'),
    path('delete-export/', views.delete_export, name='delete_export'),
    path('export-status/', views.export_status, name='export_status'),
    path('member/<int:member_id>/', views.member_report, name='member_report'),
    path('export-all-members/', views.all_members_excel, name='all_members_excel'),
    path('transaction-history/', views.transaction_history, name='transaction_history'),
    path('unified/', views.unified_reports, name='unified'),
    path('analytics/', views.detailed_analytics, name='analytics'),
    
    # Clean, comprehensive reports
    path('comprehensive-annual/', views_clean.comprehensive_annual_report, name='comprehensive_annual'),
    path('comprehensive-monthly/', views_clean.comprehensive_monthly_report, name='comprehensive_monthly'),
    path('comprehensive-balance-sheet/', views_clean.comprehensive_balance_sheet, name='comprehensive_balance_sheet'),
]
