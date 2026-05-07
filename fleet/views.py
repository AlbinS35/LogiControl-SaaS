from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import timedelta
import uuid

from .models import Vehicle, Trip, User, Company, Payroll, Alert, Expense
from .forms import (
    TripDriverUpdateForm, TripApprovalForm, TripCreateForm,
    VehicleForm, DriverForm, OwnerSignupForm,
)


# ══════════════════════════════════════════════════════════
#  ROLE DECORATORS
# ══════════════════════════════════════════════════════════

def admin_required(function=None):
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_admin(),
        login_url='/login/'
    )
    return actual_decorator(function) if function else actual_decorator


def manager_required(function=None):
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and (u.is_manager() or u.is_admin()),
        login_url='/login/'
    )
    return actual_decorator(function) if function else actual_decorator


def driver_required(function=None):
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.is_driver(),
        login_url='/login/'
    )
    return actual_decorator(function) if function else actual_decorator


# ══════════════════════════════════════════════════════════
#  AUTH – Login redirect + signup
# ══════════════════════════════════════════════════════════

def home(request):
    """Public landing page."""
    return render(request, 'home.html')


def pricing(request):
    return render(request, 'pricing.html')


def resources(request):
    return render(request, 'resources.html')


@login_required
def dashboard_redirect(request):
    if request.user.is_admin():
        return redirect('admin_dashboard')
    elif request.user.is_manager():
        return redirect('manager_dashboard')
    elif request.user.is_driver():
        return redirect('driver_dashboard')
    return redirect('login')


