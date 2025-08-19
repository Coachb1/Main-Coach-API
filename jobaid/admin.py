from django.contrib import admin

from jobaid.models import JobAid, JobAidQuestion, JobAidSession

# Register your models here.

class JobAidQuestionInline(admin.TabularInline):
    model = JobAidQuestion
    extra = 1
    fields = ("question", "question_type", "description", "dropdowns", "section")
    show_change_link = True


@admin.register(JobAid)
class JobAidAdmin(admin.ModelAdmin):
    list_display = ("title", "description", "validation_prompt_short", "report_generation_prompt_short", "report_header", "report_footer")
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
    list_display = ("job_aid", "question", "question_type", "description", "dropdowns", "section")
    list_filter = ("question_type", "job_aid")
    search_fields = ("question", "description", "dropdowns")


@admin.register(JobAidSession)
class JobAidSessionAdmin(admin.ModelAdmin):
    list_display = ("job_aid", "email", "full_name", "status", "created_at", "report_url")
    list_filter = ("status", "job_aid", "created_at")
    search_fields = ("email", "full_name")
    readonly_fields = ("created_at", "generated_report_data")
