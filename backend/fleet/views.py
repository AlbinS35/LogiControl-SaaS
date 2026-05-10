from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from datetime import timedelta
import uuid

from .models import Vehicle, Trip, User, Company, Payroll, Alert, Expense, FuelEntry, MaintenanceRecord, MaintenanceLog
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


from django.views.decorators.cache import never_cache
from django.contrib.auth import logout as auth_logout

@never_cache
@login_required
def dashboard_redirect(request):
    if request.user.is_admin():
        return redirect('admin_dashboard')
    elif request.user.is_manager():
        return redirect('manager_dashboard')
    elif request.user.is_driver():
        return redirect('driver_dashboard')
    return redirect('login')

@never_cache
def custom_logout(request):
    """Ensure the user is fully logged out and session is cleared, even on GET for convenience or POST."""
    auth_logout(request)
    request.session.flush()
    response = redirect('home')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


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
    from .models import GlobalSettings, LinkedTrip
    settings_obj, created = GlobalSettings.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        if 'update_settings' in request.POST:
            settings_obj.exchange_commission_rate = request.POST.get('exchange_commission_rate', settings_obj.exchange_commission_rate)
            settings_obj.heavy_asset_commission_rate = request.POST.get('heavy_asset_commission_rate', settings_obj.heavy_asset_commission_rate)
            settings_obj.flat_transaction_fee = request.POST.get('flat_transaction_fee', settings_obj.flat_transaction_fee)
            settings_obj.enable_cross_tenant_matching = request.POST.get('enable_cross_tenant_matching') == 'on'
            settings_obj.save()
            messages.success(request, "Exchange Settings updated successfully.")
        elif 'mark_paid' in request.POST:
            trip_id = request.POST.get('linked_trip_id')
            trip = get_object_or_404(LinkedTrip, id=trip_id)
            trip.settlement_status = 'PAID'
            trip.save()
            messages.success(request, f"Settlement for Loop #{trip.id} marked as Paid.")
        return redirect('admin_settings')
        
    linked_trips = LinkedTrip.objects.select_related(
        'outbound_trip__company', 'return_trip__company'
    ).order_by('-id')
    
    return render(request, 'fleet/admin_settings.html', {
        'settings': settings_obj,
        'linked_trips': linked_trips
    })

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

    # Active (on-trip) drivers
    active_driver_ids = Trip.objects.filter(
        status__in=['in_progress', 'approved'], company=company
    ).exclude(driver__isnull=True).values_list('driver_id', flat=True)

    # All drivers for this company
    all_drivers = User.objects.filter(role='driver', company=company)
    active_drivers = all_drivers.filter(id__in=active_driver_ids)
    idle_drivers = all_drivers.exclude(id__in=active_driver_ids)

    # Maintenance vehicles
    maintenance_vehicles = Vehicle.objects.filter(status='maintenance', company=company)
    maintenance_count = maintenance_vehicles.count()

    # Pending trips (bills / vouchers to approve)
    pending_trips = Trip.objects.filter(status='pending', company=company)
    payrolls = Payroll.objects.filter(company=company).order_by('-month')[:5]

    expiring_vehicles = Vehicle.objects.filter(
        Q(rc_expiry__lte=thirty_days) |
        Q(fitness_expiry__lte=thirty_days) |
        Q(insurance_expiry__lte=thirty_days),
        company=company
    ).distinct()

    busy_vehicles = Trip.objects.filter(status='in_progress', company=company).values_list('vehicle_id', flat=True)
    available_vehicles = Vehicle.objects.filter(status='active', company=company).exclude(id__in=busy_vehicles)

    # Fleet status table (active + approved trips with driver info)
    active_trips_list = Trip.objects.filter(
        status__in=['in_progress', 'approved'], company=company
    ).select_related('driver', 'vehicle').order_by('-created_at')

    # Bill approvals — trips with pending fuel/toll receipts
    bill_approval_trips = Trip.objects.filter(
        company=company,
        fuel_approved=False,
        fuel_amount__isnull=False,
    ).exclude(fuel_amount=0).select_related('driver', 'vehicle').order_by('-updated_at')[:10]

    total_pending_amount = sum(
        (t.fuel_amount or 0) + (t.toll_amount or 0)
        for t in bill_approval_trips
    )

    unread_alerts = Alert.objects.filter(company=company, status='unread').order_by('-created_at')[:5]

    context = {
        'pending_trips': pending_trips,
        'payrolls': payrolls,
        'expiring_vehicles': expiring_vehicles,
        'active_drivers': active_drivers,
        'idle_drivers': idle_drivers,
        'all_drivers': all_drivers,
        'available_vehicles': available_vehicles,
        'active_trips_list': active_trips_list,
        'active_trips_count': Trip.objects.filter(status__in=['in_progress', 'approved'], company=company).count(),
        'maintenance_vehicles': maintenance_vehicles,
        'maintenance_count': maintenance_count,
        'bill_approval_trips': bill_approval_trips,
        'total_pending_amount': total_pending_amount,
        'today': today,
        'unread_alerts': unread_alerts,
    }
    return render(request, 'fleet/manager_dashboard.html', context)


