from django.db import models

class JotUrlSession(models.Model):
    email = models.CharField(max_length=255)
    session_id = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "joturl_session"