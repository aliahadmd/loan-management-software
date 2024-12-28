from django.contrib import admin
from .models import LoanType, Loan, Payment

@admin.register(LoanType)
class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'min_amount', 'max_amount', 'max_duration_months')
    search_fields = ('name',)

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('id', 'borrower', 'loan_type', 'amount', 'status', 'application_date')
    list_filter = ('status', 'loan_type')
    search_fields = ('borrower__username', 'borrower__email')
    readonly_fields = ('monthly_payment', 'total_payable')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'loan', 'amount', 'payment_date', 'payment_method', 'transaction_id')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('transaction_id', 'loan__borrower__username')