# ══════════════════════════════════════════════════════════
#  DRIVER DASHBOARD
# ══════════════════════════════════════════════════════════

@login_required
def force_password_change(request):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.requires_password_change = False
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            if request.user.role == 'driver':
                return redirect('driver_dashboard')
            elif request.user.role == 'manager':
                return redirect('manager_dashboard')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'registration/password_change.html', {'form': form})

@login_required
@driver_required
def driver_dashboard(request):
    if getattr(request.user, 'requires_password_change', False):
        messages.info(request, "For your security, please change your temporary password to continue.")
        return redirect('password_change')

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
def vehicle_status_update(request, vehicle_id):
    """Quick status toggle for a vehicle (e.g. maintenance → active)."""
    if request.method == 'POST':
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=request.user.company)
        new_status = request.POST.get('status', 'active')
        if new_status in ['active', 'maintenance', 'inactive']:
            vehicle.status = new_status
            vehicle.save()
            messages.success(request, f"Vehicle {vehicle.registration_number} marked as {new_status}.")
        else:
            messages.error(request, "Invalid status.")
    return redirect('manager_dashboard')


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

        elif action == 'add_maintenance':
            vehicle_id = request.POST.get('vehicle_id')
            vehicle_obj = get_object_or_404(Vehicle, id=vehicle_id, company=company)
            description = request.POST.get('description', '').strip()
            if description:
                MaintenanceRecord.objects.create(
                    company=company,
                    vehicle=vehicle_obj,
                    reported_by=request.user,
                    service_type=request.POST.get('service_type', 'routine'),
                    description=description,
                    garage_name=request.POST.get('garage_name') or None,
                    cost=request.POST.get('cost') or None,
                    status=request.POST.get('status', 'scheduled'),
                    scheduled_date=request.POST.get('scheduled_date') or None,
                    invoice_image=request.FILES.get('invoice_image'),
                )
                messages.success(request, f"Maintenance record logged for {vehicle_obj.registration_number}.")
            else:
                messages.error(request, "Description is required to log a maintenance record.")

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

