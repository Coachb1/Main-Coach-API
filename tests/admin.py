from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test




class TestAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_code','title','test_type','interaction_mode','deleted')
    search_fields = ('test_code',)
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_type')


admin.site.register(Test, TestAdmin)