def owner_signup(request):
    """Self-service registration for Company Owners (Managers)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = OwnerSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='fleet.backends.RoleBasedBackend')
        messages.success(request, f"Welcome to LogiTracker, {user.first_name}! Your company account is ready.")
        return redirect('manager_dashboard')

    return render(request, 'registration/signup.html', {'form': form})


# ══════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════

@login_required
@admin_required
def admin_dashboard(request):
    vehicles = Vehicle.objects.select_related('company')
    drivers = User.objects.filter(role='driver').select_related('company')
    trips = Trip.objects.select_related('vehicle', 'driver').order_by('-created_at')
    companies = Company.objects.annotate(
        vehicle_count=Count('vehicles', distinct=True),
        user_count=Count('users', distinct=True)
    )
    managers = User.objects.filter(role='manager').select_related('company')
    maintenance_vehicles = vehicles.filter(status='maintenance')
    unread_alerts = Alert.objects.filter(status='unread').select_related('vehicle', 'company')

    total_vehicles = vehicles.count()
    total_drivers = drivers.count()
    active_trips = trips.filter(status='in_progress').count()
    completed_trips = trips.filter(status='completed').count()
    total = trips.count()
    delivery_rate = round((completed_trips / total * 100), 1) if total > 0 else 0

    context = {
        'total_vehicles': total_vehicles,
        'total_drivers': total_drivers,
        'active_trips': active_trips,
        'delivery_rate': delivery_rate,
        'maintenance_alerts': maintenance_vehicles.count(),
        'recent_trips': trips[:10],
        'maintenance_vehicles': maintenance_vehicles[:5],
        'companies': companies[:8],
        'managers': managers[:5],
        'all_vehicles': vehicles[:10],
        'unread_alerts': unread_alerts[:10],
        'total_companies': companies.count(),
    }
    return render(request, 'fleet/admin_dashboard.html', context)

@login_required
@admin_required
def admin_tenant_management(request):
    companies = Company.objects.annotate(
        vehicle_count=Count('vehicles', distinct=True),
        user_count=Count('users', distinct=True)
    )
    return render(request, 'fleet/admin_tenant_management.html', {'companies': companies})

@login_required
@admin_required
def admin_tenant_action(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        company_id = request.POST.get('company_id')
        
        if action == 'add':
            name = request.POST.get('name')
            subscription_tier = request.POST.get('subscription_tier', 'basic')
            if name:
                Company.objects.create(name=name, subscription_tier=subscription_tier)
                messages.success(request, f"Tenant {name} created successfully.")
            else:
                messages.error(request, "Company name is required.")
        else:
            company = get_object_or_404(Company, id=company_id)
            if action == 'delete':
                company.delete()
                messages.success(request, "Tenant deleted.")
            elif action == 'suspend':
                company.is_active = not company.is_active
                company.save()
                status_str = "reactivated" if company.is_active else "suspended"
                messages.success(request, f"Tenant {status_str}.")
            elif action == 'edit':
                company.name = request.POST.get('name', company.name)
                company.subscription_tier = request.POST.get('subscription_tier', company.subscription_tier)
                company.save()
                messages.success(request, "Tenant updated.")

    return redirect(request.META.get('HTTP_REFERER', 'admin_tenant_management'))

@login_required
@admin_required
def admin_subscriptions(request):
    query = request.GET.get('q', '')
    companies = Company.objects.annotate(
        vehicle_count=Count('vehicles', distinct=True),
        user_count=Count('users', distinct=True)
    )
    
    if query:
        companies = companies.filter(Q(name__icontains=query) | Q(id__icontains=query))
        
    total_mrr = 0
    for c in companies:
        if c.subscription_tier == 'enterprise':
            total_mrr += 50000
        elif c.subscription_tier == 'pro':
            total_mrr += 16500
        else:
            total_mrr += 4000
    total_mrr_formatted = f"${total_mrr / 1000000:.2f}M" if total_mrr > 1000000 else f"${total_mrr/1000:.1f}k" if total_mrr > 0 else "$0"
    
    return render(request, 'fleet/admin_subscriptions.html', {
        'companies': companies,
        'active_subs': companies.count(),
        'total_mrr': total_mrr_formatted
    })

@login_required
@admin_required
def admin_api_integration(request):
    integrations = [
        {"name": "Google Maps API", "type": "Routing & Distance", "status": "Operational", "latency": "42ms", "uptime": "99.99%", "status_cls": "active"},
        {"name": "FASTag NETC Gateway", "type": "Toll Payments", "status": "Operational", "latency": "120ms", "uptime": "99.95%", "status_cls": "active"},
        {"name": "Razorpay Subscriptions", "type": "Billing", "status": "Operational", "latency": "85ms", "uptime": "100%", "status_cls": "active"},
        {"name": "Vahan Registry (Gov)", "type": "Compliance Verification", "status": "Degraded", "latency": "850ms", "uptime": "98.50%", "status_cls": "warning"},
    ]
    return render(request, 'fleet/admin_api_integration.html', {"integrations": integrations})

@login_required
@admin_required
def admin_support_tickets(request):
    status_filter = request.GET.get('status', 'all').lower()
    
    all_tickets = [
        {"id": "TK-9921", "subject": "API Rate Limit Exceeded on Routing", "tenant": "Global Freight Inc.", "priority": "High", "status": "Open", "time": "10 mins ago", "status_cls": "open", "priority_cls": "high"},
        {"id": "TK-9920", "subject": "Billing issue on Pro Plan upgrade", "tenant": "Apex Logistics", "priority": "Medium", "status": "Open", "time": "2 hours ago", "status_cls": "open", "priority_cls": "medium"},
        {"id": "TK-9919", "subject": "Unable to add new vehicles to fleet", "tenant": "FastTrack Express", "priority": "High", "status": "Resolved", "time": "1 day ago", "status_cls": "resolved", "priority_cls": "high"},
        {"id": "TK-9918", "subject": "Custom reporting fields request", "tenant": "Horizon Shipping", "priority": "Low", "status": "In Progress", "time": "2 days ago", "status_cls": "in-progress", "priority_cls": "low"},
    ]
    
    if status_filter != 'all':
        tickets = [t for t in all_tickets if status_filter in t['status'].lower() or status_filter in t['status_cls']]
    else:
        tickets = all_tickets
        
    return render(request, 'fleet/admin_support_tickets.html', {"tickets": tickets, "current_status": status_filter})

@login_required
@admin_required
def admin_settings(request):
    if request.method == 'POST':
        messages.success(request, "Global settings updated successfully.")
        return redirect('admin_settings')
    return render(request, 'fleet/admin_settings.html')

# ══════════════════════════════════════════════════════════
#  MANAGER DASHBOARD
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def manager_dashboard(request):
    company = request.user.company
    today = timezone.now().date()
    thirty_days = today + timedelta(days=30)

    # Trip approval via POST
    if request.method == 'POST':
        trip_id = request.POST.get('trip_id')
        action = request.POST.get('action')
        trip = get_object_or_404(Trip, id=trip_id, company=company)
        if action == 'approve':
            trip.status = 'approved'
            trip.save()
            messages.success(request, f'Trip #{trip.id} approved.')
        elif action == 'reject':
            trip.status = 'rejected'
            trip.save()
            messages.warning(request, f'Trip #{trip.id} rejected.')
        elif action == 'approve_fuel':
            trip.fuel_approved = True
            trip.save()
            messages.success(request, f'Fuel bill for Trip #{trip.id} approved.')
        elif action == 'approve_toll':
            trip.toll_approved = True
            trip.save()
            messages.success(request, f'Toll bill for Trip #{trip.id} approved.')
        return redirect('manager_dashboard')

    pending_trips = Trip.objects.filter(status='pending', company=company)
    payrolls = Payroll.objects.filter(company=company).order_by('-month')[:5]

    expiring_vehicles = Vehicle.objects.filter(
        Q(rc_expiry__lte=thirty_days) |
        Q(fitness_expiry__lte=thirty_days) |
        Q(insurance_expiry__lte=thirty_days),
        company=company
    ).distinct()

    busy_drivers = Trip.objects.filter(status='in_progress', company=company).values_list('driver_id', flat=True)
    available_drivers = User.objects.filter(role='driver', company=company).exclude(id__in=busy_drivers)
    busy_vehicles = Trip.objects.filter(status='in_progress', company=company).values_list('vehicle_id', flat=True)
    available_vehicles = Vehicle.objects.filter(status='active', company=company).exclude(id__in=busy_vehicles)

    active_trips_list = Trip.objects.filter(
        status='in_progress', company=company
    ).select_related('driver', 'vehicle')[:5]

    unread_alerts = Alert.objects.filter(company=company, status='unread').order_by('-created_at')[:5]

    # Expense approvals
    pending_fuel_trips = Trip.objects.filter(
        company=company,
        fuel_amount__isnull=False,
        fuel_approved=False
    ).exclude(fuel_amount=0).select_related('driver', 'vehicle')[:5]

    context = {
        'pending_trips': pending_trips,
        'payrolls': payrolls,
        'expiring_vehicles': expiring_vehicles,
        'available_drivers': available_drivers,
        'available_vehicles': available_vehicles,
        'active_trips_list': active_trips_list,
        'active_trips_count': active_trips_list.count(),
        'maintenance_count': Vehicle.objects.filter(status='maintenance', company=company).count(),
        'today': today,
        'unread_alerts': unread_alerts,
        'pending_fuel_trips': pending_fuel_trips,
    }
    return render(request, 'fleet/manager_dashboard.html', context)


# ══════════════════════════════════════════════════════════
#  DRIVER DASHBOARD
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_dashboard(request):
    trips = Trip.objects.filter(driver=request.user).order_by('-created_at')
    active_trip = trips.filter(status__in=['approved', 'in_progress']).first()
    recent_alerts = Alert.objects.filter(
        raised_by=request.user, status='unread'
    ).order_by('-created_at')[:5]

    return render(request, 'fleet/driver_dashboard.html', {
        'trips': trips[:10],
        'active_trip': active_trip,
        'recent_alerts': recent_alerts,
    })


@login_required
@driver_required
def driver_action(request, trip_id, action):
    from .signals import raise_panic_alert, raise_maintenance_alert
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)

    if action == 'health_check':
        trip.pre_trip_check = True
        trip.save()
        messages.success(request, 'Pre-trip health check completed.')

    elif action == 'start':
        if trip.status == 'approved':
            trip.status = 'in_progress'
            trip.save()
            messages.success(request, 'Trip started. Safe driving!')

    elif action == 'panic':
        raise_panic_alert(trip, request.user)
        messages.error(request, '🚨 EMERGENCY ALERT SENT! Dispatch has been notified.')

    elif action == 'maintenance_alert':
        notes = request.POST.get('notes', 'No details provided.')
        raise_maintenance_alert(trip, request.user, notes)
        trip.vehicle.status = 'maintenance'
        trip.vehicle.save()
        messages.warning(request, 'Maintenance alert sent to your manager.')

    return redirect('driver_dashboard')


@login_required
@driver_required
def driver_trip_update(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)

    if request.method == 'POST':
        form = TripDriverUpdateForm(request.POST, request.FILES, instance=trip)
        if form.is_valid():
            updated_trip = form.save(commit=False)
            if 'complete_trip' in request.POST:
                # Validate odometer before completing
                if (
                    updated_trip.end_odometer
                    and updated_trip.start_odometer
                    and updated_trip.end_odometer <= updated_trip.start_odometer
                ):
                    messages.error(request, "End odometer must be greater than start odometer.")
                    return render(request, 'fleet/driver_trip_update.html', {'form': form, 'trip': trip})
                updated_trip.status = 'completed'
                # Update vehicle odometer
                if updated_trip.end_odometer:
                    updated_trip.vehicle.current_odometer = updated_trip.end_odometer
                    updated_trip.vehicle.save()
            elif trip.status == 'approved':
                updated_trip.status = 'in_progress'
            updated_trip.save()
            messages.success(request, 'Trip updated successfully.')
            return redirect('driver_dashboard')
    else:
        form = TripDriverUpdateForm(instance=trip)

    return render(request, 'fleet/driver_trip_update.html', {'form': form, 'trip': trip})


# ══════════════════════════════════════════════════════════
#  VEHICLE MANAGEMENT
# ══════════════════════════════════════════════════════════

@login_required
def vehicle_directory(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'fleet/vehicle_directory.html', {'vehicles': vehicles})


@login_required
@manager_required
def fleet_registry(request):
    company = request.user.company
    vehicles = Vehicle.objects.filter(company=company)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_vehicle':
            form = VehicleForm(request.POST, request.FILES)
            if form.is_valid():
                vehicle = form.save(commit=False)
                vehicle.company = company
                vehicle.save()
                messages.success(request, "Vehicle added successfully.")
            else:
                messages.error(request, "Error adding vehicle. Please check the form.")

        elif action == 'edit_vehicle':
            vehicle_id = request.POST.get('vehicle_id')
            vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
            form = VehicleForm(request.POST, request.FILES, instance=vehicle)
            if form.is_valid():
                form.save()
                messages.success(request, "Vehicle updated successfully.")
            else:
                messages.error(request, "Error updating vehicle.")

        elif action == 'delete_vehicle':
            vehicle_id = request.POST.get('vehicle_id')
            vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
            vehicle.delete()
            messages.success(request, "Vehicle deleted.")

        elif action == 'quick_upload':
            vehicle_id = request.POST.get('vehicle_id')
            doc_type = request.POST.get('doc_type')
            document = request.FILES.get('document')
            if vehicle_id and doc_type and document:
                vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
                field_map = {
                    'rc': 'rc_document', 'insurance': 'insurance_policy',
                    'puc': 'puc_certificate', 'fitness': 'fitness_certificate',
                }
                expiry_map = {
                    'rc': request.POST.get('rc_expiry'),
                    'insurance': request.POST.get('insurance_expiry'),
                    'puc': request.POST.get('puc_expiry'),
                    'fitness': request.POST.get('fitness_expiry'),
                }
                if doc_type in field_map:
                    setattr(vehicle, field_map[doc_type], document)
                    if expiry_map.get(doc_type):
                        setattr(vehicle, f"{doc_type}_expiry" if doc_type != 'insurance' else 'insurance_expiry', expiry_map[doc_type])
                    vehicle.save()
                    messages.success(request, f"Document uploaded for {vehicle.registration_number}.")
            else:
                messages.error(request, "Select vehicle, document type, and file.")

        return redirect('fleet_registry')

    today = timezone.now().date()
    total_vehicles = vehicles.count()
    valid_vehicles = vehicles.filter(
        Q(rc_expiry__gt=today) | Q(rc_expiry__isnull=True),
        Q(fitness_expiry__gt=today) | Q(fitness_expiry__isnull=True),
        Q(insurance_expiry__gt=today) | Q(insurance_expiry__isnull=True),
        Q(puc_expiry__gt=today) | Q(puc_expiry__isnull=True),
    ).count()
    expired_vehicles = total_vehicles - valid_vehicles
    compliance_pct = int(valid_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0

    context = {
        'vehicles': vehicles,
        'total_vehicles': total_vehicles,
        'valid_vehicles': valid_vehicles,
        'expired_vehicles': expired_vehicles,
        'compliance_percentage': compliance_pct,
        'today': today,
        'form': VehicleForm(),
    }
    return render(request, 'fleet/fleet_registry.html', context)


# ══════════════════════════════════════════════════════════
#  DRIVER MANAGEMENT (Manager side)
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def driver_directory(request):
    company = request.user.company
    drivers = User.objects.filter(role='driver', company=company)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_driver':
            form = DriverForm(request.POST)
            if form.is_valid():
                driver = form.save(commit=False)
                driver.role = 'driver'
                driver.company = company
                driver.username = f"drv_{uuid.uuid4().hex[:8]}"
                
                # Generate a random initial password
                import string
                import random
                from django.core.mail import send_mail
                
                raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                driver.set_password(raw_password)
                driver.save()
                
                if driver.email:
                    subject = 'Welcome to LogiControl Fleet Registry'
                    message = f"""Hello {driver.first_name},
                    
