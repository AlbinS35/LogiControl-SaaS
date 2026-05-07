from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Company, User, Vehicle, Trip, Payroll, Expense, Alert


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_tier', 'gstin', 'doc_expiry_lead_time', 'created_at')
    search_fields = ('name', 'gstin')
    list_filter = ('subscription_tier',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('LogiTracker Profile', {
            'fields': ('role', 'company', 'phone_number', 'date_of_birth',
                       'driving_license', 'experience_years', 'profile_picture',
                       'invitation_token', 'invitation_accepted')
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('LogiTracker Profile', {
            'fields': ('role', 'company', 'phone_number')
        }),
    )
    list_display = ('username', 'get_full_name', 'role', 'company', 'email', 'is_active')
    list_filter = ('role', 'company', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'make', 'model', 'year', 'status', 'company', 'current_odometer')
    list_filter = ('status', 'company')
    search_fields = ('registration_number', 'make', 'model')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_location', 'end_location', 'driver', 'vehicle', 'status', 'company', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('start_location', 'end_location', 'driver__username')
    date_hierarchy = 'created_at'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ('driver', 'month', 'base_salary', 'trip_bonus', 'total_paid', 'status', 'company')
    list_filter = ('status', 'company')
    search_fields = ('driver__username', 'driver__first_name')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('driver', 'expense_type', 'amount', 'status', 'company', 'submitted_at')
    list_filter = ('status', 'expense_type', 'company')
    search_fields = ('driver__username',)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('alert_type', 'company', 'vehicle', 'status', 'created_at')
    list_filter = ('alert_type', 'status', 'company')
    search_fields = ('message',)