@login_required
@manager_required
def vehicle_fuel_insights(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=request.user.company)
    trips = Trip.objects.filter(vehicle=vehicle, status='completed').prefetch_related('fuel_entries').order_by('-updated_at')
    
    insights = []
    total_fuel_overall = 0
    total_money_overall = 0
    total_distance_overall = 0
    
    for trip in trips:
        entries = trip.fuel_entries.filter(status='APPROVED')
        total_fuel = sum(entry.volume_liters for entry in entries)
        total_money = sum(entry.total_cost for entry in entries)
        
        # Determine trip distance
        if trip.total_distance_km:
            dist = float(trip.total_distance_km)
        elif trip.end_odometer and trip.start_odometer:
            dist = float(trip.end_odometer - trip.start_odometer)
        else:
            dist = 0
            
        efficiency = (dist / float(total_fuel)) if total_fuel > 0 else 0
        
        insights.append({
            'trip': trip,
            'total_fuel': round(float(total_fuel), 2),
            'total_money': round(float(total_money), 2),
            'distance': dist,
            'efficiency': round(efficiency, 2)
        })
        
        total_fuel_overall += float(total_fuel)
        total_money_overall += float(total_money)
        total_distance_overall += dist
        
    overall_efficiency = (total_distance_overall / total_fuel_overall) if total_fuel_overall > 0 else 0
    
    context = {
        'vehicle': vehicle,
        'insights': insights,
        'total_fuel_overall': round(total_fuel_overall, 2),
        'total_money_overall': round(total_money_overall, 2),
        'overall_efficiency': round(overall_efficiency, 2),
        'total_distance_overall': round(total_distance_overall, 2)
    }
    return render(request, 'fleet/vehicle_fuel_insights.html', context)

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
            form = DriverForm(request.POST, request.FILES)
            if form.is_valid():
                driver = form.save(commit=False)
                driver.role = 'driver'
                driver.company = company
                import uuid
                import string
                import random
                
                # Generate unique work email
                safe_name = (driver.first_name or 'driver').lower().replace(' ', '')
                work_email = f"{safe_name}.drv{uuid.uuid4().hex[:4]}@logicontrol.in"
                driver.username = work_email
                
                # Generate a random initial password
                raw_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                driver.set_password(raw_password)
                
                driver.requires_password_change = True
                # Inject raw password for the post_save signal to dispatch via email
                driver._raw_password = raw_password
                
                driver.save()
                
                if driver.email:
                    messages.success(request, f"Driver Onboarded. Credentials sent to {driver.email}.")
                else:
                    messages.success(request, f"Driver Onboarded. No personal email provided, so credentials could not be sent.")
            else:
                messages.error(request, f"Error adding driver. {form.errors.as_text()}")

        elif action == 'edit_driver':
            driver_id = request.POST.get('driver_id')
            driver = get_object_or_404(User, id=driver_id, role='driver', company=company)
            form = DriverForm(request.POST, request.FILES, instance=driver)
            if form.is_valid():
                form.save()
                messages.success(request, "Driver updated.")
            else:
                messages.error(request, f"Error updating driver. {form.errors.as_text()}")

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
                if trip.total_distance_km and trip.total_distance_km > 150:
                    trip.status = 'pending'
                    if trip.driver:
                        messages.warning(request, "Trip exceeds 150km. Dispatch is locked until a backhaul is secured.")
                else:
                    if trip.driver:
                        trip.status = 'approved'
                    else:
                        trip.status = 'pending'
                
                trip.save()  # Must save the trip first to generate an ID
                
                if trip.driver:
                    Alert.objects.create(
                        company=company,
                        trip=trip,
                        raised_by=request.user,
                        alert_type='trip_assigned',
                        message=f"New trip assigned: {trip.start_location} → {trip.end_location}.",
                    )
                
                messages.success(request, "Trip created successfully.")
                return redirect('trip_allocation')
            else:
                messages.error(request, "Please fix the errors below.")
    else:
        form = TripCreateForm(company=company)

    busy_drivers = Trip.objects.filter(status='in_progress', company=company).values_list('driver_id', flat=True)
    available_drivers = User.objects.filter(role='driver', company=company).exclude(id__in=busy_drivers)

    # Unassigned = pending trips that have NO driver assigned yet
    unassigned_trips = Trip.objects.filter(
        status='pending', company=company, driver__isnull=True
    ).select_related('vehicle').order_by('scheduled_departure')

    # Urgent deliveries = trips whose scheduled departure is today or overdue, still pending
    from django.utils import timezone as tz
    now = tz.now()
    urgent_trips = Trip.objects.filter(
        company=company,
        status='pending',
        scheduled_departure__lte=now
    ).select_related('vehicle', 'driver').order_by('scheduled_departure')

    context = {
        'form': form,
        'unassigned_trips': unassigned_trips,
        'available_drivers': available_drivers,
        'urgent_trips': urgent_trips,
        'urgent_count': urgent_trips.count(),
        'now': now,
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
    from django.db.models import F, Sum, Avg
    today = timezone.now().date()
    completed_today = Trip.objects.filter(company=company, status='completed', updated_at__date=today)
    total_distance_qs = completed_today.aggregate(total=Sum(F('end_odometer') - F('start_odometer')))
    total_distance = total_distance_qs['total'] or 0

    # Calculate Avg Fleet Speed
    active_vehicles = Vehicle.objects.filter(company=company, trips__in=active_trips)
    avg_speed_qs = active_vehicles.aggregate(avg=Avg('current_speed'))
    avg_speed = round(avg_speed_qs['avg'] or 0, 1)

    critical_alerts = Alert.objects.filter(company=company, alert_type__in=['panic', 'maintenance']).order_by('-created_at')[:5]

    context = {
        'active_trips': active_trips,
        'total_distance': total_distance,
        'critical_alerts': critical_alerts,
        'avg_speed': avg_speed,
    }
    return render(request, 'fleet/route_analytics.html', context)


@login_required
@manager_required
def api_telemetry(request):
    import random
    from django.http import JsonResponse
    from django.db.models import F, Sum, Avg
    from django.utils import timezone
    company = request.user.company
    active_trips = Trip.objects.filter(company=company, status='in_progress').select_related('vehicle')
    
    vehicles_data = []
    for trip in active_trips:
        v = trip.vehicle
        # For demonstration purposes in SaaS, if coordinates are empty, provide a random one near central India
        lat = v.current_latitude if v.current_latitude else 20.5937 + random.uniform(-2, 2)
        lon = v.current_longitude if v.current_longitude else 78.9629 + random.uniform(-2, 2)
        vehicles_data.append({
            'id': v.id,
            'registration': v.registration_number,
            'lat': float(lat),
            'lon': float(lon),
            'speed': float(v.current_speed),
            'trip_id': trip.id,
            'destination': trip.end_location,
        })
        
    today = timezone.now().date()
    completed_today = Trip.objects.filter(company=company, status='completed', updated_at__date=today)
    total_distance_qs = completed_today.aggregate(total=Sum(F('end_odometer') - F('start_odometer')))
    total_distance = total_distance_qs['total'] or 0

    active_vehicles = Vehicle.objects.filter(company=company, trips__in=active_trips)
    avg_speed_qs = active_vehicles.aggregate(avg=Avg('current_speed'))
    avg_speed = round(avg_speed_qs['avg'] or 0, 1)

    alerts = Alert.objects.filter(company=company, alert_type__in=['panic', 'maintenance']).order_by('-created_at')[:5]
    alerts_data = []
    for alert in alerts:
        alerts_data.append({
            'type': alert.get_alert_type_display(),
            'message': alert.message,
        })

    return JsonResponse({
        'vehicles': vehicles_data,
        'total_distance': total_distance,
        'avg_speed': avg_speed,
        'alerts': alerts_data
    })


@login_required
@manager_required
def export_route_analytics(request):
    import csv
    from django.http import HttpResponse
    from django.utils import timezone
    company = request.user.company
    today = timezone.now().date()
    trips = Trip.objects.filter(company=company, updated_at__date=today)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="route_analytics_{today}.csv"'
    
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
#  DRIVER SETTINGS (separate from manager settings)
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_settings(request):
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name  = request.POST.get('last_name',  request.user.last_name)
        request.user.email      = request.POST.get('email',      request.user.email)
        request.user.phone_number = request.POST.get('phone_number', request.user.phone_number)
        if request.FILES.get('profile_picture'):
            request.user.profile_picture = request.FILES['profile_picture']
        if 'appearance_mode' in request.POST:
            request.user.appearance_mode   = request.POST.get('appearance_mode', 'light')
            request.user.platform_language = request.POST.get('platform_language', 'English (India)')
        request.user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('driver_settings')

    active_trip = Trip.objects.filter(
        driver=request.user, status__in=['approved', 'in_progress']
    ).select_related('vehicle').first()

    return render(request, 'fleet/driver_settings.html', {'active_trip': active_trip})


# ══════════════════════════════════════════════════════════
#  DRIVER FUEL REGISTRY
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_fuel_registry(request):
    from .models import FuelEntry
    from django.db.models import Sum, Avg, Count, Q

    active_trip = Trip.objects.filter(
        driver=request.user, status__in=['approved', 'in_progress']
    ).select_related('vehicle').first()

    fuel_entries = FuelEntry.objects.none()
    analytics = {}

    if active_trip:
        # All fuel entries for this trip (tenant-isolated)
        fuel_entries = FuelEntry.objects.filter(
            trip=active_trip,
            driver=request.user,
            company=request.user.company
        ).order_by('-timestamp')

        # Station search filter
        search_q = request.GET.get('q', '').strip()
        if search_q:
            fuel_entries = fuel_entries.filter(station_name__icontains=search_q)

        # POST – log a new fuel purchase
        if request.method == 'POST':
            try:
                vol   = float(request.POST.get('volume_liters', 0))
                cost  = float(request.POST.get('total_cost', 0))
                odo   = int(request.POST.get('odometer_at_fill', active_trip.vehicle.current_odometer or 0))
                entry = FuelEntry(
                    driver          = request.user,
                    vehicle         = active_trip.vehicle,
                    trip            = active_trip,
                    company         = request.user.company,
                    station_name    = request.POST.get('station_name', ''),
                    volume_liters   = vol,
                    total_cost      = cost,
                    odometer_at_fill= odo,
                    notes           = request.POST.get('notes', ''),
                    status          = 'PENDING',
                )
                if request.FILES.get('receipt_image'):
                    entry.receipt_image = request.FILES['receipt_image']
                entry.save()
                messages.success(request, 'Fuel purchase logged successfully. Awaiting manager approval.')
            except Exception as e:
                messages.error(request, f'Error logging fuel entry: {e}')
            return redirect('driver_fuel_registry')

        # ── Analytics Calculations ──────────────────────────────
        agg = fuel_entries.aggregate(
            total_volume  = Sum('volume_liters'),
            total_spent   = Sum('total_cost'),
            approved_spent= Sum('total_cost', filter=Q(status='APPROVED')),
            entry_count   = Count('id'),
        )

        total_volume = float(agg['total_volume'] or 0)
        total_spent  = float(agg['total_spent']  or 0)
        approved_spent = float(agg['approved_spent'] or 0)

        # Trip distance
        trip_distance = 0
        if active_trip.start_odometer and active_trip.vehicle.current_odometer:
            trip_distance = max(0, active_trip.vehicle.current_odometer - active_trip.start_odometer)

        # Average burn (L/100km)
        avg_burn = 0
        if trip_distance > 0 and total_volume > 0:
            avg_burn = round((total_volume / trip_distance) * 100, 1)

        # Estimated fuel level (assume 300L tank for heavy vehicles, scale by vehicle type)
        tank_capacity = 300  # litres – default for HMV/trailer
        if hasattr(active_trip.vehicle, 'vehicle_type'):
            if active_trip.vehicle.vehicle_type == 'lmv':
                tank_capacity = 80
            elif active_trip.vehicle.vehicle_type == 'mhv':
                tank_capacity = 150

        estimated_fuel_level = min(100, round((total_volume / tank_capacity) * 100)) if tank_capacity else 0
        remaining_liters = round(tank_capacity * (estimated_fuel_level / 100))

        # Remaining range
        remaining_range = 0
        if avg_burn > 0:
            remaining_range = round((remaining_liters / avg_burn) * 100)

        # Last refill info
        last_entry = fuel_entries.filter(status='APPROVED').first() or fuel_entries.first()
        avg_price_per_liter = round(total_spent / total_volume, 2) if total_volume > 0 else 0

        analytics = {
            'estimated_fuel_pct': estimated_fuel_level,
            'remaining_liters':   remaining_liters,
            'avg_burn':           avg_burn,
            'remaining_range':    remaining_range,
            'trip_spending':      round(approved_spent, 2),
            'total_volume':       round(total_volume, 1),
            'avg_price_per_liter':avg_price_per_liter,
            'last_entry':         last_entry,
            'entry_count':        agg['entry_count'],
        }

    return render(request, 'fleet/driver_fuel_registry.html', {
        'active_trip':  active_trip,
        'fuel_entries': fuel_entries,
        'analytics':    analytics,
        'search_q':     request.GET.get('q', ''),
    })


# ══════════════════════════════════════════════════════════
#  DRIVER REVENUE & EARNINGS
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_revenue(request):
    from django.db.models import Sum, Avg, Count, Q
    from datetime import date
    import json

    driver  = request.user
    company = driver.company
    today   = timezone.now().date()

    # ── Date ranges ──────────────────────────────────────────
    current_month_start = today.replace(day=1)
    # Previous month
    if today.month == 1:
        prev_month_start = date(today.year - 1, 12, 1)
        prev_month_end   = date(today.year, 1, 1)
    else:
        prev_month_start = date(today.year, today.month - 1, 1)
        prev_month_end   = current_month_start

    # ── Base salary ──────────────────────────────────────────
    base_salary = float(driver.contract_salary or 0)
    # Fall back to latest payroll entry if no contract set
    if base_salary == 0:
        latest_payroll = Payroll.objects.filter(
            driver=driver, company=company
        ).order_by('-month').first()
        if latest_payroll:
            base_salary = float(latest_payroll.base_salary)

    # ── Current-month trip bonus ─────────────────────────────
    current_bonus_agg = Trip.objects.filter(
        driver=driver, company=company,
        status='completed',
        updated_at__date__gte=current_month_start,
    ).aggregate(total_bonus=Sum('bonus_amount'))
    current_trip_bonus = float(current_bonus_agg['total_bonus'] or 0)

    mtd_total = base_salary + current_trip_bonus

    # ── Previous month totals for % change ──────────────────
    prev_payroll = Payroll.objects.filter(
        driver=driver, company=company,
        month__gte=prev_month_start,
        month__lt=prev_month_end,
    ).first()
    prev_total = float(prev_payroll.total_paid if prev_payroll else 0)
    if prev_total > 0:
        pct_change = round(((mtd_total - prev_total) / prev_total) * 100, 1)
    else:
        pct_change = 0

    # ── Weekly earnings trend (last 7 weeks) ─────────────────
    weekly_labels = []
    weekly_values = []
    for i in range(6, -1, -1):
        week_start = today - timedelta(weeks=i+1)
        week_end   = today - timedelta(weeks=i)
        label = week_start.strftime('W%U')
        trips_in_week = Trip.objects.filter(
            driver=driver, company=company,
            status='completed',
            updated_at__date__gte=week_start,
            updated_at__date__lt=week_end,
        ).aggregate(bonus=Sum('bonus_amount'))
        week_earn = float(trips_in_week['bonus'] or 0) + (base_salary / 4.33)
        weekly_labels.append(label)
        weekly_values.append(round(week_earn, 0))

    # ── Performance Scorecard ────────────────────────────────
    # Safety: 100 - (alerts × 5), floor 0
    alert_count = Alert.objects.filter(
        raised_by=driver,
        created_at__date__gte=current_month_start,
    ).exclude(alert_type='trip_assigned').count()
    safety_score = max(0, min(100, 100 - (alert_count * 5)))

    # Efficiency: (target_burn / actual_burn) × 100; target = 28 L/100km
    fuel_agg = FuelEntry.objects.filter(
        driver=driver, company=company,
        timestamp__date__gte=current_month_start,
    ).aggregate(total_vol=Sum('volume_liters'))
    total_vol = float(fuel_agg['total_vol'] or 0)

    trip_distance = 0
    active_trip = Trip.objects.filter(
        driver=driver, status__in=['approved', 'in_progress']
    ).select_related('vehicle').first()
    if active_trip and active_trip.start_odometer and active_trip.vehicle.current_odometer:
        trip_distance = max(0, active_trip.vehicle.current_odometer - active_trip.start_odometer)

    if trip_distance > 0 and total_vol > 0:
        actual_burn  = (total_vol / trip_distance) * 100
        target_burn  = 28.0  # L/100km standard
        efficiency_score = min(100, round((target_burn / actual_burn) * 100))
    else:
        efficiency_score = 85  # default if no data yet

    # Punctuality: % trips where arrived on time
    completed_trips = Trip.objects.filter(
        driver=driver, company=company, status='completed'
    )
    total_completed = completed_trips.count()
    on_time = completed_trips.filter(
        scheduled_arrival__isnull=False,
        updated_at__lte=models_updated_at_for_schedule()
    ).count() if total_completed else 0
    # Simplified: use a proxy — trips without maintenance_notes as "on time"
    on_time = completed_trips.filter(maintenance_notes__isnull=True).count()
    punctuality_score = round((on_time / total_completed) * 100) if total_completed > 0 else 90

    # Peer status
    avg_safety = safety_score  # single driver context; placeholder
    if safety_score >= 95:
        peer_status = "Outstanding safety record this month. You're in the top 5% of our fleet."
    elif safety_score >= 80:
        peer_status = "Good performance. You're in the top 25% of our fleet this month."
    else:
        peer_status = "Keep improving! Reduce alerts to climb the fleet rankings."

    # ── Payout history ──────────────────────────────────────
    payrolls = Payroll.objects.filter(
        driver=driver, company=company
    ).order_by('-month')[:12]

    # ── PDF download ─────────────────────────────────────────
    if request.GET.get('download') == 'pdf':
        return _generate_revenue_pdf(driver, base_salary, current_trip_bonus, mtd_total, payrolls)

    return render(request, 'fleet/driver_revenue.html', {
        'active_trip':       active_trip,
        'base_salary':       base_salary,
        'current_trip_bonus':current_trip_bonus,
        'mtd_total':         mtd_total,
        'pct_change':        pct_change,
        'weekly_labels':     json.dumps(weekly_labels),
        'weekly_values':     json.dumps(weekly_values),
        'safety_score':      safety_score,
        'efficiency_score':  efficiency_score,
        'punctuality_score': punctuality_score,
        'peer_status':       peer_status,
        'payrolls':          payrolls,
        'today':             today,
        'current_month':     today.strftime('%B %Y'),
    })


def _generate_revenue_pdf(driver, base_salary, trip_bonus, mtd_total, payrolls):
    """Generate a plain-text PDF-like statement using HttpResponse."""
    from django.http import HttpResponse
    today = timezone.now().strftime('%d %B %Y')
    content = f"""
╔══════════════════════════════════════════════════════╗
             LOGICONTROL INDIA – EARNINGS STATEMENT
╚══════════════════════════════════════════════════════╝

Driver      : {driver.get_full_name() or driver.username}
Work Email  : {driver.username}
Company     : {driver.company.name if driver.company else '—'}
Generated   : {today}

──────────────────────────────────────────────────────
  CURRENT MONTH SUMMARY
──────────────────────────────────────────────────────
  Base Salary        :  ₹{base_salary:,.2f}
  Trip Bonus         :  ₹{trip_bonus:,.2f}
  Month-to-Date Total:  ₹{mtd_total:,.2f}

──────────────────────────────────────────────────────
  PAYOUT HISTORY
──────────────────────────────────────────────────────
  {'Month':<15} {'Base':>10} {'Bonus':>10} {'Total':>12} {'Status'}
  {'-'*60}
"""
    for p in payrolls:
        content += f"  {p.month.strftime('%b %Y'):<15} ₹{float(p.base_salary):>9,.0f} ₹{float(p.trip_bonus):>9,.0f} ₹{float(p.total_paid):>11,.0f} {p.status.upper()}\n"

    content += f"""
──────────────────────────────────────────────────────
  This is a system-generated statement.
  For queries, contact your fleet manager.
  © LogiControl India SaaS Platform
"""
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="earnings_statement_{driver.username}_{today.replace(" ","_")}.txt"'
    return response


def models_updated_at_for_schedule():
    """Helper placeholder — returns current time for punctuality calc."""
    return timezone.now()


# ══════════════════════════════════════════════════════════
#  DRIVER – ROUTE ANALYTICS
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_route_analytics(request):
    from django.conf import settings
    import math

    driver  = request.user
    company = driver.company

    active_trip = (
        Trip.objects.filter(driver=driver, status__in=['approved', 'in_progress'])
        .select_related('vehicle')
        .first()
    )

    map_data = {}
    if active_trip and active_trip.vehicle:
        v = active_trip.vehicle
        lat  = float(v.current_latitude  or 20.5937)   # default: India center
        lng  = float(v.current_longitude or 78.9629)
        speed = float(v.current_speed or 0)
        heading = v.current_heading or 'North'

        # Remaining distance estimate
        total_km     = active_trip.total_distance_km or 0
        start_odo    = active_trip.start_odometer or v.current_odometer
        traveled_km  = max(0, v.current_odometer - start_odo)
        remaining_km = max(0, total_km - traveled_km)

        # ETA estimate (avg 60 km/h if speed = 0)
        avg_speed = speed if speed > 10 else 60
        eta_hours = remaining_km / avg_speed if avg_speed > 0 else 0
        eta_h = int(eta_hours)
        eta_m = int((eta_hours - eta_h) * 60)

        map_data = {
            'lat': lat, 'lng': lng,
            'speed': speed, 'heading': heading,
            'reg': v.registration_number,
            'start': active_trip.start_location,
            'end':   active_trip.end_location,
            'total_km':    total_km,
            'traveled_km': traveled_km,
            'remaining_km': remaining_km,
            'eta_display': f"{eta_h:02d}h {eta_m:02d}m",
        }

    return render(request, 'fleet/driver_route_analytics.html', {
        'active_trip': active_trip,
        'map_data':    map_data,
        'maps_api_key': getattr(settings, 'MAPS_API_KEY', ''),
    })


# ══════════════════════════════════════════════════════════
#  DRIVER – VEHICLE HEALTH
# ══════════════════════════════════════════════════════════

@login_required
@driver_required
def driver_vehicle_health(request):
    driver  = request.user
    company = driver.company

    active_trip = (
        Trip.objects.filter(driver=driver, status__in=['approved', 'in_progress'])
        .select_related('vehicle')
        .first()
    )

    vehicle = active_trip.vehicle if active_trip else None
    maintenance_logs = []
    if vehicle:
        maintenance_logs = (
            MaintenanceLog.objects
            .filter(vehicle=vehicle, company=company)
            .order_by('-last_service_date')[:10]
        )

    # Report fault POST
    if request.method == 'POST' and request.POST.get('action') == 'report_fault':
        fault_desc = request.POST.get('fault_description', '').strip()
        if fault_desc and vehicle:
            Alert.objects.create(
                company=company,
                raised_by=driver,
                vehicle=vehicle,
                alert_type='fault_report',
                severity='high',
                message=f"🚨 FAULT REPORTED by {driver.get_full_name() or driver.username} "
                        f"[{vehicle.registration_number}]: {fault_desc}",
                status='unread',
            )
            messages.success(request, "Fault reported successfully. Your manager has been notified.")
        else:
            messages.error(request, "Please describe the fault before submitting.")
        return redirect('driver_vehicle_health')

    # Determine overall health status
    if vehicle:
        avg_health = (vehicle.engine_performance + vehicle.tire_integrity + vehicle.battery_life) // 3
        if avg_health >= 80:
            health_status = 'OPTIMAL STATUS'
            health_color  = '#22c55e'
        elif avg_health >= 60:
            health_status = 'FAIR CONDITION'
            health_color  = '#f59e0b'
        else:
            health_status = 'ATTENTION NEEDED'
            health_color  = '#ef4444'
    else:
        avg_health = 0
        health_status = 'NO VEHICLE'
        health_color  = '#64748b'

    return render(request, 'fleet/driver_vehicle_health.html', {
        'active_trip':       active_trip,
        'vehicle':           vehicle,
        'maintenance_logs':  maintenance_logs,
        'health_status':     health_status,
        'health_color':      health_color,
        'avg_health':        avg_health,
    })


# ══════════════════════════════════════════════════════════
#  ALERTS API (mark as read)
# ══════════════════════════════════════════════════════════

@login_required
def mark_alert_read(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id, company=request.user.company)
    alert.status = 'read'
    alert.save()
    return redirect(request.META.get('HTTP_REFERER', 'manager_dashboard'))


# ══════════════════════════════════════════════════════════
#  FOOTER PAGES
# ══════════════════════════════════════════════════════════

def help_center(request):
    return render(request, 'help_center.html')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')

def terms_of_service(request):
    return render(request, 'terms_of_service.html')

def contact_support(request):
    return render(request, 'contact_support.html')


# ══════════════════════════════════════════════════════════
#  UNIVERSAL SEARCH
# ══════════════════════════════════════════════════════════

@login_required
@manager_required
def universal_search(request):
    query = request.GET.get('q', '').strip()
    company = request.user.company
    
    context = {'query': query}
    
    if query:
        from django.db.models import Q
        vehicles = Vehicle.objects.filter(company=company).filter(
            Q(registration_number__icontains=query) |
            Q(make__icontains=query) |
            Q(model__icontains=query)
        )
        drivers = User.objects.filter(role='driver', company=company).filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(driving_license__icontains=query) |
            Q(username__icontains=query) |
            Q(phone_number__icontains=query)
        )
        trips = Trip.objects.filter(company=company).filter(
            Q(start_location__icontains=query) |
            Q(end_location__icontains=query)
        )
        if query.isdigit():
            trips = trips | Trip.objects.filter(company=company, id=query)
        
        context.update({
            'vehicles': vehicles,
            'drivers': drivers,
            'trips': trips,
        })
        
    return render(request, 'fleet/search_results.html', context)


