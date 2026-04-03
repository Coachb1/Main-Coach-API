from django.utils import timezone
from django.contrib import admin
from import_export.admin import ExportActionMixin
from commons.db.admin_mixins import SearchablePaginatedInlineMixin
from commons.utils import sanitize_text
from identities.helpers import get_user_via_identity
from tenants.models import Tenant
from tests.admin_helpers import CSVValidationError, normalize_row_collections, upsert_cases, upsert_collections, validate_business_rules, validate_row
from django.db import transaction
from tests.models import (
    Test,
    TestQuestion,
    Psychometric,
    PsychometricItem,
    TestAttemptSession,
    TestQuestionResponse,
    TestReportConfig
)
from django.utils.translation import gettext_lazy as _
from tenants.admin import TenantAwareModelAdmin
from django.contrib import messages
from users.helpers import get_client_info_from_user_detail
from users.models import ClientUserInfo, UserAttribute
from openpyxl import Workbook
from django.http import HttpResponse
from tests.helpers import create_and_email_to_pilot_user, create_and_send_next_test, export_modules_to_csv, extract_transform_iq, format_game_json_to_string, process_test_pilot_user_csv
from .models import CaseMappings, Collection, ConceptSession, Course, CoursePackage, Module, ModuleProgress, PsychometricReportSection, PsychometricReportSubsection, TestMapping, TestRecommendation, UserProgress, UserTestMapping
from django.db import models
from django.shortcuts import render, redirect
from django.urls import path, reverse
from .models import TestPilotuser, TestPilotRecords
from .forms import BulkUpdateForm, CSVUploadForm, CollectionAdminForm, CourseAdminForm, CoursePackageAdminForm, ModuleForm, PsychometricAdminForm, PsychometricReportAdminForm
from django.utils.html import format_html
from import_export.resources import ModelResource
from import_export.fields import Field
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

import io
import csv
import json

import logging

logger = logging.getLogger("main")


class StartWithUserFilter(admin.SimpleListFilter):
    title = "Start with User"
    parameter_name = "Start with User"

    def lookups(self, request, model_admin):
        return (
            ("start_with_user", "Start With User"),
            ("does_not_start_with_user", "Does Not Start With User"),
        )

    def queryset(self, request, queryset):
        if self.value() == "start_with_user":
            return queryset.filter(
                orchestrated_conversation_details__isnull=False
            ).filter(orchestrated_conversation_details__start_with_user__isnull=False)
        if self.value() == "does_not_start_with_user":
            return queryset.filter(
                orchestrated_conversation_details__isnull=True
            ) | queryset.filter(
                orchestrated_conversation_details__start_with_user__isnull=True
            )
        return queryset


class OnlyCompetencyFilter(admin.SimpleListFilter):
    title = _("Competency Group")
    parameter_name = "only_competency"

    def lookups(self, request, model_admin):
        return (("has_competency", _("Has Competency")),)

    def queryset(self, request, queryset):
        if self.value() == "has_competency":
            return queryset.exclude(competency_group=None).exclude(
                competency_group__exact=""
            )
        return queryset

class HasDescriptionMediaFilter(admin.SimpleListFilter):
    title = 'Has Description Media'
    parameter_name = 'has_description_media'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(description_media__isnull=True).exclude(description_media__exact='')
        elif self.value() == 'no':
            return queryset.filter(description_media__isnull=True) | queryset.filter(description_media__exact='')
        return queryset


class TestAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = (
        "uid",
        "test_code",
        "deleted",
        "questions_link",
        "title",
        "description",
        'description_media',
        "test_type",
        "scenario_case",
        "interaction_mode",
        "page_name",
        "client_name",
        "competency_group",
        "area_domain",
        "tab_category",
        "calculate_culture",
        "psychometric",
        "psychometric_report_config",
        "personality_model",
        "start_with_user",
        "time_limit",
        "instruction_media_link",
        "notice_board",
        "generate_feedback",
        "is_personality_game"
    )
    search_fields = (
        "test_code",
        "title",
        "uid",
        "tab_category",
        "competency_group",
        "area_domain",
    )
    list_editable = (
        "deleted",
        'title',
        'description',
        'description_media',
        "calculate_culture",
        "page_name",
        "client_name",
        "competency_group",
        "area_domain",
        "psychometric",
        "psychometric_report_config",
        "personality_model",
        "tab_category",
        "time_limit",
        "instruction_media_link",
        "notice_board",
        "generate_feedback",
        "is_personality_game"
    )
    list_filter = (
        "deleted",
        "test_type",
        "scenario_case",
        "calculate_culture",
        "interaction_mode",
        "page_name",
        "client_name",
        "generate_feedback",
        "is_personality_game",
        StartWithUserFilter,
        OnlyCompetencyFilter,
        HasDescriptionMediaFilter
    )
    ordering = ("-id",)
    def questions_link(self, obj):
        url = (
            reverse("admin:tests_testquestion_changelist")
            + f"?test_id={obj.uid}"
        )
        return format_html('<a href="{}">View Questions</a>', url)

    questions_link.short_description = "Questions"

    def start_with_user(self, obj):
        start_with_user_message = (
            obj.orchestrated_conversation_details.get("start_with_user")
            if obj.orchestrated_conversation_details
            else None
        )
        start_with_user = False if start_with_user_message is None else True
        return start_with_user


class TestQuestionAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = (
        "uid",
        "test_id",
        "question_number",
        "question",
        "question_for",
        "deleted",
    )
    search_fields = ("test_id", "uid")
    list_editable = ("deleted",)
    list_filter = ("test_id",)


