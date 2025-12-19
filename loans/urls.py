from django.urls import path
from . import views

app_name = 'loans'

urlpatterns = [
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('applications/', views.loan_applications, name='applications'),
    path('active/', views.active_loans, name='active'),
    path('repayments/', views.loan_repayments, name='repayments'),
    path('reports/', views.loan_reports, name='reports'),
    path('products/', views.loan_products, name='products'),
    path('calculator/', views.loan_calculator, name='calculator'),
    path('calculate-ajax/', views.calculate_loan_ajax, name='calculate_ajax'),
    path('overdue/', views.overdue_loans, name='overdue'),
    path('apply/', views.apply_for_loan, name='apply'),
    path('<int:pk>/', views.loan_detail, name='detail'),
    path('<int:pk>/details/', views.loan_details_ajax, name='details_ajax'),
    path('<int:pk>/disburse/', views.disburse_loan, name='disburse'),
    path('member/<int:member_id>/', views.member_loans, name='member_loans'),
    path('<int:pk>/export/', views.export_detail, name='export_detail'),
    path('loan-data/', views.loan_data_ajax, name='loan_data'),  # AJAX endpoint for loan data
    path('disbursement-receipt/', views.disbursement_receipt, name='disbursement_receipt'),  # Disbursement receipt
    path('bulk-disburse/', views.bulk_disburse, name='bulk_disburse'),  # Bulk disbursement
]
