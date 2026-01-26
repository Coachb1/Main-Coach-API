import csv
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import path
from company_iq.services.csv_upload import import_companyiq_csv
from django.shortcuts import render, redirect
from .models import CompanyIQ
from django.utils.html import format_html


@admin.register(CompanyIQ)
class CompanyIQAdmin(admin.ModelAdmin):

    # ==========================
    # LIST VIEW (REVIEW-FIRST)
    # ==========================
    list_display = (
        "id",
        "created",
        "updated",
        "deleted",
        "company",
        "industry",
        "source",
        "approved_badge",
        "revenue_us_millions",
        "employees_full_time",
        "get_score",
        "why_score",
        "sticker"
    )

    list_filter = (
        "approved",
        "source",
        "industry",
    )

    search_fields = (
        "company",
        "hq",
    )

    list_editable = ("deleted",)

    ordering = ("-updated",)

    actions = ["approve_selected", "export_as_csv"]

    # ==========================
    # DETAIL VIEW (HUMAN READABLE)
    # ==========================
    fieldsets = (
        ("Company Basics", {
            "fields": (
                "company",
                "industry",
                "hq",
                "sticker"
            )
        }),
        ("Business Scale", {
            "fields": (
                "revenue_us_millions",
                "employees_full_time",
            )
        }),
        ("AI & Cloud Intelligence", {
            "fields": (
                "ai_cloud_leadership_roles",
                "ai_digital_initiatives",
                "cloud_tech_stack_signals",
                "ai_use_cases",
                "transformation_iq_outlook"
            )
        }),
        ("Governance", {
            "fields": (
                "source",
                "approved",
                "score"
            )
        }),
        ("Audit", {
            "fields": (
                "created",
                "updated",
                "deleted"
            )
        }),
    )

    # ==========================
    # READ-ONLY SAFETY
    # ==========================
    readonly_fields = (
        "source",
        "created",
        "updated",
        "score"
    )

    def get_score(self, obj):
        """
        Display the AI maturity score as a percentage.
        """
        if obj.score and "score" in obj.score:
            return f"{obj.score['score']}%"
        return "N/A"
    def why_score(self, obj):
        if obj.score and "justification" in obj.score:
            return format_html(
                '<div style="max-height:120px; max-width:500px; '
                'overflow:auto; white-space:pre-wrap;">{}</div>',
                obj.score["justification"]
            )
        return "N/A"

    why_score.short_description = "Why Score"
    change_list_template = "admin/companyiq/companyiq_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-csv/", self.upload_csv),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES.get("csv_file")
            generate_score = request.POST.get("generate_score", "false").lower() == "true"

            if not csv_file:
                messages.error(request, "No CSV file selected.")
                return redirect(request.get_full_path())

            created, errors = import_companyiq_csv(csv_file,generate_score)

            messages.success(
                request,
                f"{created} CompanyIQ records created/updated."
            )

            if errors:
                messages.warning(
                    request,
                    f"{len(errors)} rows failed. Check logs."
                )
                all_errors = "\n".join(errors[:5])
                messages.error(request, all_errors)
                return redirect(request.get_full_path())
                

            return redirect("..")

        return render(request, "admin/companyiq/companyiq_upload_csv.html")



    def get_readonly_fields(self, request, obj=None):
        """
        Lock all intelligence fields once approved.
        Approved data = frozen truth.
        """
        if obj and obj.approved:
            return self.readonly_fields + (
                "company",
                "industry",
                "hq",
                "revenue_us_millions",
                "employees_full_time",
                "ai_cloud_leadership_roles",
                "ai_digital_initiatives",
                "cloud_tech_stack_signals",
                "ai_use_cases",
                "transformation_iq_outlook",
            )
        return self.readonly_fields

    # ==========================
    # VISUAL TRUST SIGNAL
    # ==========================
    def approved_badge(self, obj):
        return "✅ Approved" if obj.approved else "❌ Pending"

    approved_badge.short_description = "Approval Status"

    # ==========================
    # BULK APPROVAL ACTION
    # ==========================
    @admin.action(description="Approve selected CompanyIQ records")
    def approve_selected(self, request, queryset):
        updated = queryset.filter(approved=False).update(approved=True)
        self.message_user(
            request,
            f"{updated} CompanyIQ records approved successfully."
        )
    @admin.action(description="Export selected CompanyIQ records to CSV")
    def export_as_csv(self, request, queryset):
        """
        Export selected CompanyIQ records as CSV.
        Respects filters + selection.
        """

        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = 'attachment; filename="companyiq_export.csv"'

        writer = csv.writer(response)

        # CSV headers (human-readable, stable contract)
        writer.writerow([
            "Score",
            "Score Justification",
            "Sticker",
            "Company",
            "Industry",
            "HQ",
            "Revenue (US Millions)",
            "Employees (Full-Time)",
            "AI/Cloud Leadership Roles",
            "AI / Digital Initiatives",
            "Cloud / Tech Stack Signals",
            "AI Use Cases",
            "Transformation IQ Outlook",
            "Use LLM",
            "Approved",
            "Created",
            "Updated",
        ])

        for obj in queryset.iterator():
            writer.writerow([
                obj.score.get("score", ""),
                obj.score.get("justification", ""),
                obj.sticker or "",
                obj.company,
                obj.industry,
                obj.hq,
                obj.revenue_us_millions,
                obj.employees_full_time,
                "\n".join(obj.ai_cloud_leadership_roles or []),
                "\n".join(obj.ai_digital_initiatives or []),
                "\n".join(obj.cloud_tech_stack_signals or []),
                "\n".join(obj.ai_use_cases or []),
                obj.transformation_iq_outlook or "",
                obj.source == "LLM",
                "TRUE" if obj.approved else "FALSE",
                obj.created.isoformat() if obj.created else "",
                obj.updated.isoformat() if obj.updated else "",
            ])

        return response