admin.site.register(Test, TestAdmin)
admin.site.register(TestQuestion, TestQuestionAdmin)


class PsychometricItemsInline(admin.TabularInline):
    model = PsychometricItem
    extra = 0  # Start with 1 extra row for adding new subsections
    show_change_link = (
        True  # Allow users to edit the related subsection from this interface
    )


class PsychometricAdmin(admin.ModelAdmin):
    form = PsychometricAdminForm
    inlines = [
        PsychometricItemsInline,
    ]
    list_per_page = 10
    # filter_horizontal = ('items',)
    list_display = ("id", "uid", "tenant_id", "name", "description")
    search_fields = ("name",)


admin.site.register(Psychometric, PsychometricAdmin)


# class PsychometricItemAdmin(admin.ModelAdmin):
#     list_per_page = 10
#     list_display = ('id', 'psychometric','section', 'subsection')
#     search_fields = ('section', 'subsection','psychometric')
#     list_filter = ('psychometric',)
#     ordering = ('-id',)

# admin.site.register(PsychometricItem, PsychometricItemAdmin)


class ScenarioCaseFilter(admin.SimpleListFilter):
    title = "Scenario Case"
    parameter_name = "scenario_case"

    def lookups(self, request, model_admin):
        # Fetch unique scenario cases
        scenario_cases = set(
            Test.objects.filter(deleted=False).values_list("scenario_case", flat=True)
        )
        return [(case, case) for case in scenario_cases if case]

    def queryset(self, request, queryset):
        # Filter queryset based on selected scenario case
        scenario_case = self.value()
        if scenario_case:
            test_ids = Test.objects.filter(
                scenario_case=scenario_case, deleted=False
            ).values_list("uid", flat=True)
            return queryset.filter(test_id__in=test_ids)
        return queryset


class TestTypeFilter(admin.SimpleListFilter):
    title = "Test Type"
    parameter_name = "test_type"

    def lookups(self, request, model_admin):
        # Fetch unique Test Types
        test_types = set(
            Test.objects.filter(deleted=False).values_list("test_type", flat=True)
        )
        return [(testtype, testtype) for testtype in test_types if testtype]

    def queryset(self, request, queryset):
        # Filter queryset based on selected test type
        test_type = self.value()
        if test_type:
            test_ids = Test.objects.filter(
                test_type=test_type, deleted=False
            ).values_list("uid", flat=True)
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
        "finished_at",
    )
    search_fields = ("participant_id", "test_id", "test_invite_id")
    list_filter = (
        "status",
        "is_report_sent_to_email",
        "is_report_sent_to_whatsapp",
        "finished_at",
        TestTypeFilter,
        ScenarioCaseFilter,  # New filter
    )
    list_per_page = 10
    ordering = ("-id",)
    actions = ["export_as_csv", "export_as_excel"]

    def get_queryset(self, request):
        # Fetch the original queryset
        queryset = super().get_queryset(request)

        # Extract unique test_ids from the queryset
        test_ids = queryset.values_list("test_id", flat=True)

        # Fetch existing Test objects
        existing_tests = Test.objects.filter(uid__in=test_ids, deleted=False)
        self.tests_cache = {test.uid: test for test in existing_tests}

        # Exclude rows where the Test is not found
        queryset = queryset.filter(test_id__in=self.tests_cache.keys())

        # Fetch UserAttributes for participant_ids
        participant_ids = queryset.values_list("participant_id", flat=True)
        self.user_attributes_cache = {
            ua.user_id: ua
            for ua in UserAttribute.objects.filter(
                user_id__in=participant_ids, deleted=False
            )
        }
        return queryset

    def get_client_name(self, obj):
        return get_client_info_from_user_detail(
            tenant_id=obj.tenant_id, user_uid=obj.participant_id
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
        if user_att and user_att.attributes.get("email"):
            return user_att.attributes.get("email")
        return None

    get_user_email.short_description = "User Email"

    def export_as_csv(self, request, queryset):
        return self.export_file(request, queryset, file_type="csv")

    def export_as_excel(self, request, queryset):
        return self.export_file(request, queryset, file_type="xlsx")

    def export_file(self, request, queryset, file_type):

        # File setup
        response = HttpResponse(
            content_type=(
                "text/csv"
                if file_type == "csv"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        )
        response["Content-Disposition"] = (
            f'attachment; filename="test_attempt_sessions.{file_type}"'
        )

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
                questions = TestQuestion.objects.filter(
                    test_id=test.uid, deleted=False
                ).order_by("id")
                responses = TestQuestionResponse.objects.filter(
                    test_attempt_session_id=obj.uid, deleted=False
                ).order_by("id")
                data = [
                    (q.question, r.response_text) for q, r in zip(questions, responses)
                ]
            elif test_type in [
                "dynamic_discussion_thread",
                "orchestrated_conversation",
            ]:
                responses = TestQuestionResponse.objects.filter(
                    test_attempt_session_id=obj.uid, deleted=False
                )
                if test.scenario_case == "game":
                    data = []
                    for r in responses:
                        question_text = ""
                        try:
                            question = json.loads(r.question_text)
                            question_text += format_game_json_to_string(question)

                            if question.get("end_message"):
                                question_text += question.get("end_message")
                                if question.get("feedback"):
                                    question_text += (
                                        f"\n\n Feedback: {question.get('feedback')}"
                                    )

                                only_game = True

                        except Exception as e:
                            logger.exception(e)
                            question_text = r.question_text

                        data.append(((question_text or "").strip(), r.response_text))

                else:
                    # For non-'game', pair bot questions with user responses
                    bot_questions = list(
                        responses.exclude(responder_type="user")
                        .order_by("id")
                        .values_list("response_text", flat=True)
                    )
                    user_responses = list(
                        responses.filter(responder_type="user")
                        .order_by("id")
                        .values_list("response_text", flat=True)
                    )

                    # Pair bot questions with user responses sequentially
                    first_question = ""

                    for msg in test.orchestrated_conversation_details[
                        "initial_messages"
                    ]:
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
            "ID",
            "Client Name",
            "Test Code",
            "Test Title",
            "Scenario Case",
            "User Email",
            "Test Score",
            "Status",
            "Started At",
            "Finished At",
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
            for q, r in question_response_data:
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


class SubsectionInline(admin.TabularInline):
    model = PsychometricReportSubsection
    extra = 1  # Start with 1 extra row for adding new subsections
    fields = ["name", "value", "parent", "range_value", "footer"]
    autocomplete_fields = [
        "parent"
    ]  # Use autocomplete for parent field, which is a ForeignKey
    show_change_link = (
        True  # Allow users to edit the related subsection from this interface
    )


class PsychometricReportConfigAdmin(admin.ModelAdmin):
    form = PsychometricReportAdminForm
    list_display = ("uid", "name", "value", "footer")
    search_fields = ("name", "value")
    list_filter = ("name",)

    # Allow adding multiple subsections within the section form using inline editing
    inlines = [SubsectionInline]

    # Group fields and add description for non-technical users
    fieldsets = (
        (
            None,
            {
                "fields": ("name", "value", "footer", "csv_file"),
                "description": "Enter the section details. Add subsections below.",
            },
        ),
    )

    # Customizing the admin interface for readability
    formfield_overrides = {
        models.TextField: {"widget": admin.widgets.AdminTextInputWidget},
    }


class SubsectionAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "parent", "value", "footer", "range_value")
    search_fields = ("name", "value")
    list_filter = ("section", "parent")

    # Allow easy selection for parent and section via autocomplete
    autocomplete_fields = ["parent", "section"]

    # Add help text for non-technical users
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "section",
                    "parent",
                    "value",
                    "footer",
                    "range_value",
                ),
                "description": "Enter the subsection name and value. Optionally, choose a parent subsection.",
            },
        ),
    )

    def has_module_permission(self, request):
        return False


