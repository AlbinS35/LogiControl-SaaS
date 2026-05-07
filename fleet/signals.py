"""
Django Signals for LogiTracker Fleet Management System.
- Fires document-expiry alerts daily (called from management command or Celery).
- Creates Alert records when vehicle docs are near expiry.
- Sends invitation email when a new Driver user is created by a manager.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import secrets


# ─────────────────────────────────────────────
#  1. Auto-generate invitation token for Drivers
# ─────────────────────────────────────────────
@receiver(pre_save, sender='fleet.User')
def generate_driver_invitation_token(sender, instance, **kwargs):
    """
    When a new Driver user is saved without an invitation token,
    generate a secure token so the manager can send an invite link.
    """
    if instance.pk is None and instance.role == 'driver':
        if not instance.invitation_token:
            instance.invitation_token = secrets.token_urlsafe(32)


@receiver(post_save, sender='fleet.User')
def send_driver_invitation_email(sender, instance, created, **kwargs):
    """
    After a new driver is created, send a welcome / invitation email.
    """
    if created and instance.role == 'driver' and instance.email:
        subject = f"Welcome to {instance.company.name if instance.company else 'LogiTracker'}!"
        body = (
            f"Hi {instance.get_full_name() or instance.username},\n\n"
            f"Your driver account has been created.\n"
            f"Username : {instance.username}\n"
            f"Password : Driver@123  (please change this immediately)\n\n"
            f"Login at: {settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://127.0.0.1:8000'}/login/\n\n"
            f"— LogiTracker Team"
        )
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [instance.email])
        except Exception:
            pass  # Email sending is best-effort; don't break user creation


# ─────────────────────────────────────────────
#  2. Document Expiry Alert Generator
#     Call fleet.signals.check_document_expiry() from a
#     management command or Celery task every 24 h.
# ─────────────────────────────────────────────
def check_document_expiry():
    """
    Scan every vehicle and create an Alert record if any document
    is expiring within the company's configured lead time.
    Avoids duplicate alerts by checking for existing unresolved ones.
    """
    from .models import Vehicle, Alert

    today = timezone.now().date()
    for vehicle in Vehicle.objects.select_related('company').exclude(company=None):
        lead_days = vehicle.company.doc_expiry_lead_time
        if not vehicle.company.alert_expiring_docs:
            continue

        for doc_name, expiry_date in vehicle.expiring_docs(lead_days):
            days_left = (expiry_date - today).days
            message = (
                f"Document '{doc_name}' for vehicle {vehicle.registration_number} "
                f"expires on {expiry_date.strftime('%d %b %Y')} "
                f"({'EXPIRED' if days_left < 0 else f'{days_left} days left'})."
            )
            # Avoid flooding – only create if no open alert for same vehicle+doc
            already_exists = Alert.objects.filter(
                company=vehicle.company,
                vehicle=vehicle,
                alert_type='doc_expiry',
                message__icontains=doc_name,
                status__in=['unread', 'read'],
            ).exists()
            if not already_exists:
                Alert.objects.create(
                    company=vehicle.company,
                    vehicle=vehicle,
                    alert_type='doc_expiry',
                    message=message,
                )


# ─────────────────────────────────────────────
#  3. Raise Alert on Panic / SOS from driver_action view
#     (called imperatively from views.py – not a signal)
# ─────────────────────────────────────────────
def raise_panic_alert(trip, driver):
    from .models import Alert
    Alert.objects.create(
        company=trip.company,
        vehicle=trip.vehicle,
        trip=trip,
        raised_by=driver,
        alert_type='panic',
        message=(
            f"🚨 EMERGENCY SOS from driver {driver.get_full_name() or driver.username} "
            f"on trip #{trip.id} ({trip.start_location} → {trip.end_location})."
        ),
    )


# ─────────────────────────────────────────────
#  4. Raise maintenance alert from driver One-Tap
# ─────────────────────────────────────────────
def raise_maintenance_alert(trip, driver, notes):
    from .models import Alert
    Alert.objects.create(
        company=trip.company,
        vehicle=trip.vehicle,
        trip=trip,
        raised_by=driver,
        alert_type='maintenance',
        message=(
            f"Maintenance issue reported by {driver.get_full_name() or driver.username} "
            f"for vehicle {trip.vehicle.registration_number}: {notes}"
        ),
    )
