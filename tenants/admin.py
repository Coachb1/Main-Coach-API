from django.contrib import admin
from import_export.admin import ExportActionMixin
from tenants.models import Tenant




class TenantAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','name','subdomain_prefix','logo','test_per_month','mobile_number_restriction_whatsapp','mobile_number_list','use_skills_from_skill_bank')
    search_fields = ('subdomain_prefix','name')
    list_editable = ('logo','test_per_month','mobile_number_restriction_whatsapp','mobile_number_list','use_skills_from_skill_bank')

admin.site.register(Tenant, TenantAdmin)