# Registering the models in the admin panel
admin.site.register(PsychometricReportSection, PsychometricReportConfigAdmin)
admin.site.register(PsychometricReportSubsection, SubsectionAdmin)


class TestPilotRecordsInline(admin.TabularInline):
    model = TestPilotRecords
    extra = 1
    fields = ('test', 'sent_email', 'test_attempted', 'active')
    readonly_fields = ('test',)
    can_delete = True



class TestPilotUserAdmin(TenantAwareModelAdmin):
    list_display = ('id', 'name', 'email','targeted_skills' ,'industry', 'department', 'restart_status','preferences', 'frequency','view_records',"company", 'top_skills', 'history', 'leaderboard')
    list_filter = ('industry', 'department', 'restart')
    search_fields = ('name', 'email', 'industry', 'department')
    inlines = [TestPilotRecordsInline]
    
    def restart_status(self, obj):
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>',
                           'green' if obj.restart else 'red', 'Yes' if obj.restart else 'No')
    restart_status.short_description = "Restart"
    
    def view_records(self, obj):
        return format_html('<a href="/custom-admin/tests/testpilotrecords/?pilotuser__uid__exact={}" style="color: blue; font-weight: bold;">View Records</a>', obj.uid)
    view_records.short_description = "Test Records"

    ordering = ('-id',)
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'client', 'name', 'email')
        }),
        ('Professional Details', {
            'fields': ('industry', 'department', 'targeted_skills', 'objective')
        }),
        ('Additional Info', {
            'fields': ('key_stakeholders', 'situation', "company", 'top_skills', 'history', 'leaderboard', 'restart')
        }),
        ('Configrations', {
            'fields': ('preferences', 'frequency')
        }),
    )
    change_list_template = (
        "admin/testpilotusers/testpilotuser_changelist.html"  # Custom template for button
    )

    def get_urls(self):
        """Add custom URL for CSV upload."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "upload-csv/",
                self.admin_site.admin_view(self.upload_csv),
                name="upload_csv",
            ),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        """Handles CSV file upload with proper exception handling."""
        print('upload csv calling', request.method)
        if request.method == "POST":

            try:
                csv_file = request.FILES["csv_file"]

                tenant_id = request.POST.get("tenant_id")
                print(csv_file, tenant_id)
                

                # ✅ 3. Read and process the CSV file
                decoded_file = io.TextIOWrapper(csv_file, encoding="utf-8")
                reader = csv.DictReader(decoded_file)

                required_fields = ["Name", "Email", "Targeted Skills", "Frequency", "Perferences", "Same Intake"]

                # ✅ Check if file is empty
                if not reader.fieldnames:
                    messages.error(request, "CSV file is empty! Please upload a valid file.")
                    return redirect(request.get_full_path())

                # ✅ 4. Check if the CSV contains all required fields
                if not all(field in reader.fieldnames for field in required_fields):
                    r_fields = ",".join(required_fields)
                    messages.error(
                        request,
                        f"CSV is missing required fields: {r_fields} .",
                    )
                    return redirect(request.get_full_path())
                try:
                    process_test_pilot_user_csv(csv=reader, tenant_id=tenant_id)
                except Exception as e:
                    logger.exception(e)
                    messages.error(request, f"{e}")
                    return redirect(request.get_full_path())
                

                messages.success(
                    request,
                    f"CSV uploaded successfully!",
                )
                return redirect("..")

            except csv.Error:
                messages.error(
                    request, "Error processing CSV file. Please check the file format."
                )
            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {str(e)}")

            return redirect(request.get_full_path())  # Redirect back to admin

        else:
            form = CSVUploadForm()

        return render(
            request,
            "admin/testpilotusers/csv_upload.html",
            {"form": form, "title": "Upload CSV", "opts": self.model._meta, "popup": True},
        )


admin.site.register(TestPilotuser, TestPilotUserAdmin)


class TestPilotRecordsResource(ModelResource):
    id = Field(attribute='id', column_name='ID')
    created = Field(attribute='created', column_name='Created')
    pilotuser_name = Field(column_name='Pilot User Name')
    pilotuser_email = Field(column_name='Pilot User Email')
    test = Field(attribute='test', column_name='Test')
    sent_email = Field(column_name='Sent Email')
    test_attempted = Field(column_name='Test Attempted')
    scenario_case_type = Field(attribute='scenario_case_type', column_name='Scenario Case Type')

    class Meta:
        model = TestPilotRecords
        fields = ('id', 'created', 'test', 'scenario_case_type')  # Explicitly mentioned fields
        export_order = ('id', 'created', 'pilotuser_name', 'pilotuser_email', 'test', 'sent_email', 'test_attempted', 'scenario_case_type')

    def dehydrate_pilotuser_name(self, obj):
        return obj.pilotuser.name if obj.pilotuser else ""

    def dehydrate_pilotuser_email(self, obj):
        return obj.pilotuser.email if obj.pilotuser else ""

    def dehydrate_sent_email(self, obj):
        return "True" if obj.sent_email else "False"

    def dehydrate_test_attempted(self, obj):
        return "True" if obj.test_attempted else "False"


class TestPilotRecordsAdmin(ExportActionMixin,TenantAwareModelAdmin):
    resource_class = TestPilotRecordsResource
    list_display = ('id', 'created','get_pilotuser_name', 'get_pilotuser_email', 'test', 'sent_email', 'test_attempted','scenario_case_type', 'active')
    search_fields = ('pilotuser__name', 'test__name', 'pilotuser__email')
    list_filter = ('sent_email', 'test_attempted', 'active', 'created')
    ordering = ('id',)
    change_list_template = (
        "admin/testpilotrecords/testpilotrecord_changelist.html"  # Custom template for button
    )
    fieldsets = (
        ('Pilot User & Test', {
            'fields': ('pilotuser', 'test')
        }),
        ('Status', {
            'fields': ('sent_email', 'test_attempted', 'active')
        }),
        ('Additional Info', {
            'fields': ('body',)
        }),
    )

    @admin.display(description='Pilot User Email')
    def get_pilotuser_email(self, obj):
        return obj.pilotuser.email if obj.pilotuser else None
    @admin.display(description='Pilot User Email')
    def get_pilotuser_name(self, obj):
        return obj.pilotuser.name if obj.pilotuser else None
    
    def get_urls(self):
        """Add custom URL for CSV upload."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "new-test-creation/",
                self.admin_site.admin_view(self.new_test_creation),
                name="new_test_creation",
            ),
        ]
        return custom_urls + urls

    def new_test_creation(self, request):
        """Handles CSV file upload with proper exception handling."""
        print('upload csv new testcalling', request.method)
        if request.method == "POST":

            try:
                csv_file = request.FILES["csv_file"]
             

                # ✅ 3. Read and process the CSV file
                decoded_file = io.TextIOWrapper(csv_file, encoding="utf-8")
                reader = csv.DictReader(decoded_file)

                required_fields = ["Email", "Test Type", 'Send Email']

                # ✅ Check if file is empty
                if not reader.fieldnames:
                    messages.error(request, "CSV file is empty! Please upload a valid file.")
                    return redirect(request.get_full_path())

                # ✅ 4. Check if the CSV contains all required fields
                if not all(field in reader.fieldnames for field in required_fields):
                    r_fields = ",".join(required_fields)
                    messages.error(
                        request,
                        f"CSV is missing required fields: {r_fields} .",
                    )
                    return redirect(request.get_full_path())
                

                # 5. check if TestType is valid
                invalid_row = []
                test_sequence = ["dynamic_game", "static_role_play_soft", "dynamic_start_with_user", 
                    "static_hard", "static_soft", "normal_dynamic_test_hard", 
                    "static_role_play_hard", "normal_dynamic_test_soft", "case", "checkin",
                    "static_game"]
                rows = list(reader)
                for row in rows:
                    if row['Test Type'] not in test_sequence:
                        invalid_row.append(f"invalid Test Type detacted for email: {row['Email']} with Test Type: {row['Test Type']}")


                if len(invalid_row) > 0:
                    messages.error(
                        request,
                        f"Validation Error: {invalid_row} .",
                    )
                    return redirect(request.get_full_path())
                print(f"reader: {reader}, pilot: {row['Email']}, test_type: {row['Test Type']} send email: {row['Send Email'].lower().strip() == 'true'}")
                
                try:
                    create_and_send_next_test(reader=rows)
                except Exception as e:
                    logger.exception(e)
                    messages.error(request, f"{e}")
                    return redirect(request.get_full_path())
                

                messages.success(
                    request,
                    f"New Test created successfully!",
                )
                return redirect("..")

            except csv.Error:
                messages.error(
                    request, "Error processing CSV file. Please check the file format."
                )
            except Exception as e:
                logger.exception(e)
                messages.error(request, f"An unexpected error occurred: {str(e)}")

            return redirect(request.get_full_path())  # Redirect back to admin

        else:
            form = CSVUploadForm(show_tenant_id=False)

        return render(
            request,
            "admin/testpilotrecords/csv_upload.html",
            {"form": form, "title": "New Test Creation", "opts": self.model._meta, "popup": True},
        )

