from django.contrib import admin
from import_export.admin import ExportActionMixin
from tests.models import (
    Test,
    TestQuestion,
    Psychometric,
    PsychometricItem,
    TestAttemptSession,
    TestQuestionResponse,
)
from django.utils.translation import gettext_lazy as _
from tenants.admin import TenantAwareModelAdmin
from django.contrib import messages
from users.helpers import get_client_info_from_user_detail
from users.models import UserAttribute
from openpyxl import Workbook
from django.http import HttpResponse
from tests.helpers import format_game_json_to_string, process_test_pilot_user_csv
from .models import PsychometricReportSection, PsychometricReportSubsection, TestRecommendation
from django.db import models
from django.shortcuts import render, redirect
from django.urls import path
from .models import TestPilotuser, TestPilotRecords
from .forms import CSVUploadForm, PsychometricAdminForm, PsychometricReportAdminForm
from django.utils.html import format_html
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


class TestAdmin(ExportActionMixin, TenantAwareModelAdmin):
    list_per_page = 10
    list_display = (
        "uid",
        "test_code",
        "deleted",
        "title",
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
        "start_with_user",
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
        "calculate_culture",
        "page_name",
        "client_name",
        "competency_group",
        "area_domain",
        "psychometric",
        "psychometric_report_config",
        "tab_category",
    )
    list_filter = (
        "deleted",
        "test_type",
        "scenario_case",
        "calculate_culture",
        "interaction_mode",
        "page_name",
        "client_name",
        StartWithUserFilter,
        OnlyCompetencyFilter,
    )
    ordering = ("-id",)

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
    list_display = ('id', 'name', 'email', 'industry', 'department', 'restart_status', 'view_records')
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
            'fields': ('key_stakeholders', 'situation', 'restart')
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

                required_fields = ["Name", "Email", "Targeted Skills"]

                # ✅ Check if file is empty
                if not reader.fieldnames:
                    messages.error(request, "CSV file is empty! Please upload a valid file.")
                    return redirect(request.get_full_path())

                # ✅ 4. Check if the CSV contains all required fields
                if not all(field in reader.fieldnames for field in required_fields):
                    messages.error(
                        request,
                        "CSV is missing required fields: Name, Email, Targeted Skills.",
                    )
                    return redirect(request.get_full_path())
                try:
                    process_test_pilot_user_csv(csv=reader, tenant_id=tenant_id)
                except Exception as e:
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

class TestPilotRecordsAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_pilotuser_name', 'get_pilotuser_email', 'test', 'sent_email', 'test_attempted', 'active')
    search_fields = ('pilotuser__name', 'test__name', 'pilotuser__email')
    list_filter = ('sent_email', 'test_attempted', 'active')
    ordering = ('id',)

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

admin.site.register(TestPilotRecords, TestPilotRecordsAdmin)

@admin.register(TestRecommendation)
class TestRecommendationAdmin(admin.ModelAdmin):
    list_display = ("id", "recommended_test", "origin_test", "test_case", "session_id", "user_id")
    search_fields = ("recommended_test__uid", "origin_test__uid", "test_case", "session_id", "user_id")
    list_filter = ("test_case",)
    ordering = ("id",)