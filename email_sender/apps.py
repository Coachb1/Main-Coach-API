from django.apps import AppConfig
import os

class EmailSenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_sender'

    def ready(self) -> None:
        from email_sender.jobs import initialize_weekly_email_schedular
        print(os.environ.get('RUN_MAIN'))
        if os.environ.get('RUN_MAIN'):
            initialize_weekly_email_schedular()



        