admin.site.register(TestPilotRecords, TestPilotRecordsAdmin)

@admin.register(TestRecommendation)
class TestRecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "recommended_test", "origin_test", "test_case", "session_id", "user_id")
    search_fields = ("recommended_test__uid", "origin_test__uid", "test_case", "session_id", "user_id")
    list_filter = ("test_case",)
    ordering = ("id",)


@admin.register(TestReportConfig)
class TestReportConfigAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'test', 'skill_rating', 'culture_rating', 'competency_metrix', 'feedback_summary',
        'rating_summary', 'flash_card', 'mindmap', 'speech_metrix', 'powerfiller_words',
        'skill_explanation', 'culture_explanation', 'psychometric_culture_explanation',
        'psychometric_culture_rating'
    )
    search_fields = ('test__title', 'test__test_code') 
    autocomplete_fields = ['test']
    list_editable = (
        'skill_rating', 'culture_rating', 'competency_metrix', 'feedback_summary',
        'rating_summary', 'flash_card', 'mindmap', 'speech_metrix', 'powerfiller_words',
        'skill_explanation', 'culture_explanation', 'psychometric_culture_explanation',
        'psychometric_culture_rating'
    )
    ordering = ('-id',)  





@admin.register(TestMapping)
class TestMappingAdmin(admin.ModelAdmin, ExportActionMixin):
    list_display = ('id','test', 'client', 'page_name', 'tab_category', 'domain','tab_sticker')
    change_list_template = "admin/testmapping/testmapping_changelist.html"  # custom template for button
    search_fields = ('test__title', 'test__test_code', 'client__client_name', 'page_name', 'tab_category', 'domain')
    list_filter = ('test', 'client', 'page_name', 'tab_category', 'domain')
    list_editable = ('page_name', 'tab_category', 'domain','tab_sticker')
    autocomplete_fields = ['test']
    ordering = ('-id',)
    actions = ['bulk_update_fields']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='testmapping-upload-csv'),
        ]
        return custom_urls + urls

    def bulk_update_fields(self, request, queryset):
        form = None

        if 'apply' in request.POST:
            form = BulkUpdateForm(request.POST)
            if form.is_valid():
                data = form.cleaned_data
                updated = 0

                for obj in queryset:
                    if data['tab_category']:
                        obj.tab_category = data['tab_category']
                    if data['tab_sticker']:
                        obj.tab_sticker = data['tab_sticker']
                    if data['tab_difficulty']:
                        obj.tab_difficulty = data['tab_difficulty']
                    if data['tab_type']:
                        obj.tab_type = data['tab_type']
                    obj.save()
                    updated += 1

                self.message_user(request, f"Successfully updated {updated} records.")
                return redirect(request.get_full_path())

        else:
            form = BulkUpdateForm(initial={'_selected_action': request.POST.getlist(ACTION_CHECKBOX_NAME)})

        return render(request, "admin/testmapping/testmapping_bulk_update.html", {
            'items': queryset,
            'form': form,
            'title': "Bulk Update TestMapping Fields"
        })

    def upload_csv(self, request):
        if request.method == "POST":
            # form = CSVUploadForm(request.POST or None, request.FILES or None, show_tenant_id=False)
            # if form.is_valid():
            try:
                csv_file = io.TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8')
                reader = csv.DictReader(csv_file)
                required_fields = ["test_code",'tab_category','page_name']

                # ✅ Check if file is empty
                if not reader.fieldnames:
                    messages.error(request, "CSV file is empty! Please upload a valid file.")
                    return redirect(request.get_full_path())

                # ✅ 4. Check if the CSV contains all required fields
                if not all(field in reader.fieldnames for field in required_fields):
                    r_fields = ",".join(required_fields)
                    messages.error(
                        request,
                        f"CSV is missing required fields: {r_fields} .",
                    )
                    return redirect(request.get_full_path())
                created_count = 0
                for index, row in enumerate(reader, start=1):
                    try:
                        test_name = row.get('test_code','').strip()
                        test = Test.objects.get(test_code=test_name)
                    except Test.DoesNotExist:
                        messages.warning(request, f"[Row {index}] Test not found: '{row.get('test_code')}'")
                        continue

                    client = None
                    client_name = row.get('client', '').strip()
                    if client_name:
                        try:
                            client = ClientUserInfo.objects.get(client_name=client_name)
                        except ClientUserInfo.DoesNotExist:
                            messages.warning(request, f"[Row {index}] Client not found: '{client_name}'")
                            continue

                    try:
                        obj, created = TestMapping.objects.get_or_create(
                            test=test,
                            client=client,
                            page_name=row.get('page_name', '').strip() or None,
                            defaults={
                                'tab_category': row.get('tab_category', '').strip() or None,
                                'domain': row.get('domain', '').strip() or None,
                                'tab_sticker': row.get('tab_sticker', '').strip() or None,
                                'tab_difficulty': row.get('tab_difficulty', '').strip() or 'Difficuly Level : Intermediate',
                                'tab_type': row.get('tab_type', '').strip() or 'simulation',
                            }
                        )
                        if created:
                            created_count += 1
                    except Exception as e:
                        messages.warning(request, f"[Row {index}] Error creating mapping: {e}")
            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {str(e)}")
                return redirect(request.get_full_path())
            self.message_user(request, f"Successfully uploaded {created_count} test mappings.", level=messages.SUCCESS)
            return redirect("..")
        else:
            form =  CSVUploadForm(show_tenant_id=False)

        context = {
            "form": form,
            "opts": self.model._meta,
            "title": "Upload CSV for Test Mappings",
        }
        return render(request, "admin/testmapping/csv_upload.html", context)



