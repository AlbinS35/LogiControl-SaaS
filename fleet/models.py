from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError


# ─────────────────────────────────────────────
#  COMPANY  (multi-tenant root)
# ─────────────────────────────────────────────
class Company(models.Model):
    name = models.CharField(max_length=255)
    subscription_tier = models.CharField(max_length=50, default='basic')
    is_active = models.BooleanField(default=True)

    # Organization Details
    gstin = models.CharField(max_length=50, null=True, blank=True)
    default_currency = models.CharField(max_length=10, default='INR')
    registered_address = models.TextField(null=True, blank=True)

    # Notification Preferences
    alert_expiring_docs = models.BooleanField(default=True)
    alert_maintenance = models.BooleanField(default=True)
    alert_trip_assignment = models.BooleanField(default=False)
    alert_fuel_approvals = models.BooleanField(default=True)

    # Compliance Thresholds
    doc_expiry_lead_time = models.IntegerField(
        default=15,
        help_text="Days before expiry to trigger an alert"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  USER  (Admin / Manager / Driver)
# ─────────────────────────────────────────────
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'SaaS Admin'),
        ('manager', 'Company Manager'),
        ('driver', 'Driver'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='driver')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        null=True, blank=True, related_name='users'
    )

    # Driver-specific
    date_of_birth = models.DateField(null=True, blank=True)
    driving_license = models.CharField(max_length=50, null=True, blank=True)
    experience_years = models.IntegerField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    # Profile & Preferences
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    appearance_mode = models.CharField(max_length=10, default='light')
    platform_language = models.CharField(max_length=20, default='English (India)')

    # Invitation flow for drivers
    invitation_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    invitation_accepted = models.BooleanField(default=False)

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role == 'manager'

    def is_driver(self):
        return self.role == 'driver'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


# ─────────────────────────────────────────────
#  VEHICLE  (with Document Vault)
# ─────────────────────────────────────────────
class Vehicle(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('maintenance', 'In Maintenance'),
        ('inactive', 'Inactive'),
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        null=True, blank=True, related_name='vehicles'
    )
    registration_number = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.IntegerField()
    current_odometer = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Document Vault
    rc_document = models.FileField(upload_to='documents/rc/', null=True, blank=True)
    rc_expiry = models.DateField(null=True, blank=True)
    fitness_certificate = models.FileField(upload_to='documents/fitness/', null=True, blank=True)
    fitness_expiry = models.DateField(null=True, blank=True)
    insurance_policy = models.FileField(upload_to='documents/insurance/', null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    puc_certificate = models.FileField(upload_to='documents/puc/', null=True, blank=True)
    puc_expiry = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.registration_number} – {self.make} {self.model}"

    def expiring_docs(self, lead_days=None):
        """Return list of document names expiring within lead_days."""
        if lead_days is None:
            lead_days = self.company.doc_expiry_lead_time if self.company else 15
        threshold = timezone.now().date() + timezone.timedelta(days=lead_days)
        expiring = []
        for doc_name, expiry_field in [
            ('RC', self.rc_expiry),
            ('Fitness Certificate', self.fitness_expiry),
            ('Insurance', self.insurance_expiry),
            ('PUC', self.puc_expiry),
        ]:
            if expiry_field and expiry_field <= threshold:
                expiring.append((doc_name, expiry_field))
        return expiring


# ─────────────────────────────────────────────
#  TRIP  (with Odometer Validation)
# ─────────────────────────────────────────────
class Trip(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        null=True, blank=True, related_name='trips'
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='trips')
    driver = models.ForeignKey(
        User, on_delete=models.CASCADE,
        limit_choices_to={'role': 'driver'}, related_name='trips',
        null=True, blank=True
    )
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    goods_type = models.CharField(max_length=100, null=True, blank=True)
    goods_name = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Schedule
    scheduled_departure = models.DateTimeField(null=True, blank=True)
    scheduled_arrival = models.DateTimeField(null=True, blank=True)

    # Odometer readings
    start_odometer = models.IntegerField(null=True, blank=True)
    end_odometer = models.IntegerField(null=True, blank=True)

    # Driver trip logs
    fuel_level = models.CharField(max_length=50, null=True, blank=True)
    maintenance_notes = models.TextField(null=True, blank=True)

    # Digital Paperwork
    fuel_receipt = models.ImageField(upload_to='receipts/fuel/', null=True, blank=True)
    toll_receipt = models.ImageField(upload_to='receipts/toll/', null=True, blank=True)

    # Checklists
    pre_trip_check = models.BooleanField(default=False)

    # Financials
    fuel_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    toll_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fuel_approved = models.BooleanField(default=False)
    toll_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Odometer validation: end must exceed start."""
        if (
            self.status == 'completed'
            and self.end_odometer is not None
            and self.start_odometer is not None
        ):
            if self.end_odometer <= self.start_odometer:
                raise ValidationError(
                    "End odometer reading must be greater than start odometer reading."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Trip #{self.id}: {self.start_location} → {self.end_location} ({self.status})"


# ─────────────────────────────────────────────
#  EXPENSE  (Fuel / Toll bills)
# ─────────────────────────────────────────────
class Expense(models.Model):
    TYPE_CHOICES = (
        ('fuel', 'Fuel'),
        ('toll', 'Toll'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        related_name='expenses'
    )
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE,
        related_name='expenses', null=True, blank=True
    )
    driver = models.ForeignKey(
        User, on_delete=models.CASCADE,
        limit_choices_to={'role': 'driver'}, related_name='expenses'
    )
    expense_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='fuel')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_image = models.ImageField(upload_to='receipts/expenses/', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_expenses'
    )

    def __str__(self):
        return f"{self.expense_type.title()} – ₹{self.amount} ({self.status})"


# ─────────────────────────────────────────────
#  PAYROLL
# ─────────────────────────────────────────────
class Payroll(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE,
        null=True, blank=True, related_name='payrolls'
    )
    driver = models.ForeignKey(
        User, on_delete=models.CASCADE,
        limit_choices_to={'role': 'driver'}
    )
    month = models.DateField(help_text="First day of the payroll month")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trip_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expense_reimbursement = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=(('pending', 'Pending'), ('paid', 'Paid')),
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payroll – {self.driver.username} ({self.month.strftime('%b %Y')})"


# ─────────────────────────────────────────────
#  ALERT  (Document Expiry / Maintenance)
# ─────────────────────────────────────────────
class Alert(models.Model):
    ALERT_TYPE_CHOICES = (
        ('doc_expiry', 'Document Expiry'),
        ('maintenance', 'Maintenance Request'),
        ('trip_assigned', 'Trip Assigned'),
        ('fuel_approval', 'Fuel Bill Approval'),
        ('panic', 'Emergency / SOS'),
    )
    STATUS_CHOICES = (
        ('unread', 'Unread'),
        ('read', 'Read'),
        ('resolved', 'Resolved'),
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='alerts'
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE,
        null=True, blank=True, related_name='alerts'
    )
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE,
        null=True, blank=True, related_name='alerts'
    )
    raised_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='raised_alerts'
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.alert_type}] {self.message[:60]}"
