from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError

class LoanType(models.Model):
    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    max_duration_months = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} ({self.interest_rate}%)"

class Loan(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
    ]

    borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    duration_months = models.PositiveIntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    purpose = models.TextField()
    application_date = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_payable = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Only calculate on creation
            self.interest_rate = self.loan_type.interest_rate
            # Calculate monthly payment using simple interest
            principal = self.amount
            rate = self.interest_rate / 100 / 12  # Monthly interest rate
            duration = self.duration_months
            
            # Monthly payment formula
            self.monthly_payment = (principal * (rate * (1 + rate)**duration)) / ((1 + rate)**duration - 1)
            self.total_payable = self.monthly_payment * duration

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Loan #{self.pk} - {self.borrower.username} ({self.status})"

    def approve_loan(self, approved_by):
        if self.status == 'PENDING':
            self.status = 'APPROVED'
            self.approved_date = timezone.now()
            self.save()
            
            # Create a notification or log entry
            LoanStatusHistory.objects.create(
                loan=self,
                old_status='PENDING',
                new_status='APPROVED',
                changed_by=approved_by
            )
            return True
        return False

    def reject_loan(self, rejected_by, reason):
        if self.status == 'PENDING':
            self.status = 'REJECTED'
            self.save()
            
            LoanStatusHistory.objects.create(
                loan=self,
                old_status='PENDING',
                new_status='REJECTED',
                changed_by=rejected_by,
                notes=reason
            )
            return True
        return False

    def activate_loan(self):
        if self.status == 'APPROVED':
            self.status = 'ACTIVE'
            self.save()
            return True
        return False

    def get_absolute_url(self):
        return reverse('loan_detail', kwargs={'pk': self.pk})

    def get_total_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    def get_remaining_balance(self):
        return self.total_payable - self.get_total_paid()

    def is_fully_paid(self):
        return self.get_remaining_balance() <= Decimal('0.00')

    def record_payment(self, amount, payment_method, transaction_id):
        if self.status != 'ACTIVE':
            raise ValidationError("Can only make payments for active loans")
        
        if amount > self.get_remaining_balance():
            raise ValidationError("Payment amount exceeds remaining balance")

        payment = Payment.objects.create(
            loan=self,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id
        )

        if self.is_fully_paid():
            self.status = 'CLOSED'
            self.save()

        return payment

class LoanStatusHistory(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=10)
    new_status = models.CharField(max_length=10)
    changed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHECK', 'Check'),
        ('MOBILE_MONEY', 'Mobile Money'),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payment_date']
