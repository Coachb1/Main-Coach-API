from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test, TestQuestion, Psychometric, PsychometricItem, TestAttemptSession
from django.utils.translation import gettext_lazy as _
from tenants.admin import TenantAwareModelAdmin
import csv
from django import forms
from django.core.exceptions import ValidationError
from tests.helpers import parse_psychometric_csv
from django.contrib import messages
from django.db import transaction
from tenants.models import Tenant
from identities.helpers import get_user_via_identity
from identities.models import Identity
from users.helpers import get_client_info_from_user_detail
from users.models import UserAttribute

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
    list_display = ('uid','test_code','title','test_type','scenario_case','interaction_mode','page_name','client_name','competency_group','area_domain','tab_category','deleted','calculate_culture', 'psychometric','start_with_user')
    search_fields = ('test_code','title','uid','tab_category','competency_group','area_domain')
    list_editable = ('deleted','calculate_culture','page_name','client_name','competency_group','area_domain','psychometric','tab_category')
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


class PsychometricAdminForm(forms.ModelForm):
    csv_file = forms.FileField(
        required=False,
        help_text=_("Upload a CSV file to create Psychometric Items automatically.")
    )
    tenant_id = forms.ChoiceField(
        choices=[(None, _("Select a tenant - (None)"))] + Tenant.get_tenant_choices(),  # Fetch all tenants from the database
        required=False,  # Set this to True or False depending on your requirements
        help_text=_("Select the tenant associated with this Psychometric item."),
        initial=None
    )


    class Meta:
        model = Psychometric
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get('csv_file')
        print(f"cleanded data: {cleaned_data}" )

        tenant_id = cleaned_data.get('tenant_id')

        # Handle saving None if tenant_id is not selected
        if tenant_id == '':
            cleaned_data['tenant_id'] = None 

        if not self.instance.pk:  # Check if this is a new instance (not saved yet)
            if not csv_file:
                raise ValidationError(_("A CSV file is required during creation."))
            # Ensure it's a CSV file by checking the file type
            if not csv_file.name.endswith('.csv'):
                raise ValidationError(_("File must be a CSV."))
            
        if csv_file:
            try:
                items_data = parse_psychometric_csv(csv_file=csv_file)
                created_items = []
                for item_data in items_data:
                    item = PsychometricItem.objects.create(**item_data)
                    created_items.append(item.uid)

                # Associate created items with the Psychometric instance
                # existing_items = []
                # if self.instance.pk:
                #     existing_items = list(self.instance.items.all().values_list('uid',flat=True))
                # else:
                existing_items = [item.uid for item in cleaned_data.get('items')] if cleaned_data.get('items') else []
                    
                psyitems = existing_items + created_items  # Combine existing and newly created items
                cleaned_data['items'] = PsychometricItem.objects.filter(uid__in=psyitems)


            except ValidationError as e:
                raise ValidationError(_(str(e)))
                
        return cleaned_data


class PsychometricAdmin(admin.ModelAdmin):
    form = PsychometricAdminForm
    list_per_page = 10
    filter_horizontal = ('items',)
    list_display = ('id', 'uid', 'tenant_id','name', 'description')
    search_fields = ('name',)


admin.site.register(Psychometric, PsychometricAdmin)


class PsychometricItemAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id', 'section', 'subsection')
    search_fields = ('section', 'subsection')
    ordering = ('-id',)

admin.site.register(PsychometricItem, PsychometricItemAdmin)


# class UserTestConfigsAdminForm(forms.ModelForm):
#     class Meta:
#         model = UserTestConfigs
#         fields = '__all__'

#     tenant_id = forms.ChoiceField(
#         choices=Tenant.get_tenant_choices(),  # Fetch all tenants from the database
#         required=True,  # Set this to True or False depending on your requirements
#         help_text=_("Select the tenant."),
#         initial=None
#     )


#     def clean(self):
#         cleaned_data = super().clean()
#         tenant_id = cleaned_data.get("tenant_id")

#         tenant = Tenant.objects.get(uid=tenant_id)
#         try:
#             user = get_user_via_identity(
#                 tenant=tenant,
#                 identity_type="deepchat_unique_id",
#                 identity_value=user_email
#             )
#             if not user:
#                 raise ValidationError("Invalid user email!.")
#         except:
#             raise ValidationError("Invalid user email!.")
        

#         cleaned_data['user_id'] = user.uid


#         test = Test.objects.filter(tenant_id=tenant_id, test_code=test_code, deleted=False).first()
#         # Validate test_code based on tenant_id
#         if not test:
#             raise ValidationError("Invalid test code for the given tenant.")
        
#         cleaned_data['test_title'] = test.title


#         if cleaned_data.get('access_code'):
#             if UserTestConfigs.objects.filter(tenant_id=tenant_id, access_code=self.access_code).exists():
#                 raise ValidationError("The access code is already taken. Please choose a unique access code.")

#         return cleaned_data

# class UserTestConfigsAdmin(TenantAwareModelAdmin):
#     list_display = ('id','client_name', 'member_emails','report_on', 'access_code')
#     search_fields = ('client_name', 'member_emails','access_code')

# admin.site.register(UserTestConfigs, UserTestConfigsAdmin)


@admin.register(TestAttemptSession)
class TestAttemptSessionAdmin(TenantAwareModelAdmin):
    list_display = (
        "id", 
        "get_client_name", 
        "get_test_code", 
        "get_title", 
        "get_user_email", 
        "test_score", 
        "status", 
        "started_at", 
        "finished_at"
    )
    search_fields = ("participant_id", "test_id", "test_invite_id")
    list_filter = ("status", "is_report_sent_to_email", "is_report_sent_to_whatsapp")
    list_per_page = 10
    ordering = ('-id',)


    def get_client_name(self, obj):
        # Assuming fetch_client_by_user_id(participant_id) is a function that fetches the client name
        return get_client_info_from_user_detail(
            tenant_id=obj.tenant_id,
            user_uid=obj.participant_id
            )
    get_client_name.short_description = "Client Name"
    
    def get_test_code(self, obj):
        test = Test.objects.filter(deleted=False,uid=obj.test_id).first()
        if test:
            return test.test_code
        else:
            return None
    get_test_code.short_description = "Test Code"
    
    def get_title(self, obj):
        test = Test.objects.filter(deleted=False,uid=obj.test_id).first()
        if test:
            return test.title
        else:
            return None
    get_title.short_description = "Test Title"

    def get_user_email(self, obj):
        user_att = UserAttribute.objects.get(deleted=False, user_id=obj.participant_id)
        if user_att.attributes.get('email'):
            return user_att.attributes.get('email')
        else:
            return None
    get_user_email.short_description = "User Email"
