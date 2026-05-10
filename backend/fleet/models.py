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

    # Driver-specific onboarding & documents
    LICENSE_CHOICES = (
        ('LMV', 'Light Motor Vehicle (LMV)'),
        ('HMV', 'Heavy Motor Vehicle (HMV)'),
        ('Trailer', 'HPMV/HGMV with Trailer Endorsement'),
    )
    license_type = models.CharField(max_length=20, choices=LICENSE_CHOICES, null=True, blank=True)
    hazmat_certified = models.BooleanField(default=False)
    aadhaar_number = models.CharField(max_length=20, null=True, blank=True)
    badge_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Document Vault for Drivers
    dl_front = models.FileField(upload_to='documents/driver/dl/', null=True, blank=True)
    dl_back = models.FileField(upload_to='documents/driver/dl/', null=True, blank=True)
    dl_expiry = models.DateField(null=True, blank=True)
    medical_certificate = models.FileField(upload_to='documents/driver/medical/', null=True, blank=True)
    medical_expiry = models.DateField(null=True, blank=True)
    police_verification = models.FileField(upload_to='documents/driver/police/', null=True, blank=True)
    police_verification_expiry = models.DateField(null=True, blank=True)
    requires_password_change = models.BooleanField(default=False)

    # Financial
    contract_salary = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Monthly base salary (INR) — set by manager"
    )

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role == 'manager'

    def is_driver(self):
        return self.role == 'driver'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.role == 'driver' and getattr(self, 'company', None):
            from django.utils import timezone
            if getattr(self, 'dl_expiry', None):
                threshold = timezone.now().date() + timezone.timedelta(days=self.company.doc_expiry_lead_time)
                if self.dl_expiry <= threshold:
                    Alert.objects.get_or_create(
                        company=self.company,
                        alert_type='doc_expiry',
                        message=f"Driving License for {self.get_full_name() or self.username} is expiring on {self.dl_expiry.strftime('%Y-%m-%d')}.",
                        defaults={'status': 'unread'}
                    )

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

    VEHICLE_TYPE_CHOICES = (
        ('lmv', 'Light Goods Vehicle / LMV (< 7.5t)'),
        ('mhv', 'Medium Heavy Vehicle'),
        ('torus', 'Torus'),
        ('multi_axle', 'Multi Axle Truck'),
        ('trailer', 'Trailer'),
        ('other', 'Other'),
    )
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default='other')
    loading_capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Capacity in tons")

    # Document Vault
    rc_document = models.FileField(upload_to='documents/rc/', null=True, blank=True)
    rc_expiry = models.DateField(null=True, blank=True)
    fitness_certificate = models.FileField(upload_to='documents/fitness/', null=True, blank=True)
    fitness_expiry = models.DateField(null=True, blank=True)
    insurance_policy = models.FileField(upload_to='documents/insurance/', null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    puc_certificate = models.FileField(upload_to='documents/puc/', null=True, blank=True)
    puc_expiry = models.DateField(null=True, blank=True)

    # Telemetry Data
    current_latitude  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    current_speed     = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, help_text="Speed in km/h")
    current_heading   = models.CharField(max_length=20, null=True, blank=True, help_text="e.g. North-East")
    last_location_update = models.DateTimeField(null=True, blank=True)

    # Vehicle Health Metrics (0-100, updated by IoT or manual entry)
    engine_performance = models.PositiveSmallIntegerField(default=92, help_text="Engine score 0-100")
    tire_integrity     = models.PositiveSmallIntegerField(default=96, help_text="Tyre score 0-100")
    battery_life       = models.PositiveSmallIntegerField(default=54, help_text="Battery score 0-100")
    engine_compression = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="PSI")
    tire_pressure      = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Bar")

    def __str__(self):
        return f"{self.registration_number} – {self.make} {self.model}"

    def expiring_docs(self, lead_days=None):
        """Return list of document names expiring within lead_days."""
        if lead_days is None:
            lead_days = self.company.doc_expiry_lead_time if self.company else 15
        from django.utils import timezone
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
    total_distance_km = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Planned route distance in kilometres"
    )

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
    bonus_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Trip completion bonus awarded by manager (INR)"
    )
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
#  FUEL ENTRY  (Driver Fuel Registry)
# ─────────────────────────────────────────────
class FuelEntry(models.Model):
    STATUS_CHOICES = [
        ('PENDING',  'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    driver  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fuel_entries')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='fuel_entries')
    trip    = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='fuel_entries')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='fuel_entries')

    station_name      = models.CharField(max_length=255)
    volume_liters     = models.DecimalField(max_digits=10, decimal_places=2)
    cost_per_liter    = models.DecimalField(max_digits=8,  decimal_places=2, null=True, blank=True)
    total_cost        = models.DecimalField(max_digits=10, decimal_places=2)
    odometer_at_fill  = models.IntegerField(help_text='Odometer reading at the time of filling (km)')
    receipt_image     = models.ImageField(upload_to='receipts/fuel_entries/', null=True, blank=True)
    status            = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    notes             = models.TextField(null=True, blank=True)

    timestamp  = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_fuel_entries'
    )

    class Meta:
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        # Auto-calculate cost_per_liter if not supplied
        if self.volume_liters and self.total_cost and not self.cost_per_liter:
            self.cost_per_liter = round(float(self.total_cost) / float(self.volume_liters), 2)
        # Update vehicle odometer
        if self.vehicle and self.odometer_at_fill:
            if self.odometer_at_fill > self.vehicle.current_odometer:
                self.vehicle.current_odometer = self.odometer_at_fill
                self.vehicle.save(update_fields=['current_odometer'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Fuel – {self.station_name} | {self.volume_liters}L | ₹{self.total_cost} ({self.status})"


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


# ─────────────────────────────────────────────
#  MAINTENANCE RECORD  (Vehicle service log)
# ─────────────────────────────────────────────
class MaintenanceRecord(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('routine',   'Routine Service'),
        ('repair',    'Breakdown Repair'),
        ('tyre',      'Tyre Replacement'),
        ('oil',       'Oil Change'),
        ('brake',     'Brake Service'),
        ('electrical','Electrical Repair'),
        ('bodywork',  'Bodywork / Denting'),
        ('other',     'Other'),
    ]
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress','In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    company   = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='maintenance_records')
    vehicle   = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='maintenance_records')
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reported_maintenance'
    )

    service_type  = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='routine')
    description   = models.TextField()
    garage_name   = models.CharField(max_length=255, null=True, blank=True)
    cost          = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    odometer_at_service = models.IntegerField(null=True, blank=True)
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='scheduled')

    scheduled_date  = models.DateField(null=True, blank=True)
    completed_date  = models.DateField(null=True, blank=True)
    next_service_due= models.DateField(null=True, blank=True, help_text='Recommended next service date')

    invoice_image   = models.ImageField(upload_to='maintenance/invoices/', null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_service_type_display()} – {self.vehicle.registration_number} ({self.status})"


