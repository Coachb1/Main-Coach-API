from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test




class TestAdmin(ExportActionMixin, admin.ModelAdmin):
    list_display = ('uid','test_code','title','test_type','interaction_mode','deleted')
    search_fields = ('test_code',)
    list_editable = ('deleted',)


admin.site.register(Test, TestAdmin)