You have been successfully registered to the LogiControl Fleet Management System by your manager at {company.name}.

Your login credentials are:
Username: {driver.username}
Password: {raw_password}

Please log in and change your password as soon as possible.
"""
                    try:
                        send_mail(
                            subject,
                            message,
                            'noreply@logicontrol.in',
                            [driver.email],
                            fail_silently=False,
                        )
                        messages.success(request, f"Driver {driver.get_full_name()} onboarded. Login details sent to {driver.email}.")
                    except Exception as e:
                        messages.warning(request, f"Driver {driver.get_full_name()} onboarded, but email delivery failed.")
                else:
                    messages.success(request, f"Driver {driver.get_full_name()} onboarded successfully.")
            else:
                messages.error(request, "Error adding driver. Check form details.")

        elif action == 'edit_driver':
            driver_id = request.POST.get('driver_id')
            driver = get_object_or_404(User, id=driver_id, role='driver', company=company)
            form = DriverForm(request.POST, instance=driver)
            if form.is_valid():
                form.save()
                messages.success(request, "Driver updated.")
            else:
                messages.error(request, "Error updating driver.")

        elif action == 'delete_driver':
            driver_id = request.POST.get('driver_id')
            driver = get_object_or_404(User, id=driver_id, role='driver', company=company)
            driver.delete()
            messages.success(request, "Driver removed.")

        return redirect('driver_directory')

    import datetime
    today = datetime.date.today()
    busy_driver_ids = list(
        Trip.objects.filter(status='in_progress', company=company).values_list('driver_id', flat=True)
    )
    for d in drivers:
        d.computed_age = (
            today.year - d.date_of_birth.year
            - ((today.month, today.day) < (d.date_of_birth.month, d.date_of_birth.day))
        ) if d.date_of_birth else "N/A"
        d.computed_status = "On-Trip" if d.id in busy_driver_ids else "Active"

    context = {
        'drivers': drivers,
        'total_drivers': drivers.count(),
        'active_on_trip': len(busy_driver_ids),
        'scheduled_leave': 0,
        'form': DriverForm(),
    }
    return render(request, 'fleet/driver_directory.html', context)


# ══════════════════════════════════════════════════════════
#  TRIP ALLOCATION
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def trip_allocation(request):
    company = request.user.company

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_driver':
            trip_id = request.POST.get('trip_id')
            driver_id = request.POST.get('driver_id')
            trip = get_object_or_404(Trip, id=trip_id, company=company)
            driver = get_object_or_404(User, id=driver_id, role='driver', company=company)
            trip.driver = driver
            trip.status = 'approved'
            trip.save()
            Alert.objects.create(
                company=company,
                trip=trip,
                raised_by=request.user,
                alert_type='trip_assigned',
                message=f"New trip assigned: {trip.start_location} → {trip.end_location}.",
            )
            messages.success(request, f"Trip allocated to {driver.get_full_name() or driver.username}.")
            return redirect('trip_allocation')
        else:
            form = TripCreateForm(request.POST, company=company)
            if form.is_valid():
                trip = form.save(commit=False)
                trip.company = company
                if trip.driver:
                    trip.status = 'approved'
                    Alert.objects.create(
                        company=company,
                        trip=trip,
                        raised_by=request.user,
                        alert_type='trip_assigned',
                        message=f"New trip assigned: {trip.start_location} → {trip.end_location}.",
                    )
                else:
                    trip.status = 'pending'
                trip.save()
                messages.success(request, "Trip created successfully.")
                return redirect('trip_allocation')
            else:
                messages.error(request, "Please fix the errors below.")
    else:
        form = TripCreateForm(company=company)

    busy_drivers = Trip.objects.filter(status='in_progress', company=company).values_list('driver_id', flat=True)
    available_drivers = User.objects.filter(role='driver', company=company).exclude(id__in=busy_drivers)
    unassigned_trips = Trip.objects.filter(status='pending', company=company)

    context = {
        'form': form,
        'unassigned_trips': unassigned_trips,
        'available_drivers': available_drivers,
    }
    return render(request, 'fleet/trip_allocation.html', context)


# ══════════════════════════════════════════════════════════
#  ROUTE ANALYTICS
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def route_analytics(request):
    company = request.user.company
    active_trips = Trip.objects.filter(company=company, status='in_progress').select_related('vehicle')
    
    # Calculate distance for today's completed trips
    from django.utils import timezone
    from django.db.models import F, Sum
    today = timezone.now().date()
    completed_today = Trip.objects.filter(company=company, status='completed', updated_at__date=today)
    total_distance_qs = completed_today.aggregate(total=Sum(F('end_odometer') - F('start_odometer')))
    total_distance = total_distance_qs['total'] or 0

    critical_alerts = Alert.objects.filter(company=company, alert_type__in=['panic', 'maintenance']).order_by('-created_at')[:5]

    context = {
        'active_trips': active_trips,
        'total_distance': total_distance,
        'critical_alerts': critical_alerts,
        'avg_speed': 58,  # Hardcoded placeholder
    }
    return render(request, 'fleet/route_analytics.html', context)


@login_required
@manager_required
def export_route_analytics(request):
    import csv
    from django.http import HttpResponse
    company = request.user.company
    trips = Trip.objects.filter(company=company)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="route_analytics.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Trip ID', 'Vehicle', 'Driver', 'Start Location', 'End Location', 'Status', 'Distance (KM)'])
    
    for trip in trips:
        distance = ''
        if trip.end_odometer and trip.start_odometer:
            distance = trip.end_odometer - trip.start_odometer
        writer.writerow([
            trip.id, 
            trip.vehicle.registration_number, 
            trip.driver.get_full_name() or trip.driver.username, 
            trip.start_location, 
            trip.end_location, 
            trip.get_status_display(),
            distance
        ])
    return response


# ══════════════════════════════════════════════════════════
#  REVENUE / PAYROLL
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def revenue_dashboard(request):
    company = request.user.company
    status_filter = request.GET.get('status', 'all')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'pay_payroll':
            payroll_id = request.POST.get('payroll_id')
            payroll = get_object_or_404(Payroll, id=payroll_id, company=company)
            payroll.status = 'paid'
            payroll.save()
            messages.success(request, f"Payment processed for {payroll.driver.get_full_name() or payroll.driver.username}.")
        elif action == 'bulk_pay_payrolls':
            pending = Payroll.objects.filter(company=company, status='pending')
            count = pending.count()
            if count > 0:
                pending.update(status='paid')
                messages.success(request, f"Successfully processed {count} payments in bulk.")
            else:
                messages.warning(request, "No pending payments to process.")
        return redirect('revenue_dashboard')

    payrolls = Payroll.objects.filter(company=company, status='pending').select_related('driver')
    if status_filter != 'all':
        pass # In this dashboard we only show pending payments in the main table
        
    paid_payrolls = Payroll.objects.filter(company=company, status='paid').order_by('-created_at')[:5]
    total_pending = payrolls.aggregate(total=Sum('total_paid'))['total'] or 0

    context = {
        'pending_payrolls': payrolls,
        'paid_payrolls': paid_payrolls,
        'total_pending': total_pending,
    }
    return render(request, 'fleet/revenue.html', context)

@login_required
@manager_required
def export_revenue(request):
    import csv
    from django.http import HttpResponse
    company = request.user.company
    payrolls = Payroll.objects.filter(company=company).select_related('driver')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="revenue_payments.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Payroll ID', 'Driver', 'Month', 'Base Salary', 'Fuel Deductions', 'Toll Deductions', 'Total Paid', 'Status'])
    
    for p in payrolls:
        writer.writerow([
            p.id, 
            p.driver.get_full_name() or p.driver.username, 
            p.month.strftime('%Y-%m'), 
            p.base_salary, 
            p.fuel_deductions, 
            p.toll_deductions, 
            p.total_paid, 
            p.get_status_display()
        ])
    return response

@login_required
@manager_required
def export_receipt(request, payroll_id):
    from django.http import HttpResponse
    payroll = get_object_or_404(Payroll, id=payroll_id, company=request.user.company, status='paid')
    
    content = f"""==================================================
              PAYMENT RECEIPT
