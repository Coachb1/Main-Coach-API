from django.apps import AppConfig
from apscheduler.schedulers.background import BackgroundScheduler

class EmailSenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_sender'

    def ready(self):
        from email_sender.jobs import touch_point_for_session_weekly, weekly_remider_to_login, testing
        from datetime import datetime

        scheduler = BackgroundScheduler()
        job_defaults = {
                        'coalesce': False,
                        'max_instances': 3,
                        'replace_existing': True,
                        'misfire_grace_time': 120
                        }
        scheduler.configure(job_defaults=job_defaults)
        ## adding weekily email scheduler for touch point reminder for session 
        scheduler.add_job(
            touch_point_for_session_weekly,
            trigger='cron',
            day_of_week='mon',
            hour=11,
            minute=0,
            id="touch_point"
        )

        scheduler.add_job(
            weekly_remider_to_login,
            trigger='cron',
            day_of_week='mon',
            hour=11,
            minute=30,
            id='weekly_login_reminder',
        )
        specific_date_time = datetime(2024, 2, 27, 15, 30)
        scheduler.add_job(
            testing,
            trigger='date',
            run_date=specific_date_time,
            id='specific_date_time_job'
        )

        scheduler.start()
