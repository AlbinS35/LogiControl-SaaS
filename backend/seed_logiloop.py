import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logistics_fleet.settings')
django.setup()
from fleet.models import Company, Vehicle, Trip, GlobalLoadPool, User

# Find KL353211 vehicle
vehicle = Vehicle.objects.filter(registration_number='KL353211').first()
if not vehicle:
    print("Vehicle KL353211 not found.")
else:
    company = vehicle.company

    # Ensure there's a trip
    trip = Trip.objects.filter(vehicle=vehicle, end_location='Kottayam').first()
    if not trip:
        print("No trip to Kottayam found for this vehicle. Checking all trips...")
        trip = Trip.objects.filter(vehicle=vehicle).first()
        if trip:
            trip.start_location = 'Alappuzha'
            trip.end_location = 'Kottayam'
            trip.status = 'completed'
            trip.total_distance_km = 45
            trip.save()
            print("Updated trip to Alappuzha -> Kottayam")
        else:
            print("No trips found. Creating one...")
            trip = Trip.objects.create(
                vehicle=vehicle,
                company=company,
                start_location='Alappuzha',
                end_location='Kottayam',
                status='completed',
                total_distance_km=45
            )

    print(f"Trip ID: {trip.id}")

    # Create another company if needed for cross-tenant
    other_company, _ = Company.objects.get_or_create(
        name='Rubber Corp Kerala',
        defaults={'subscription_tier': 'pro', 'is_active': True}
    )

    # Clear existing loads
    GlobalLoadPool.objects.all().delete()

    # Create a GlobalLoadPool in Ettumanoor (near Kottayam) -> Alappuzha
    # Kottayam: 9.5916, 76.5222
    # Ettumanoor: 9.6644, 76.5599
    # Alappuzha: 9.4981, 76.3388

    # Match 1: Cross-Tenant
    load1 = GlobalLoadPool.objects.create(
        origin_company=other_company,
        cargo_type='Rubber Sheets',
        weight_tons=4.0,
        required_vehicle_type='pickup',
        origin_lat=9.6644,
        origin_lon=76.5599,
        origin_name='Ettumanoor',
        destination_lat=9.4981,
        destination_lon=76.3388,
        destination_name='Alappuzha',
        visibility='PUBLIC',
        is_fulfilled=False
    )

    # Match 2: Internal
    load2 = GlobalLoadPool.objects.create(
        origin_company=company,
        cargo_type='Empty Crates',
        weight_tons=1.5,
        required_vehicle_type='pickup',
        origin_lat=9.5916,
        origin_lon=76.5222,
        origin_name='Kottayam',
        destination_lat=9.9312,
        destination_lon=76.2673,
        destination_name='Kochi',
        visibility='PRIVATE',
        is_fulfilled=False
    )

    print(f"Created GlobalLoadPool loads: {load1.id}, {load2.id}")
