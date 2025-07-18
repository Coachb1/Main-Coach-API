from django.db import models

class AdminDashboardModel(models.Model):
    class Meta:
        managed = False  # No DB table created
        verbose_name = "Admin Dashboard"
        verbose_name_plural = "Admin Dashboard"
