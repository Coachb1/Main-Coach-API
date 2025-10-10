
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from bulk_admin_action.models import AdminDashboardModel

class AdminDashboard(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin_dashboard'))  # your custom view

admin.site.register(AdminDashboardModel, AdminDashboard)