@admin.register(UserTestMapping)
class UserTestMappingAdmin(admin.ModelAdmin, ExportActionMixin):
    list_display = ('id', 'user', 'get_tests', 'sticker')
    search_fields = ('user__name', 'sticker')
    filter_horizontal = ('tests',)
    change_list_template = "admin/usertestmapping/usertestmapping_changelist.html"  # custom template for button
    autocomplete_fields = ['tests']
    ordering = ('-id',)
    
    def get_tests(self, obj):
        return ", ".join([t.test_code for t in obj.tests.all()])
    get_tests.short_description = 'Tests'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='usertestmapping-upload-csv'),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        if request.method == "POST":
            try:
                csv_file = io.TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8')
                reader = csv.DictReader(csv_file)
                required_fields = ["email",'test_codes','sticker']

                # ✅ Check if file is empty
                if not reader.fieldnames:
                    messages.error(request, "CSV file is empty! Please upload a valid file.")
                    return redirect(request.get_full_path())

                # ✅ 4. Check if the CSV contains all required fields
                if not all(field in reader.fieldnames for field in required_fields):
                    r_fields = ",".join(required_fields)
                    messages.error(
                        request,
                        f"CSV is missing required fields: {r_fields} .",
                    )
                    return redirect(request.get_full_path())
                created_count = 0
                for index, row in enumerate(reader, start=1):
                    test_list = [code.strip() for code in row.get('test_codes','').strip().split(',') if code.strip()]
                    
                    tests = Test.objects.filter(client_mappings__isnull=False, test_code__in=test_list).distinct()
                    if tests.count == 0:
                        messages.warning(request, f"[Row {index}] Tests not found: '{row.get('test_codes')}'")
                        continue

                    tenant = Tenant.objects.get(uid=tests.first().tenant_id)
                    user = get_user_via_identity(
                        tenant=tenant,
                        identity_type="deepchat_unique_id",
                        identity_value=row.get('email')
                    )
                    if not user:
                        messages.warning(request, f"[Row {index}] Error creating mapping: User not found with {row.get('email')}")
                        continue


                    try:
                        obj, created = UserTestMapping.objects.get_or_create(
                            user=user
                        )
                        obj.sticker = row.get('sticker')
                        obj.save()

                        obj.tests.set(tests)

                        if created:
                            created_count += 1
                    except Exception as e:
                        messages.warning(request, f"[Row {index}] Error creating mapping: {e}")
            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {str(e)}")
                return redirect(request.get_full_path())
            self.message_user(request, f"Successfully uploaded {created_count} user test mappings.", level=messages.SUCCESS)
            return redirect("..")
        else:
            form =  CSVUploadForm(show_tenant_id=False)

        context = {
            "form": form,
            "opts": self.model._meta,
            "title": "Upload CSV for User Test Mappings",
        }
        return render(request, "admin/usertestmapping/csv_upload.html", context)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    form = CourseAdminForm
    list_display = ("id", "course_package", "title", "sub_title", "type", "view_modules_link")
    list_filter = ("type", )
    search_fields = ("title", "sub_title")
    ordering = ("-id",)
    actions = ["export_modules_to_csv"]

    def course_package(self, obj):
        """
        Returns the course package name if it exists.
        """
        package = ""
        for pkage in obj.packages.all():
            package += f"{pkage.title}, "
        return package.rstrip(", ")
    course_package.short_description = "Course Package"


    def view_modules_link(self, obj):
        url = (
            reverse("admin:tests_module_changelist")
            + f"?course__id__exact={obj.id}"
        )
        return format_html('<a href="{}">View Modules</a>', url)

    view_modules_link.short_description = "Modules"

    def export_modules_to_csv(self, request, queryset):
        """
        Export all modules belonging to the selected courses as CSV.
        """
        return export_modules_to_csv(queryset)
    
    def save_model(self, request, obj, form, change):
        """
        Overrides save to process CSV after saving course.
        """
        super().save_model(request, obj, form, change)

        csv_file = form.cleaned_data.get("upload_csv")
        if not csv_file:
            return  # no CSV uploaded, skip

        try:
            decoded_file = csv_file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded_file))
            JSON_FIELDS = {"card_button_config"}
            created_count, updated_count = 0, 0
            skiped_rows = []
            for row in reader:
                cleaned = {}
                for index, (k, v) in enumerate(row.items()):
                    key = k.strip().replace(" ", "_").lower()
                    value = v.strip() if v.strip() else None


                    if not value:
                        cleaned[key] = None
                        continue

                    if not (key.startswith("transform_iq") or key.startswith("iq")):
                        value = sanitize_text(value)

                    # Parse JSON fields
                    if key in JSON_FIELDS:
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            print(f"❌ Invalid JSON in {key}: {value}")
                            value = None


                    cleaned[key] = value
                    
                row = cleaned
                print('row', row)
                module_title = row.get("name")
                if not module_title or not str(module_title).strip():
                    skiped_rows.append(index+1)
                    continue # skip invalid rows
                chapter_type = row.get("chapter_type").strip().upper() if row.get("chapter_type") else "BOOK"

                test = None
                if row.get('test_code'):
                    test = Test.objects.filter(deleted=False, test_code=row.get('test_code')).first()


                # now we are checking two case where client name 1 and others like transform iq overview are numbered as 
                # second without clientname and without numbered
                # Client Name 1	Transform IQ Overview 1	IQ-Tech Lead 1	IQ-Operations Lead 1	IQ-Finance Lead 1	IQ-People Lead 1	IQ-Core Business Lead 1
                print(row.keys())
                # detect all client indexes dynamically
                iq = extract_transform_iq(row)

                # Define all possible fields and their mappings from the row
                field_mapping = {
                    "module_name": module_title,
                    "test": test,
                    "chapter_type": chapter_type,
                    "author": row.get("author"),
                    "tag": row.get("industry"),
                    "description": row.get("description"),
                    "business_outcome": row.get("business_outcome"),
                    "implementation_complexity": row.get("implementation_complexity"),
                    "unexpected_outcome": row.get("unexpected_outcome"),
                    "function": row.get("function"),
                    "video_url": row.get("video_link"),
                    "audio_link": row.get("audio_link"),
                    "image_link": row.get("image_link"),
                    "embed_link": row.get("report_link"),
                    "list_name": row.get("category"),
                    "emerging_player": row.get("latest/recent") or row.get("emerging_player"),
                    "startup": row.get("startup"),
                    "key_words": row.get("keywords"),
                    "transform_iq": iq,
                    "sticker": row.get("sticker"),
                    "card_button_config": row.get("card_button_config"),
                }

                # 1. Filter out fields that are None or empty strings to ensure we only update "available" data
                # 2. Special handling for booleans (like emerging_player and startup)
                defaults = {}
                for field, value in field_mapping.items():
                    if value is not None and str(value).strip() != "":
                        # Process specific fields that need formatting
                        if field in ["emerging_player", "startup"]:
                            defaults[field] = str(value).strip().upper() == "TRUE"
                        elif field in ["key_words", "sticker"]:
                            defaults[field] = str(value).strip()
                        else:
                            defaults[field] = value
                    
                module, created = Module.objects.update_or_create(
                    title=module_title,
                    course=obj,  # attach to this course
                    defaults=defaults
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            self.message_user(
                request,
                f"✅ {created_count} modules created and {updated_count} updated from CSV. \n skiped rows: {skiped_rows}",
                level=messages.SUCCESS,
            )

        except Exception as e:
            self.message_user(request, f"❌ CSV processing failed: {e}", level=messages.ERROR)

    

class CourseInline(admin.TabularInline):
    """
    Inline to show/add courses inside a package.
    Admin can either select existing courses (autocomplete)
    or create new ones (with inline module support).
    """
    model = CoursePackage.courses.through  # M2M link
    extra = 1
    autocomplete_fields = ("course",)  # search existing courses


@admin.register(CoursePackage)
class CoursePackageAdmin(TenantAwareModelAdmin):  # keep TenantAwareModelAdmin if needed
    form = CoursePackageAdminForm
    list_display = ('id', 'uid', "title", "sub_title", "client", 'image_link')
    list_filter = ("client",)
    search_fields = ("title", "sub_title", "client__client_name")
    ordering = ("title",)
    inlines = [CourseInline]
    autocomplete_fields = ("client",)  # enable search dropdown for clients
    exclude = ("courses",)  # hide default M2M widget


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    form = ModuleForm
    list_display = ("title", "module_name", "course", "author", "tag")
    list_filter = ("course", "author", "tag")
    search_fields = ("title", "module_name", "course__title", "author")
    ordering = ("course", "title")
    list_per_page = 10


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "start_time", "end_time", "modules_completed")
    list_filter = ("course", "modules_completed")
    search_fields = ("user__name", "course__title")
    ordering = ("-start_time",)


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ("user_progress", "module", "status", "start_time", "end_time")
    list_filter = ("status", "module__course")
    search_fields = ("user_progress__user__name", "module__title", "module__course__title")
    ordering = ("-start_time",)

