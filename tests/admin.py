from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test, TestQuestion


class StartWithUserFilter(admin.SimpleListFilter):
    title = 'Start with User'
    parameter_name = 'Start with User'

    def lookups(self, request, model_admin):
        return (
            ('start_with_user', 'Start With User'),
            ('does_not_start_with_user', 'Does Not Start With User'),
        )

    
    # def queryset(self, request, queryset):
    #     if self.value() == 'start_with_user':
    #         return queryset.filter(orchestrated_conversation_details__start_with_user__isnull=False)
    #     if self.value() == 'does_not_start_with_user':
    #         return queryset.filter(orchestrated_conversation_details__start_with_user__isnull=True)
    #     return queryset
    
    
    def queryset(self, request, queryset):
        if self.value() == 'start_with_user':
            return queryset.filter(orchestrated_conversation_details__isnull=False).filter(orchestrated_conversation_details__start_with_user__isnull=False)
        if self.value() == 'does_not_start_with_user':
            return queryset.filter(orchestrated_conversation_details__isnull=True) | queryset.filter(orchestrated_conversation_details__start_with_user__isnull=True)
        return queryset


class TestAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_code','title','test_type','interaction_mode','deleted', 'start_with_user')
    search_fields = ('test_code','title')
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_type',StartWithUserFilter)
    
    def start_with_user(self, obj):
        start_with_user_message = obj.orchestrated_conversation_details.get('start_with_user') if obj.orchestrated_conversation_details else None
        start_with_user = False if start_with_user_message is None else True
        return start_with_user

class TestQuestionAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_id','question_number','question','question_for','deleted')
    search_fields = ('test_id',)
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_id')


admin.site.register(Test, TestAdmin)
admin.site.register(TestQuestion, TestQuestionAdmin)