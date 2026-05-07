"""
Management command: check_doc_expiry
Scans all vehicles and generates Alert records for expiring documents.
Schedule via cron / Task Scheduler to run daily.

Usage:
    python manage.py check_doc_expiry
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Scan vehicle documents and create expiry alerts for vehicles near expiry.'

    def handle(self, *args, **options):
        from fleet.signals import check_document_expiry
        check_document_expiry()
        self.stdout.write(self.style.SUCCESS('Document expiry check completed.'))
