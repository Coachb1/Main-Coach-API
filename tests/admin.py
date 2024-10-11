from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test, TestQuestion
from django.utils.translation import gettext_lazy as _
from tenants.admin import TenantAwareModelAdmin



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


class OnlyCompetencyFilter(admin.SimpleListFilter):
    title = _('Competency Group')
    parameter_name = 'only_competency'

    def lookups(self, request, model_admin):
        return (
            ('has_competency', _('Has Competency')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'has_competency':
            return queryset.exclude(competency_group = None).exclude(competency_group__exact='')
        return queryset

class TestAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_code','title','test_type','scenario_case','interaction_mode','page_name','client_name','competency_group','area_domain','tab_category','deleted','calculate_culture', 'start_with_user')
    search_fields = ('test_code','title','uid','tab_category','competency_group','area_domain')
    list_editable = ('deleted','calculate_culture','page_name','client_name','competency_group','area_domain','tab_category')
    list_filter = ('tenant_id','test_type','scenario_case','calculate_culture','interaction_mode','page_name','client_name',StartWithUserFilter,OnlyCompetencyFilter)
    
    def start_with_user(self, obj):
        start_with_user_message = obj.orchestrated_conversation_details.get('start_with_user') if obj.orchestrated_conversation_details else None
        start_with_user = False if start_with_user_message is None else True
        return start_with_user

class TestQuestionAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('uid','test_id','question_number','question','question_for','deleted')
    search_fields = ('test_id','uid')
    list_editable = ('deleted',)
    list_filter = ('tenant_id','test_id')


admin.site.register(Test, TestAdmin)
admin.site.register(TestQuestion, TestQuestionAdmin)