from django.apps import AppConfig
import os

class EmailSenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_sender'

    _scheduler = None

    def ready(self) -> None:
        from email_sender.jobs import initialize_weekly_email_schedular        
        if not self._scheduler:
            self._scheduler = initialize_weekly_email_schedular()
            self._scheduler.start()
        



        
