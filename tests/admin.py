from django.contrib import admin 
from import_export.admin import ExportActionMixin
from tests.models import Test, TestQuestion, Psychometric, PsychometricItem, TestAttemptSession, TestQuestionResponse
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
import csv
from openpyxl import Workbook
from django.http import HttpResponse
import json
from tests.helpers import format_game_json_to_string
from .models import PsychometricReportSection, PsychometricReportSubsection
from django.db import models
from io import TextIOWrapper

import logging

logger = logging.getLogger('main')

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
    list_display = ('uid','test_code','title','test_type','scenario_case','interaction_mode','page_name','client_name','competency_group','area_domain','tab_category','deleted','calculate_culture', 'psychometric','psychometric_report_config','start_with_user')
    search_fields = ('test_code','title','uid','tab_category','competency_group','area_domain')
    list_editable = ('deleted','calculate_culture','page_name','client_name','competency_group','area_domain','psychometric','psychometric_report_config','tab_category')
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
                # Parse CSV to extract PsychometricItem data
                items_data = parse_psychometric_csv(csv_file=csv_file)

                # Create the Psychometric instance temporarily to get its pk
                with transaction.atomic():
                    # Save the Psychometric instance temporarily to fetch its pk
                    psychometric_instance = self.instance
                    psychometric_instance.save()

                    # Prepare a list of PsychometricItem instances to be created
                    psychometric_items = []
                    for item_data in items_data:
                        # Assuming item_data is a dictionary with field names matching the model
                        psychometric_item = PsychometricItem(
                            **item_data,
                            psychometric=psychometric_instance  # Associate these items with the current Psychometric instance
                        )
                        psychometric_items.append(psychometric_item)

                    # Use bulk_create for efficient database insertions
                    PsychometricItem.objects.bulk_create(psychometric_items)

                    # Optionally, store items_data if you want to reference them later
                    cleaned_data['items_data'] = items_data

                    # After bulk_create, manually handle saving the Psychometric instance if needed
                    # If necessary, save the Psychometric instance after items are created

            except ValidationError as e:
                raise ValidationError(_(f"Error parsing CSV file: {e}"))
            
        return cleaned_data            


class PsychometricAdmin(admin.ModelAdmin):
    form = PsychometricAdminForm
    list_per_page = 10
    # filter_horizontal = ('items',)
    list_display = ('id', 'uid', 'tenant_id','name', 'description')
    search_fields = ('name',)


admin.site.register(Psychometric, PsychometricAdmin)


class PsychometricItemAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id', 'psychometric','section', 'subsection')
    search_fields = ('section', 'subsection','psychometric')
    list_filter = ('psychometric',)
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

class ScenarioCaseFilter(admin.SimpleListFilter):
    title = "Scenario Case"
    parameter_name = "scenario_case"

    def lookups(self, request, model_admin):
        # Fetch unique scenario cases
        scenario_cases = set(Test.objects.filter(deleted=False).values_list('scenario_case', flat=True))
        return [(case, case) for case in scenario_cases if case]

    def queryset(self, request, queryset):
        # Filter queryset based on selected scenario case
        scenario_case = self.value()
        if scenario_case:
            test_ids = Test.objects.filter(scenario_case=scenario_case, deleted=False).values_list('uid', flat=True)
            return queryset.filter(test_id__in=test_ids)
        return queryset
    
class TestTypeFilter(admin.SimpleListFilter):
    title = "Test Type"
    parameter_name = "test_type"

    def lookups(self, request, model_admin):
        # Fetch unique Test Types
        test_types = set(Test.objects.filter(deleted=False).values_list('test_type', flat=True))
        return [(testtype, testtype) for testtype in test_types if testtype]

    def queryset(self, request, queryset):
        # Filter queryset based on selected test type
        test_type = self.value()
        if test_type:
            test_ids = Test.objects.filter(test_type=test_type, deleted=False).values_list('uid', flat=True)
            return queryset.filter(test_id__in=test_ids)
        return queryset

