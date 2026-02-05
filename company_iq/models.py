from django.db import models
from django.core.exceptions import ValidationError
from commons.db.model import MyModel


class CompanyIQ(MyModel):
    SOURCE_CHOICES = [
        ("LLM", "LLM"),
        ("CSV", "CSV"),
        ("Manual", "Manual"),
    ]

    # Core identity
    company = models.CharField(max_length=255)
    company_normalized = models.CharField(
        max_length=255,
        editable=False,
        db_index=True
    )
    industry = models.CharField(max_length=50)
    hq = models.CharField(max_length=255)

    # Scale
    revenue_us_millions = models.IntegerField()
    employees_full_time = models.IntegerField()

    # Intelligence blocks
    ai_cloud_leadership_roles = models.JSONField(default=list)
    ai_digital_initiatives = models.JSONField(default=list)
    cloud_tech_stack_signals = models.JSONField(default=list)
    ai_use_cases = models.JSONField(default=list)
    transformation_iq_outlook = models.TextField(
        null=True,
        blank=True,
        help_text="12-18 month AI / digital transformation outlook"
    )


    # Governance
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="Manual")
    approved = models.BooleanField(default=False)

    score = models.JSONField(
        default=dict,
        help_text="AI maturity scores and insights"
    )
    sticker = models.CharField(max_length=55, null=True, blank=True)


    class Meta:
        verbose_name = "CompanyIQ"
        verbose_name_plural = "CompanyIQ"
        ordering = ["-created"]


    def save(self, *args, **kwargs):
        # Normalize company name first
        normalized = self.company.strip().lower()
        self.company_normalized = normalized

        # Duplicate check ONLY on create
        if self.pk is None:
            exists = CompanyIQ.objects.filter(
                company_normalized=normalized,
                deleted=False,
            ).exists()

            if exists:
                raise ValidationError(
                    "A CompanyIQ record with this company name already exists."
                )

        super().save(*args, **kwargs)


    def __str__(self):
        return self.company