# ══════════════════════════════════════════════════════════
#  LOGILOOP EXCHANGE (Cross-Tenant Backhaul)
# ══════════════════════════════════════════════════════════

import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth."""
    R = 6371  # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@login_required
@manager_required
def logiloop_matcher(request, trip_id):
    from .models import GlobalLoadPool, LinkedTrip
    trip = get_object_or_404(Trip, id=trip_id, company=request.user.company)
    
    # Destination coordinates (mocking for Theni based on prompt context, 
    # in production this would be geocoded from trip.end_location)
    dest_lat = float(request.GET.get('lat', 10.0104)) 
    dest_lon = float(request.GET.get('lon', 77.4768)) 
    
    vehicle_type = trip.vehicle.vehicle_type
    
    # Fetch all visible loads
    all_pool_loads = GlobalLoadPool.objects.filter(is_fulfilled=False).filter(
        Q(visibility='PUBLIC') | 
        Q(origin_company=request.user.company) | 
        Q(visibility='PARTNER')
    )
    
    matching_loads = []
    
    # Fetch settings
    settings_obj = GlobalSettings.objects.first()
    if not settings_obj:
        settings_obj = GlobalSettings.objects.create()
        
    rate = float(settings_obj.heavy_asset_commission_rate) if trip.vehicle.vehicle_type in ['torus', 'trailer'] else float(settings_obj.exchange_commission_rate)
    flat_fee = float(settings_obj.flat_transaction_fee)
    
    # Mock parameters for simulation
    revenue_out = 45000
    cost_per_km = 45
    
    for load in all_pool_loads:
        # Asset Specialization: Torus Trucks must not carry refrigerated/closed loads
        if vehicle_type == 'torus' and ('refrigerated' in load.cargo_type.lower() or 'closed' in load.cargo_type.lower()):
            continue
            
        dist = haversine(dest_lat, dest_lon, load.origin_lat, load.origin_lon)
        if dist <= 60.0:  # 60km radius
            return_dist = haversine(load.origin_lat, load.origin_lon, load.destination_lat, load.destination_lon)
            total_dist = (trip.total_distance_km or 200) + return_dist
            fuel_cost = total_dist * cost_per_km
            
            revenue_return = float(load.weight_tons) * 1500
            platform_fee = ((revenue_return * rate) / 100) + flat_fee if load.origin_company != request.user.company else 0
            
            net_profit = (revenue_out + revenue_return) - fuel_cost - platform_fee
            
            matching_loads.append({
                'load': load,
                'distance': round(dist, 1),
                'match_type': 'Internal' if load.origin_company == request.user.company else 'Cross-Tenant',
                'revenue_out': revenue_out,
                'revenue_return': round(revenue_return, 2),
                'total_revenue': round(revenue_out + revenue_return, 2),
                'fuel_cost': round(fuel_cost, 2),
                'platform_fee': round(platform_fee, 2),
                'net_profit': round(net_profit, 2)
            })
            
    # Sort by distance
    matching_loads.sort(key=lambda x: x['distance'])
    
    if request.method == 'POST':
        load_id = request.POST.get('load_id')
        selected_load = get_object_or_404(GlobalLoadPool, id=load_id)
        
        # 3. Cross-Tenant Handshake (Auto-generate return trip)
        return_trip = Trip.objects.create(
            company=request.user.company,
            vehicle=trip.vehicle,
            driver=trip.driver,
            start_location=f"Lat {selected_load.origin_lat:.4f}, Lon {selected_load.origin_lon:.4f}",
            end_location=f"Lat {selected_load.destination_lat:.4f}, Lon {selected_load.destination_lon:.4f}",
            goods_type=selected_load.cargo_type,
            status='approved'
        )
        selected_load.is_fulfilled = True
        selected_load.save()
        
        # Unlock outbound trip dispatch since backhaul is secured
        trip.status = 'approved'
        trip.save()
        
        # Calculate financial ROI loop
        # Formula: Net Profit = (Revenue_Out + Revenue_Return) - (Total Distance * Cost_Per_KM)
        revenue_out = 45000  # Example mock data
        revenue_return = float(selected_load.weight_tons) * 1500  # mock rate
        total_dist = (trip.total_distance_km or 200) + haversine(selected_load.origin_lat, selected_load.origin_lon, selected_load.destination_lat, selected_load.destination_lon)
        cost_per_km = 45
        fuel_cost = total_dist * cost_per_km
        
        # Calculate your cut from the return leg revenue based on GlobalSettings
        settings_obj = GlobalSettings.objects.first()
        rate = float(settings_obj.heavy_asset_commission_rate) if trip.vehicle.vehicle_type in ['torus', 'trailer'] else float(settings_obj.exchange_commission_rate)
        flat_fee = float(settings_obj.flat_transaction_fee)
        
        platform_fee = ((revenue_return * rate) / 100) + flat_fee if selected_load.origin_company != request.user.company else 0
        
        linked_loop = LinkedTrip.objects.create(
            outbound_trip=trip,
            return_trip=return_trip,
            combined_revenue=revenue_out + revenue_return,
            total_estimated_fuel_cost=fuel_cost,
            platform_commission=platform_fee
        )
        
        roi = linked_loop.calculate_loop_roi()
        if roi > 0:
            messages.success(request, f"Backhaul secured! Linked Loop created. ROI: ₹{roi:,.2f}")
        else:
            messages.warning(request, f"Backhaul secured, but Linked Loop ROI is negative: ₹{roi:,.2f}")
            
        return redirect('trip_allocation')
        
    return render(request, 'fleet/logiloop_matcher.html', {
        'trip': trip,
        'matching_loads': matching_loads,
        'dest_lat': dest_lat,
        'dest_lon': dest_lon
    })
