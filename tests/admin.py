from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test, TestQuestion




class TestAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_code','title','test_type','interaction_mode','deleted')
    search_fields = ('test_code','title')
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_type')

class TestQuestionAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_id','question_number','question','question_for','deleted')
    search_fields = ('test_id',)
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_id')


admin.site.register(Test, TestAdmin)
admin.site.register(TestQuestion, TestQuestionAdmin)