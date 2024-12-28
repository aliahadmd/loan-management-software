from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from .models import Loan, Payment, LoanType
from .forms import LoanApplicationForm, PaymentForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum, Avg, Case, When, F, DecimalField, IntegerField
from django.db.models.functions import TruncMonth, Coalesce
from datetime import datetime, timedelta
import json

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

@login_required
def dashboard(request):
    user_loans = Loan.objects.filter(borrower=request.user)
    
    # Calculate dashboard statistics
    stats = {
        'total_loans': user_loans.count(),
        'active_loans': user_loans.filter(status='ACTIVE').count(),
        'pending_loans': user_loans.filter(status='PENDING').count(),
        'total_borrowed': user_loans.filter(status__in=['ACTIVE', 'CLOSED']).aggregate(
            total=models.Sum('amount'))['total'] or 0,
        'total_payable': user_loans.filter(status__in=['ACTIVE', 'CLOSED']).aggregate(
            total=models.Sum('total_payable'))['total'] or 0,
    }
    
    context = {
        'loans': user_loans.order_by('-application_date'),
        'stats': stats,
    }
    return render(request, 'loan/dashboard.html', context)

@login_required
def loan_application(request):
    if request.method == 'POST':
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            try:
                loan = form.save(commit=False)
                loan.borrower = request.user
                loan.save()
                messages.success(request, 'Loan application submitted successfully! We will review your application shortly.')
                return redirect('loan_detail', pk=loan.pk)
            except Exception as e:
                messages.error(request, f'Error submitting loan application: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoanApplicationForm()
    
    context = {
        'form': form,
        'loan_types': LoanType.objects.all(),
    }
    return render(request, 'loan/loan_form.html', context)

@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan, pk=pk, borrower=request.user)
    payments = loan.payments.all().order_by('-payment_date')
    
    context = {
        'loan': loan,
        'payments': payments,
    }
    return render(request, 'loan/loan_detail.html', context)

def is_loan_officer(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_loan_officer)
def loan_approval_list(request):
    pending_loans = Loan.objects.filter(status='PENDING').order_by('-application_date')
    return render(request, 'loan/loan_approval_list.html', {'loans': pending_loans})

@require_POST
@user_passes_test(is_loan_officer)
def approve_loan(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    if loan.approve_loan(request.user):
        messages.success(request, f'Loan #{loan.pk} has been approved.')
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Unable to approve loan'})

@require_POST
@user_passes_test(is_loan_officer)
def reject_loan(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    reason = request.POST.get('reason', '')
    if loan.reject_loan(request.user, reason):
        messages.success(request, f'Loan #{loan.pk} has been rejected.')
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Unable to reject loan'})

@login_required
def make_payment(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id, borrower=request.user)
    
    if loan.status != 'ACTIVE':
        messages.error(request, 'Payments can only be made for active loans.')
        return redirect('loan_detail', pk=loan.pk)

    if request.method == 'POST':
        form = PaymentForm(request.POST, loan=loan)
        if form.is_valid():
            try:
                payment = form.save()
                messages.success(
                    request, 
                    f'Payment of ${payment.amount:,.2f} recorded successfully! '
                    f'Remaining balance: ${loan.get_remaining_balance():,.2f}'
                )
                return redirect('loan_detail', pk=loan.pk)
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(loan=loan)
    
    context = {
        'form': form,
        'loan': loan,
    }
    return render(request, 'loan/payment_form.html', context)

@user_passes_test(is_loan_officer)
def loan_reports(request):
    # Basic statistics
    loans = Loan.objects.all()
    total_loans = loans.count()
    total_amount = loans.aggregate(Sum('amount'))['amount__sum'] or 0
    active_loans = loans.filter(status='ACTIVE').count()
    active_amount = loans.filter(status='ACTIVE').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Payment statistics
    payments = Payment.objects.all()
    total_payments = payments.count()
    total_collected = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Calculate total outstanding (simplified for SQLite compatibility)
    active_loans_total = loans.filter(status='ACTIVE').aggregate(
        total_payable=Sum('total_payable')
    )['total_payable'] or 0
    
    active_loans_paid = loans.filter(status='ACTIVE').annotate(
        paid=Sum('payments__amount')
    ).aggregate(
        total_paid=Sum('paid')
    )['total_paid'] or 0
    
    total_outstanding = active_loans_total - active_loans_paid

    # Status distribution
    status_distribution = loans.values('status').annotate(count=Count('id'))
    status_labels = []
    status_data = []
    for item in status_distribution:
        status_labels.append(item['status'].capitalize())
        status_data.append(item['count'])

    # Monthly applications (last 12 months)
    twelve_months_ago = datetime.now() - timedelta(days=365)
    monthly_apps = (
        loans.filter(application_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('application_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    
    monthly_labels = []
    monthly_data = []
    for item in monthly_apps:
        monthly_labels.append(item['month'].strftime('%b %Y'))
        monthly_data.append(item['count'])

    # Loan type analysis
    loan_type_analysis = []
    for loan_type in LoanType.objects.all():
        type_loans = loans.filter(loan_type=loan_type)
        total_type_loans = type_loans.count()
        if total_type_loans > 0:
            total_amount = type_loans.aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            avg_amount = type_loans.aggregate(
                avg=Avg('amount')
            )['avg'] or 0
            
            analysis = {
                'name': loan_type.name,
                'total_loans': total_type_loans,
                'total_amount': total_amount,
                'avg_amount': avg_amount,
                'active_loans': type_loans.filter(status='ACTIVE').count(),
                'success_rate': (type_loans.filter(
                    status__in=['ACTIVE', 'CLOSED']).count() / total_type_loans) * 100
            }
            loan_type_analysis.append(analysis)

    context = {
        'total_loans': total_loans,
        'total_amount': total_amount,
        'active_loans': active_loans,
        'active_amount': active_amount,
        'total_payments': total_payments,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'status_labels': json.dumps(status_labels),
        'status_data': status_data,
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_data': monthly_data,
        'loan_type_analysis': loan_type_analysis,
    }
    
    return render(request, 'loan/reports.html', context)