==================================================
Receipt ID: TXN_PAY_{payroll.id}
Date: {payroll.updated_at.strftime('%Y-%m-%d %H:%M:%S')}

Driver: {payroll.driver.get_full_name() or payroll.driver.username}
Company: {request.user.company.name}
Month: {payroll.month.strftime('%Y-%m')}

--------------------------------------------------
Base Salary:         Rs. {payroll.base_salary}
Fuel Deductions:     Rs. {payroll.fuel_deductions}
Toll Deductions:     Rs. {payroll.toll_deductions}
--------------------------------------------------
TOTAL PAID:          Rs. {payroll.total_paid}
==================================================
Status: PAID
"""
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="receipt_{payroll.id}.txt"'
    return response


# ══════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════

@login_required
def fleet_settings(request):
    company = request.user.company if hasattr(request.user, 'company') else None

    if request.method == 'POST':
        if 'first_name' in request.POST:
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.email = request.POST.get('email', '')
            request.user.phone_number = request.POST.get('phone_number', '')
            if request.FILES.get('profile_picture'):
                request.user.profile_picture = request.FILES['profile_picture']
            request.user.save()

        if 'appearance_mode' in request.POST:
            request.user.appearance_mode = request.POST.get('appearance_mode', 'light')
            request.user.platform_language = request.POST.get('platform_language', 'English (India)')
            request.user.save()

        if 'company_name' in request.POST and company:
            company.name = request.POST.get('company_name', company.name)
            company.gstin = request.POST.get('gstin', '')
            company.default_currency = request.POST.get('default_currency', 'INR')
            company.registered_address = request.POST.get('registered_address', '')
            company.alert_expiring_docs = request.POST.get('alert_expiring_docs') == 'on'
            company.alert_maintenance = request.POST.get('alert_maintenance') == 'on'
            company.alert_trip_assignment = request.POST.get('alert_trip_assignment') == 'on'
            company.alert_fuel_approvals = request.POST.get('alert_fuel_approvals') == 'on'
            lead_time = request.POST.get('doc_expiry_lead_time', '')
            if lead_time.isdigit():
                company.doc_expiry_lead_time = int(lead_time)
            company.save()

        messages.success(request, "Settings updated successfully.")
        return redirect('fleet_settings')

    return render(request, 'fleet/settings.html', {'company': company})


# ══════════════════════════════════════════════════════════
#  ALERTS API (mark as read)
# ══════════════════════════════════════════════════════════

@login_required
def mark_alert_read(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id, company=request.user.company)
    alert.status = 'read'
    alert.save()
    return redirect(request.META.get('HTTP_REFERER', 'manager_dashboard'))
