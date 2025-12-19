from django.urls import path
from . import views

app_name = 'members'

urlpatterns = [
    path('', views.member_list, name='list'),
    path('register/', views.member_register, name='register'),
    path('register-simple/', views.member_register_simple, name='register_simple'),
    path('register-test/', views.member_register_test, name='register_test'),
    path('reports/', views.member_reports, name='reports'),
    path('<int:pk>/', views.member_detail, name='detail'),
    path('<int:pk>/edit/', views.member_edit, name='edit'),
    path('<int:pk>/change-status/', views.change_status, name='change_status'),
    path('<int:member_id>/update-monthly-deposit/', views.update_monthly_deposit, name='update_monthly_deposit'),
    path('<int:member_id>/loan-info/', views.get_member_loan_info, name='loan_info'),
]
