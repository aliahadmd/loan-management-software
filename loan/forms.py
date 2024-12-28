from django import forms
from .models import Loan, Payment, LoanType
from django.core.exceptions import ValidationError
import uuid

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['loan_type', 'amount', 'duration_months', 'purpose']
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 4}),
            'amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'duration_months': forms.NumberInput(attrs={'min': 1}),
        }
        help_texts = {
            'amount': 'Enter the loan amount you wish to borrow',
            'duration_months': 'Enter the duration in months',
            'purpose': 'Explain the purpose of the loan',
        }

    def clean(self):
        cleaned_data = super().clean()
        loan_type = cleaned_data.get('loan_type')
        amount = cleaned_data.get('amount')
        duration_months = cleaned_data.get('duration_months')

        if not loan_type or not amount or not duration_months:
            return cleaned_data

        # Validate amount range
        if amount < loan_type.min_amount:
            raise ValidationError({
                'amount': f'Amount must be at least ${loan_type.min_amount:,.2f} for {loan_type.name}'
            })
        if amount > loan_type.max_amount:
            raise ValidationError({
                'amount': f'Amount cannot exceed ${loan_type.max_amount:,.2f} for {loan_type.name}'
            })
        
        # Validate duration
        if duration_months > loan_type.max_duration_months:
            raise ValidationError({
                'duration_months': f'Duration cannot exceed {loan_type.max_duration_months} months for {loan_type.name}'
            })
        if duration_months < 1:
            raise ValidationError({
                'duration_months': 'Duration must be at least 1 month'
            })

        # Validate purpose
        purpose = cleaned_data.get('purpose', '').strip()
        if len(purpose) < 20:
            raise ValidationError({
                'purpose': 'Please provide a more detailed purpose (at least 20 characters)'
            })

        return cleaned_data

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'amount': 'Enter the payment amount',
            'payment_method': 'Select your payment method',
            'notes': 'Add any additional notes (optional)',
        }

    def __init__(self, *args, loan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loan = loan
        if loan:
            remaining = loan.get_remaining_balance()
            self.fields['amount'].help_text = f'Remaining balance: ${remaining:,.2f}'
            self.fields['amount'].widget.attrs['max'] = remaining

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or not self.loan:
            return amount

        if amount <= 0:
            raise ValidationError('Payment amount must be greater than zero')

        remaining = self.loan.get_remaining_balance()
        if amount > remaining:
            raise ValidationError(f'Payment amount cannot exceed the remaining balance (${remaining:,.2f})')

        return amount

    def save(self, commit=True):
        payment = super().save(commit=False)
        payment.loan = self.loan
        payment.transaction_id = str(uuid.uuid4())
        
        if commit:
            try:
                payment.save()
                # Check if loan is fully paid
                if payment.loan.is_fully_paid():
                    payment.loan.status = 'CLOSED'
                    payment.loan.save()
            except Exception as e:
                raise ValidationError(f'Error processing payment: {str(e)}')
                
        return payment 