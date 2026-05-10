from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # ── Public Landing & Auth ─────────────────────────────
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('resources/', views.resources, name='resources'),
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('signup/', views.owner_signup, name='owner_signup'),
    
    # ── Footer Links ─────────────────────────────
    path('help-center/', views.help_center, name='help_center'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('contact-support/', views.contact_support, name='contact_support'),

    # ── Password Reset Flow ───────────────────────────────
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/password-reset/sent/',
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/login/',
    ), name='password_reset_confirm'),

    # ── Password Change Flow ─────────────────────────────
    path('password-change/', views.force_password_change, name='password_change'),

    # ── Dashboard Routing ─────────────────────────────────
    path('dashboard/', views.dashboard_redirect, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-portal/tenants/', views.admin_tenant_management, name='admin_tenant_management'),
    path('admin-portal/tenants/action/', views.admin_tenant_action, name='admin_tenant_action'),
    path('admin-portal/subscriptions/', views.admin_subscriptions, name='admin_subscriptions'),
    path('admin-portal/api-integration/', views.admin_api_integration, name='admin_api_integration'),
    path('admin-portal/support-tickets/', views.admin_support_tickets, name='admin_support_tickets'),
    path('admin-portal/settings/', views.admin_settings, name='admin_settings'),
    path('manager-dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('driver-dashboard/', views.driver_dashboard, name='driver_dashboard'),

    # ── Driver Actions ────────────────────────────────────
    path('driver/action/<int:trip_id>/<str:action>/', views.driver_action, name='driver_action'),
    path('driver/trip/<int:trip_id>/', views.driver_trip_update, name='driver_trip_update'),
    path('driver/settings/', views.driver_settings, name='driver_settings'),
    path('driver/fuel/', views.driver_fuel_registry, name='driver_fuel_registry'),
    path('driver/revenue/', views.driver_revenue, name='driver_revenue'),
    path('driver/route/', views.driver_route_analytics, name='driver_route_analytics'),
    path('driver/health/', views.driver_vehicle_health, name='driver_vehicle_health'),

    # ── Manager – Fleet ───────────────────────────────────
    path('fleet-registry/', views.fleet_registry, name='fleet_registry'),
    path('directory/vehicles/', views.vehicle_directory, name='vehicle_directory'),
    path('directory/drivers/', views.driver_directory, name='driver_directory'),
    path('vehicle/<int:vehicle_id>/status/', views.vehicle_status_update, name='vehicle_status_update'),
    path('vehicle/<int:vehicle_id>/fuel-insights/', views.vehicle_fuel_insights, name='vehicle_fuel_insights'),

    # ── Manager – Trips ───────────────────────────────────
    path('trip-allocation/', views.trip_allocation, name='trip_allocation'),
    path('logiloop/<int:trip_id>/', views.logiloop_matcher, name='logiloop_matcher'),
    path('route-analytics/', views.route_analytics, name='route_analytics'),
    path('route-analytics/export/', views.export_route_analytics, name='export_route_analytics'),
    path('api/telemetry/', views.api_telemetry, name='api_telemetry'),
    
    # ── Universal Search ──────────────────────────────────
    path('search/', views.universal_search, name='universal_search'),

    # ── Manager – Finance ─────────────────────────────────
    path('revenue/', views.revenue_dashboard, name='revenue_dashboard'),
    path('revenue/export/', views.export_revenue, name='export_revenue'),
    path('revenue/receipt/<int:payroll_id>/', views.export_receipt, name='export_receipt'),

    # ── Common ────────────────────────────────────────────
    path('settings/', views.fleet_settings, name='fleet_settings'),
    path('alerts/<int:alert_id>/read/', views.mark_alert_read, name='mark_alert_read'),
]