# ─────────────────────────────────────────────
#  MAINTENANCE LOG  (Manager-entered; linked to Driver Health view)
# ─────────────────────────────────────────────
class MaintenanceLog(models.Model):
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('UPCOMING',  'Upcoming'),
        ('OVERDUE',   'Overdue'),
    ]

    vehicle               = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='maintenance_logs')
    company               = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='maintenance_logs')
    service_type          = models.CharField(max_length=100, help_text="e.g. Engine Tune-up, Tire Rotation")
    last_service_date     = models.DateField()
    next_scheduled_check  = models.DateField()
    technician            = models.CharField(max_length=100)
    status                = models.CharField(max_length=10, choices=STATUS_CHOICES, default='UPCOMING')
    notes                 = models.TextField(blank=True)
    created_by            = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_logs_created'
    )
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_service_date']

    def __str__(self):
        return f"{self.service_type} — {self.vehicle.registration_number} [{self.status}]"

    def save(self, *args, **kwargs):
        """Auto-derive status from dates if not explicitly set by manager."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.status not in ('COMPLETED',):
            if self.next_scheduled_check < today:
                self.status = 'OVERDUE'
            else:
                self.status = 'UPCOMING'
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
#  LOGILOOP EXCHANGE (Cross-Tenant Backhaul)
# ─────────────────────────────────────────────
class GlobalLoadPool(models.Model):
    """Loads published by tenants for other companies to pick up."""
    SHARING_CHOICES = [
        ('PRIVATE', 'Internal Only'),
        ('PUBLIC', 'All Tenants'),
        ('PARTNER', 'Trusted Only')
    ]
    
    origin_company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='offered_loads')
    cargo_type = models.CharField(max_length=100) # e.g., 'Granite', 'Vegetables'
    weight_tons = models.DecimalField(max_digits=5, decimal_places=2)
    required_vehicle_type = models.CharField(max_length=50) # e.g., 'torus', 'trailer'
    origin_lat = models.FloatField()
    origin_lon = models.FloatField()
    destination_lat = models.FloatField()
    destination_lon = models.FloatField()
    visibility = models.CharField(max_length=10, choices=SHARING_CHOICES, default='PRIVATE')
    is_fulfilled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cargo_type} ({self.weight_tons}t) from {self.origin_company.name}"


class LinkedTrip(models.Model):
    """Binds outgoing and return legs into a single 'Profitability Loop'."""
    SETTLEMENT_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid')
    ]
    
    outbound_trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name='return_leg_binding')
    return_trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True, related_name='outbound_leg_binding')
    
    # Financial Aggregation
    combined_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_estimated_fuel_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # For Cross-Tenant matches
    settlement_status = models.CharField(max_length=20, choices=SETTLEMENT_CHOICES, default='PENDING')

    def calculate_loop_roi(self):
        """Calculates if the total circuit is profitable."""
        return float(self.combined_revenue) - float(self.total_estimated_fuel_cost)

    def __str__(self):
        return f"Linked Loop: Trip #{self.outbound_trip.id} + #{self.return_trip.id if self.return_trip else 'None'}"


class GlobalSettings(models.Model):
    """SaaS Admin Configuration for the LogiLoop Exchange."""
    exchange_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Standard Rate (%)")
    heavy_asset_commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=3.00, help_text="Heavy Asset Rate (%)")
    flat_transaction_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Flat Fee per Transaction")
    enable_cross_tenant_matching = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Global Setting"
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "LogiControl Global Settings"
