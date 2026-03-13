from django.contrib import admin, messages
from django.utils.html import format_html

from django.shortcuts import redirect
from jobaid.form import BulkResourceActionForm, JobAidForm
from jobaid.models import JobAid, JobAidQuestion, JobAidSession

# Register your models here.

class JobAidQuestionInline(admin.TabularInline):
    model = JobAidQuestion
    extra = 0
    fields = ("question","validation_prompt", "question_type", "description", "dropdowns", "section",  "is_multi_select", "allow_custom_text", "attachment_allowed")
    show_change_link = True


@admin.register(JobAid)
class JobAidAdmin(admin.ModelAdmin):
    form = JobAidForm
    list_display = ("title", "description", "validation_prompt_short", "report_generation_prompt_short", 'evaluation_prompt', "report_header", "report_footer")
    search_fields = ("title", "description")
    inlines = [JobAidQuestionInline]

    def validation_prompt_short(self, obj):
        return obj.validation_prompt[:50] + ("..." if len(obj.validation_prompt) > 50 else "")
    validation_prompt_short.short_description = "Validation Prompt"

    def report_generation_prompt_short(self, obj):
        return obj.report_generation_prompt[:50] + ("..." if len(obj.report_generation_prompt) > 50 else "")
    report_generation_prompt_short.short_description = "Report Generation Prompt"


@admin.register(JobAidQuestion)
class JobAidQuestionAdmin(admin.ModelAdmin):
    list_display = ("job_aid", "question", "question_type", "description", "dropdowns", "section",  "is_multi_select", "allow_custom_text")
    list_filter = ("question_type", "job_aid")
    search_fields = ("question", "description", "dropdowns")


@admin.register(JobAidSession)
class JobAidSessionAdmin(admin.ModelAdmin):
    list_display = (
        "job_aid",
        "email",
        "full_name",
        "status",
        "created_at",
        "report_url",
        "resource_count",       # new: shows how many resources are assigned
    )
    list_filter = (
        "status",
        "job_aid",
        "created_at",
    )
    # Extended search: also searches job_aid name and resource titles
    search_fields = (
        "email",
        "full_name",
        "job_aid__name",        # adjust to actual field name on JobAid
        "resources__title",     # adjust to actual field name on Resource
        "client_id"
    )
    readonly_fields = ("created_at", "generated_report_data")
    filter_horizontal = ("resources",)
    actions = ["bulk_assign_resources_action", "bulk_deassign_resources_action"]

    # ------------------------------------------------------------------ #
    #  Extra list_display column                                           #
    # ------------------------------------------------------------------ #

    @admin.display(description="# Resources")
    def resource_count(self, obj):
        count = obj.resources.count()
        return format_html(
            '<span style="font-weight:bold;color:{}">{}</span>',
            "#28a745" if count else "#dc3545",
            count,
        )

    # ------------------------------------------------------------------ #
    #  Bulk actions — redirect to an intermediate confirmation page        #
    # ------------------------------------------------------------------ #

    def _bulk_resource_page(self, request, queryset, action_type):
        """
        Shared logic for both bulk-assign and bulk-deassign actions.
        On GET (first click): renders a form to pick resources.
        On POST (form submit): applies the changes.
        """
        from django.shortcuts import render
        from django.urls import reverse

        session_ids = list(queryset.values_list("id", flat=True))

        if "apply" in request.POST:
            form = BulkResourceActionForm(request.POST)
            if form.is_valid():
                resources = form.cleaned_data["resources"]
                sessions = JobAidSession.objects.filter(id__in=session_ids)
                count = sessions.count()
                for session in sessions:
                    if action_type == "assign":
                        session.resources.add(*resources)
                    else:
                        session.resources.remove(*resources)
                verb = "assigned to" if action_type == "assign" else "removed from"
                self.message_user(
                    request,
                    f"{resources.count()} resource(s) {verb} {count} session(s).",
                    messages.SUCCESS,
                )
                # previous page
                return redirect(request.get_full_path())
                     
        else:
            form = BulkResourceActionForm(initial={"action_type": action_type})

        sessions = []
        for obj in queryset:
            sessions.append({
                'full_name': obj.full_name,
                'email': obj.email,
                'status': obj.status,
                'resources': list(obj.resources.all()),  # ← evaluate queryset here
            })
        return render(
            request,
            "admin/jobaid/bulk_resource_action.html",  # template below
            {
                "title": f"Bulk {'Assign' if action_type == 'assign' else 'Deassign'} Resources",
                "form": form,
                "sessions": sessions,
                "session_ids": session_ids,
                "action_type": action_type,
                "opts": self.model._meta,
            },
        )

    @admin.action(description="📎 Bulk assign/deassign resources to selected sessions")
    def bulk_assign_resources_action(self, request, queryset):
        return self._bulk_resource_page(request, queryset, "assign")

    @admin.action(description="❌ Bulk deassign resources from selected sessions")
    def bulk_deassign_resources_action(self, request, queryset):
        return self._bulk_resource_page(request, queryset, "deassign")