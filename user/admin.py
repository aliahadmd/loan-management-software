from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'employment_status', 'monthly_income')
    search_fields = ('user__username', 'user__email', 'national_id')
    list_filter = ('employment_status',)
