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
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('signup/', views.owner_signup, name='owner_signup'),

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

    # ── Manager – Fleet ───────────────────────────────────
    path('fleet-registry/', views.fleet_registry, name='fleet_registry'),
    path('directory/vehicles/', views.vehicle_directory, name='vehicle_directory'),
    path('directory/drivers/', views.driver_directory, name='driver_directory'),

    # ── Manager – Trips ───────────────────────────────────
    path('trip-allocation/', views.trip_allocation, name='trip_allocation'),
    path('route-analytics/', views.route_analytics, name='route_analytics'),
    path('route-analytics/export/', views.export_route_analytics, name='export_route_analytics'),

    # ── Manager – Finance ─────────────────────────────────
    path('revenue/', views.revenue_dashboard, name='revenue_dashboard'),
    path('revenue/export/', views.export_revenue, name='export_revenue'),
    path('revenue/receipt/<int:payroll_id>/', views.export_receipt, name='export_receipt'),

    # ── Common ────────────────────────────────────────────
    path('settings/', views.fleet_settings, name='fleet_settings'),
    path('alerts/<int:alert_id>/read/', views.mark_alert_read, name='mark_alert_read'),
]
