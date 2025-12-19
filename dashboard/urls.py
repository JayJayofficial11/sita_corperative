from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('redirect/', views.dashboard_redirect, name='redirect'),
    path('member/', views.member_dashboard, name='member_dashboard'),
]
