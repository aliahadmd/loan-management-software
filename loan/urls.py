from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('apply/', views.loan_application, name='loan_application'),
    path('loan/<int:pk>/', views.loan_detail, name='loan_detail'),
    path('loan/<int:loan_id>/payment/', views.make_payment, name='make_payment'),
    path('loan/<int:pk>/approve/', views.approve_loan, name='approve_loan'),
    path('loan/<int:pk>/reject/', views.reject_loan, name='reject_loan'),
    path('loans/pending/', views.loan_approval_list, name='loan_approval_list'),
] 