@admin.register(TestAttemptSession)
class TestAttemptSessionAdmin(TenantAwareModelAdmin):
    list_display = (
        "id", 
        "tenant_id",
        "get_client_name", 
        "get_test_code", 
        "get_test_title", 
        "get_test_type",
        "get_scenario_case",  # New field
        "get_user_email", 
        "test_score", 
        "status", 
        "started_at", 
        "finished_at"
    )
    search_fields = ("participant_id", "test_id", "test_invite_id")
    list_filter = (
        "status", 
        "is_report_sent_to_email", 
        "is_report_sent_to_whatsapp", 
        TestTypeFilter,
        ScenarioCaseFilter,  # New filter
    )
    list_per_page = 10
    ordering = ('-id',)
    actions = ["export_as_csv", "export_as_excel"]

    def get_queryset(self, request):
        # Fetch the original queryset
        queryset = super().get_queryset(request)
        
        # Extract unique test_ids from the queryset
        test_ids = queryset.values_list('test_id', flat=True)
        
        # Fetch existing Test objects
        existing_tests = Test.objects.filter(uid__in=test_ids, deleted=False)
        self.tests_cache = {test.uid: test for test in existing_tests}
        
        # Exclude rows where the Test is not found
        queryset = queryset.filter(test_id__in=self.tests_cache.keys())

        # Fetch UserAttributes for participant_ids
        participant_ids = queryset.values_list('participant_id', flat=True)
        self.user_attributes_cache = {
            ua.user_id: ua for ua in UserAttribute.objects.filter(user_id__in=participant_ids, deleted=False)
        }
        return queryset
    

    def get_client_name(self, obj):
        return get_client_info_from_user_detail(
            tenant_id=obj.tenant_id,
            user_uid=obj.participant_id
        )
    get_client_name.short_description = "Client Name"

    def get_test_code(self, obj):
        test = self.tests_cache.get(obj.test_id)
        return test.test_code if test else None
    get_test_code.short_description = "Test Code"

    def get_test_title(self, obj):
        test = self.tests_cache.get(obj.test_id)
        return test.title if test else None
    get_test_title.short_description = "Test Title"

    def get_scenario_case(self, obj):
        test = self.tests_cache.get(obj.test_id)
        return test.scenario_case if test else None
    get_scenario_case.short_description = "Scenario Case"

    def get_test_type(self, obj):
        test = self.tests_cache.get(obj.test_id)
        return test.test_type if test else None
    get_test_type.short_description = "Test Type"

    def get_user_email(self, obj):
        user_att = self.user_attributes_cache.get(obj.participant_id)
        if user_att and user_att.attributes.get('email'):
            return user_att.attributes.get('email')
        return None
    get_user_email.short_description = "User Email"


    def export_as_csv(self, request, queryset):
        return self.export_file(request, queryset, file_type="csv")

    def export_as_excel(self, request, queryset):
        return self.export_file(request, queryset, file_type="xlsx")
    

    def export_file(self, request, queryset, file_type):

        # File setup
        response = HttpResponse(content_type="text/csv" if file_type == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = f'attachment; filename="test_attempt_sessions.{file_type}"'

        # Writer setup
        writer = csv.writer(response) if file_type == "csv" else Workbook()
        if file_type == "xlsx":
            sheet = writer.active
            sheet.title = "Test Attempt Sessions"

        
        
        # Determine the maximum number of questions across all rows
        max_questions = 0
        questions_responses = {}
        only_game = False
        for obj in queryset:
            test = self.tests_cache.get(obj.test_id)
            test_type = test.test_type if test else None

            if test_type == "test":
                questions = TestQuestion.objects.filter(test_id=test.uid,deleted=False).order_by('id')
                responses = TestQuestionResponse.objects.filter(
                    test_attempt_session_id=obj.uid,
                    deleted=False
                ).order_by('id')
                data = [(q.question, r.response_text) for q, r in zip(questions, responses)]
            elif test_type in ["dynamic_discussion_thread", 'orchestrated_conversation']:
                responses = TestQuestionResponse.objects.filter(
                    test_attempt_session_id=obj.uid,
                    deleted=False
                )
                if test.scenario_case == 'game':
                    data = []
                    for r in responses:
                        question_text = ""
                        try:
                            question= json.loads(r.question_text)
                            question_text += format_game_json_to_string(question)

                            if question.get('end_message'):
                                question_text += question.get('end_message')
                                if question.get('feedback'):
                                    question_text += f"\n\n Feedback: {question.get('feedback')}"
                                
                                only_game= True


                        except Exception as e:
                            logger.exception(e)
                            question_text = r.question_text

                        data.append(((question_text or "").strip(), r.response_text))

                else:
                    # For non-'game', pair bot questions with user responses
                    bot_questions = list(responses.exclude(responder_type="user").order_by('id').values_list('response_text',flat=True))
                    user_responses = list(responses.filter(responder_type="user").order_by('id').values_list('response_text',flat=True))

                    # Pair bot questions with user responses sequentially
                    first_question = ""

                    for msg in test.orchestrated_conversation_details['initial_messages']:
                        first_question += f"{msg}\n\n"

                    final_bot_question = []
                    if len(first_question) > 0:
                        final_bot_question.append(first_question)

                    final_bot_question.extend(bot_questions)
                    print(len(final_bot_question), len(user_responses))

                    data = []
                    for bot, user in zip(final_bot_question, user_responses):
                        question_text = bot or "No Question"
                        response_text = user or "No Response"
                        data.append((question_text, response_text))

            else:
                data = []

            max_questions = max(max_questions, len(data))
            questions_responses[obj.id] = data

        
        # question_headers = [
        #     f"Question{i+1}" for i in range(max_questions)
        # ]
        # response_headers = [
        #     f"Response{i+1}" for i in range(max_questions)
        # ]

        # Headers
        base_headers = [
            "ID", "Client Name", "Test Code", "Test Title", 
            "Scenario Case", "User Email", "Test Score", 
            "Status", "Started At", "Finished At"
        ]

        question_response_header = []
        for i in range(max_questions):
            question_response_header.append(f"Question {i+1}")
            question_response_header.append(f"Response {i+1}")

        if only_game:
            question_response_header = question_response_header[:-2]
            question_response_header.append(f"Final Message")

        headers = base_headers + question_response_header

        if file_type == "csv":
            writer.writerow(headers)
        else:
            sheet.append(headers)

        started_at = obj.started_at.replace(tzinfo=None) if obj.started_at else None
        finished_at = obj.finished_at.replace(tzinfo=None) if obj.finished_at else None

        # Process rows
        for obj in queryset:
            row = [
                obj.id, 
                self.get_client_name(obj), 
                self.get_test_code(obj), 
                self.get_test_title(obj), 
                self.get_scenario_case(obj), 
                self.get_user_email(obj), 
                obj.test_score, 
                obj.status, 
                started_at, 
                finished_at,
            ]
            question_response_data = questions_responses.get(obj.id, [])
            questions = [q for q, r in question_response_data]
            responses = [r for q, r in question_response_data]
            question_respones_set = []
            for q,r in question_response_data:
                question_respones_set.append(q)
                question_respones_set.append(r)

            row.extend(question_respones_set)
            # # Add questions and responses up to max_questions
            # row.extend(questions + [""] * (max_questions - len(questions)))
            # row.extend(responses + [""] * (max_questions - len(responses)))

            if file_type == "csv":
                writer.writerow(row)
            else:
                sheet.append(row)

        # Save and return response
        if file_type == "xlsx":
            writer.save(response)
        return response


    export_as_csv.short_description = "Export as CSV"
    export_as_excel.short_description = "Export as Excel"

class PsychometricReportAdminForm(forms.ModelForm):
    csv_file = forms.FileField(
        required=False,
        help_text=_("Upload a CSV file to create/update Psychometric report config")
    )


    class Meta:
        model = PsychometricReportSection
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get('csv_file')

            
        if csv_file and not csv_file.name.endswith('.csv'):
            raise ValidationError(_("File must be a CSV."))
        
        if csv_file:
            try:
                with transaction.atomic():
                    section = self.instance
                    section.save()

                    self.process_csv(csv_file=csv_file,section=section)
            except ValidationError as e:
                raise ValidationError(_(f"Error parsing CSV file: {e}"))
            
        return cleaned_data  


    def process_csv(self, csv_file, section:PsychometricReportSection):
        try:
            # Decode and read the CSV file
            decoded_file = TextIOWrapper(csv_file, encoding='utf-8')
            reader = csv.DictReader(decoded_file)
            name = section.name

            # Process the CSV rows and create subsections
            for row in reader:
                section_name = row.get('section_name')
                section_value = row.get('section_value')
                section_footer = row.get('section_footer')
                subsection_name = row.get('subsection_name')
                subsection_value = row.get('subsection_value')
                subsection_parent_name = row.get('subsection_parent_name')
                range_value = row.get('range')

                # If the section_name in the CSV matches the main section, update its value and footer
                if section_name == name:
                    if section_value or section_footer:
                        section.value = section_value
                        section.footer = section_footer
                        section.save()

                #creating section as a subsection to original section[name]
                if not subsection_name:
                    PsychometricReportSubsection.objects.update_or_create(
                        name=section_name,
                        section=section,
                        defaults={
                            'value': section_value,
                        }
                    )

                # Create or update Subsection under the corresponding Section
                if subsection_name:
                    parent = None
                    if subsection_parent_name:
                        parent = PsychometricReportSubsection.objects.filter(name=subsection_parent_name,section=section).first()

                    # Update or create the Subsection under the correct Section
                    PsychometricReportSubsection.objects.update_or_create(
                        name=subsection_name,
                        section=section,
                        defaults={
                            'value': subsection_value,
                            'parent': parent,
                            'range_value': range_value
                        }
                    )

        except Exception as e:
            raise ValidationError(f"Error processing CSV: {str(e)}") 


class SubsectionInline(admin.TabularInline):
    model = PsychometricReportSubsection
    extra = 1  # Start with 1 extra row for adding new subsections
    fields = ['name', 'value', 'parent']
    autocomplete_fields = ['parent']  # Use autocomplete for parent field, which is a ForeignKey
    show_change_link = True  # Allow users to edit the related subsection from this interface

class SectionAdmin(admin.ModelAdmin):
    form= PsychometricReportAdminForm
    list_display = ('uid','name', 'value', 'footer')
    search_fields = ('name', 'value')
    list_filter = ('name',)

    # Allow adding multiple subsections within the section form using inline editing
    inlines = [SubsectionInline]

    # Group fields and add description for non-technical users
    fieldsets = (
        (None, {
            'fields': ('name', 'value', 'footer','csv_file'),
            'description': 'Enter the section details. Add subsections below.'
        }),
    )

    # Customizing the admin interface for readability
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextInputWidget},
    }

class SubsectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'parent', 'value')
    search_fields = ('name', 'value')
    list_filter = ('section', 'parent')

    # Allow easy selection for parent and section via autocomplete
    autocomplete_fields = ['parent', 'section']

    # Add help text for non-technical users
    fieldsets = (
        (None, {
            'fields': ('name', 'section', 'parent', 'value', 'footer', 'range'),
            'description': 'Enter the subsection name and value. Optionally, choose a parent subsection.'
        }),
    )

# Registering the models in the admin panel
admin.site.register(PsychometricReportSection, SectionAdmin)
admin.site.register(PsychometricReportSubsection, SubsectionAdmin)
