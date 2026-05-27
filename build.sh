#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

# The Django app is in the 'backend' folder, so we need to run manage.py from there.
echo "Collecting static files..."
python backend/manage.py collectstatic --no-input

echo "Running database migrations..."
python backend/manage.py migrate
