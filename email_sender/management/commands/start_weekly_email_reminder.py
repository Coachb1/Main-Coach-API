from django.core.management.base import BaseCommand
from email_sender.jobs import initialize_weekly_email_schedular

class Command(BaseCommand):
    help = 'Start the APScheduler'

    def handle(self, *args, **options):
        initialize_weekly_email_schedular()