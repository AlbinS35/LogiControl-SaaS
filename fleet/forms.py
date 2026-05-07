from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Trip, Vehicle, Company

User = get_user_model()


# ─────────────────────────────────────────────
#  Trip forms
# ─────────────────────────────────────────────
class TripDriverUpdateForm(forms.ModelForm):
    """Driver fills in odometer, fuel level, receipts during/after trip."""

    class Meta:
        model = Trip
        fields = [
            'start_odometer', 'end_odometer',
            'fuel_level', 'fuel_amount',
            'toll_amount',
            'maintenance_notes',
            'fuel_receipt', 'toll_receipt',
            'pre_trip_check',
        ]
        widgets = {
            'maintenance_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'fuel_level': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3/4 full'}),
            'start_odometer': forms.NumberInput(attrs={'class': 'form-control'}),
            'end_odometer': forms.NumberInput(attrs={'class': 'form-control'}),
            'fuel_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'toll_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_odometer')
        end = cleaned_data.get('end_odometer')
        if start is not None and end is not None and end <= start:
            raise ValidationError(
                "End odometer reading must be greater than start odometer reading."
            )
        return cleaned_data


class TripApprovalForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ['status']


class TripCreateForm(forms.ModelForm):
    """Manager creates/allocates a trip."""

    class Meta:
        model = Trip
        fields = [
            'driver', 'vehicle',
            'start_location', 'end_location',
            'goods_type', 'goods_name',
            'scheduled_departure', 'scheduled_arrival',
        ]
        widgets = {
            'start_location': forms.TextInput(attrs={'class': 'form-control'}),
            'end_location': forms.TextInput(attrs={'class': 'form-control'}),
            'goods_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Perishable, Electronics'}),
            'goods_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. General Goods'}),
            'scheduled_departure': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'scheduled_arrival': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            # Restrict choices to the requesting manager's company
            busy_drivers = Trip.objects.filter(
                status='in_progress', company=company
            ).values_list('driver_id', flat=True)
            busy_vehicles = Trip.objects.filter(
                status='in_progress', company=company
            ).values_list('vehicle_id', flat=True)
            self.fields['driver'].queryset = User.objects.filter(
                role='driver', company=company
            ).exclude(id__in=busy_drivers)
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                status='active', company=company
            ).exclude(id__in=busy_vehicles)


# ─────────────────────────────────────────────
#  Vehicle form
# ─────────────────────────────────────────────
class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'registration_number', 'make', 'model', 'year', 'status',
            'rc_document', 'rc_expiry',
            'insurance_policy', 'insurance_expiry',
            'puc_certificate', 'puc_expiry',
            'fitness_certificate', 'fitness_expiry',
        ]
        widgets = {
            'registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'make': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'rc_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'insurance_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'puc_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fitness_expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


# ─────────────────────────────────────────────
#  Driver onboarding form (manager-side)
# ─────────────────────────────────────────────
class DriverForm(forms.ModelForm):
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email',
            'date_of_birth', 'driving_license',
            'experience_years', 'phone_number',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'driving_license': forms.TextInput(attrs={'class': 'form-control'}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ─────────────────────────────────────────────
#  Company Owner / Manager signup form
# ─────────────────────────────────────────────
class OwnerSignupForm(forms.Form):
    full_name = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your full name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'owner@company.com'})
    )
    phone_number = forms.CharField(
        max_length=15, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '98765 43210'})
    )
    company_name = forms.CharField(
        max_length=255, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter registered company name'})
    )
    gstin = forms.CharField(
        max_length=15, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '22AAAAA0000A1Z5'})
    )
    fleet_size = forms.ChoiceField(
        choices=[('', 'Select size'), ('1-10', '1–10 Vehicles'), ('11-50', '11–50 Vehicles'), ('51-200', '51–200 Vehicles'), ('200+', '200+ Vehicles')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(
        label="New Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )
    repeat_password = forms.CharField(
        label="Repeat Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            import re
            phone = re.sub(r'\D', '', phone)
            if len(phone) != 10:
                raise ValidationError("Phone number must be exactly 10 digits.")
        if User.objects.filter(username=phone).exists():
            raise ValidationError("An account with this phone number already exists.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_gstin(self):
        gstin = self.cleaned_data.get('gstin')
        if gstin:
            import re
            if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
                raise ValidationError("Invalid GSTIN format.")
        return gstin

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('repeat_password')
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self):
        """Create Company + Manager User atomically."""
        from django.db import transaction
        
        full_name = self.cleaned_data['full_name']
        names = full_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ''

        with transaction.atomic():
            company = Company.objects.create(
                name=self.cleaned_data['company_name'],
                gstin=self.cleaned_data.get('gstin', ''),
            )
            user = User.objects.create_user(
                username=self.cleaned_data['phone_number'],
                email=self.cleaned_data['email'],
                password=self.cleaned_data['password'],
                first_name=first_name,
                last_name=last_name,
                phone_number=self.cleaned_data['phone_number'],
                role='manager',
                company=company,
            )
        return user