class CaseMappingsInline(admin.TabularInline):
    model = CaseMappings
    extra = 1
    fields = ('tab_name', "action_name", 'embed_link', "transform_iq")  # fields shown inline
    # item_per_page = 10

@admin.register(CaseMappings)
class CaseMappingAdmin(admin.ModelAdmin):
    list_display = ("id", "collection", "tab_name", "embed_link", "transform_iq", "action_name", "sticker")
    search_fields = ("tab_name",)
    list_filter  = ('action_name',)
    ordering = ("-id",)

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    form = CollectionAdminForm
    list_display = ("id", "collection_name", "client_name", "view_case_items_link", 
                    'action_tab_info_preview', 'iframe_link', 'iframe_title', 'iframe_subtitle')
    search_fields = ("collection_name",)
    list_filter = ("collection_name",)
    ordering = ("-id",)
    inlines = [CaseMappingsInline]
    change_list_template = "admin/collections/collections_change_list.html"
    change_form_template = "admin/collections/collection_change_form.html"

    fieldsets = (
        ('Basic Information', {
            'fields': ('uid', 'deleted', 'collection_name', 'heading'),
            'description': format_html(
                """
                <div style="line-height:1.6;">
                    <strong>Basic details about the collection</strong><br><br>
                    • <b>UID</b>: Auto-generated and read-only<br>
                    • <b>Heading</b>: Optional title displayed above the tab in UI
                </div>
                """
            )
        }),

        ('Tab Configuration', {
            'fields': ('action_tab_info',),
            'description': format_html(
                """
                <div style="line-height:1.6;">
                    <strong>Configure the main pillar/tab behavior</strong><br><br>

                    <b>General Rules:</b><br>
                    • If no case mappings exist → put tab type = <b>system</b><br>
                    • For case mappings, <b>action_name</b> must start with:
                    <code>CONCEPTS_</code><br><br>

                    <b>Special Cases:</b><br>
                    • For <b>JobAid buttons</b> → use <code>jobaid_uid</code> as action_name<br><br>

                    <b>System Actions (NO prefix):</b><br>
                    <ul style="margin:6px 0 0 18px;">
                        <li><b>AI Case</b> → <code>SHOW_AI_CASES</code></li>
                        <li><b>Landscape</b> → <code>AI_LANDSCAPE</code></li>
                        <li><b>Propose</b> → <code>INTERNAL_TRANSFORMATION_PROPOSE</code></li>
                        <li><b>Logs & Radar</b> → <code>INTERNAL_TRANSFORMATION_ALIGN</code></li>
                    </ul>
                </div>
                """
            )
        }),

        ('Default Iframe Configuration', {
            'fields': ('iframe_link', 'iframe_title', 'iframe_subtitle'),
            'description': format_html(
                """
                <div style="line-height:1.6;">
                    <strong>Iframe panel configuration</strong><br><br>
                    • <b>Link</b>: URL to be embedded<br>
                    • <b>Title</b>: Displayed above iframe<br>
                    • <b>Subtitle</b>: Supporting text below title
                </div>
                """
            )
        }),
    )
    readonly_fields = ('uid',)

    def action_tab_info_preview(self, obj):
        """Show a preview of the action_tab_info"""
        if obj.action_tab_info:
            button_count = len(obj.action_tab_info.get('buttons', []))
            tab_title = obj.action_tab_info.get('title', 'N/A')
            return format_html(
                '<strong>{}</strong><br><small>{} buttons</small>',
                tab_title, button_count
            )
        return "—"
    action_tab_info_preview.short_description = "Tab Info"

    def client_name(self, obj):
        if hasattr(obj, "client_users"):
            clients = obj.client_users.all()
            if clients:
                return ", ".join(str(c.client_name) for c in clients)
            return "—"
        return "—"
    client_name.short_description = "Client"

    def view_case_items_link(self, obj):
        url = (
            reverse("admin:tests_casemappings_changelist")
            + f"?collection__id__exact={obj.id}"
        )
        return format_html('<a href="{}">View Items</a>', url)
    view_case_items_link.short_description = "Case Items"

    # -------------------------------------------------------------------
    # EXPORT CSV
    # -------------------------------------------------------------------
    actions = ["export_to_csv"]

    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        filename = "collections_export.csv"
        response["Content-Disposition"] = f"attachment; filename={filename}"

        writer = csv.writer(response)
        writer.writerow(["Collection Name", "Tab Name", "Embed Link", "Transform IQ", 
                        "Action Name", "Sticker", "Collection Iframe Link", 
                        "Collection Iframe Title", "Collection Iframe Subtitle"])

        for collection in queryset:
            for item in collection.case_items.all():
                writer.writerow([
                    collection.collection_name, item.tab_name, 
                    item.embed_link, item.transform_iq, item.action_name,
                    item.sticker, collection.iframe_link, 
                    collection.iframe_title, collection.iframe_subtitle
                ])

        return response

    export_to_csv.short_description = "Export selected collections to CSV"

    # -------------------------------------------------------------------
    # IMPORT CSV
    # -------------------------------------------------------------------
    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and "upload_csv" in request.FILES:
            try:
                file = request.FILES["upload_csv"]
                decoded = file.read().decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(decoded))

                rows = []
                errors_list = []
                for i, row in enumerate(reader, start=1):
                    clean = normalize_row_collections(row)
                    error_list = validate_row(clean, i)
                    if error_list:
                        errors_list.append(error_list)
                        continue
                    rows.append(clean)

                rows, errors = validate_business_rules(rows)
                if errors:
                    errors_list.extend(errors)

                with transaction.atomic():
                    collections_map, created_collections = upsert_collections(rows)
                    created_cases, updated_cases = upsert_cases(rows, collections_map)

                self.message_user(
                    request,
                    f"✔ Imported — {created_collections} collections, "
                    f"{created_cases} new cases, {updated_cases} updated.",
                    level=messages.SUCCESS
                )

                if errors_list:
                    err_str = ("| \n").join(errors_list)
                    self.message_user(  
                        request,
                        f"Errors: {err_str}",
                        level=messages.SUCCESS
                    )

            except CSVValidationError as e:
                self.message_user(
                    request,
                    f"CSV Validation Error:\n{str(e)}",
                    level=messages.ERROR
                )

            except Exception as e:
                self.message_user(
                    request,
                    f"Unexpected Error: {str(e)}",
                    level=messages.ERROR
                )

            return redirect(request.get_full_path())

        return super().changelist_view(request, extra_context)

@admin.register(ConceptSession)
class ConceptSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "case_mapping", "status", "started_at", "ended_at")
    list_filter = ("status", "case_mapping__collection")
    search_fields = ("user__name", "case_mapping__tab_name", "case_mapping__collection__collection_name")
    ordering = ("-started_at",)
    list_per_page = 10