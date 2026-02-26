from django.db import models

from commons.db.model import MyModel
from jobaid.helpers import get_prompt

# Create your models here.

class JobAid(MyModel):
    JOB_TYPE_CHOICES = [
        ('job_aid', 'Job Aid'),
        ('form', 'Form'),
        ('prompt_generator', 'Prompt Generator'),
    ]
    title = models.CharField(max_length=255, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    report_header = models.TextField(verbose_name="Report Header", null=True, blank=True, default=None)
    report_footer = models.TextField(verbose_name="Report Footer", null=True, blank=True, default=None)
    validation_prompt = models.TextField(verbose_name="Validation Prompt", null=True, blank=True, default=get_prompt("validation"), help_text='Deprecated')
    report_generation_prompt = models.TextField(verbose_name="Report Generation Prompt", null=True, blank=True, default=get_prompt("report_generation"))
    prompt_generation_prompt = models.TextField(verbose_name="Prompt Generation", null=True, blank=True, default=get_prompt("prompt_generation"))
    job_aid_type = models.CharField(max_length=50, verbose_name="Job Aid Type", blank=True, null=True, default='job_aid', choices=JOB_TYPE_CHOICES)
    is_validation = models.BooleanField(default=True, verbose_name="Is Validation")
    is_report = models.BooleanField(default=True, verbose_name="Is Report")
    is_prompt_generation = models.BooleanField(default=True, verbose_name="Is Prompt Generation")
    evaluation_prompt = models.TextField(verbose_name="Evaluation Prompt", null=True, blank=True, default=get_prompt("evaluation_prompt"))
    evaluate_jobaid = models.BooleanField(default=False, verbose_name="Evaluation Jobaid")
    def save(self, *args, **kwargs):
        # Apply logic BEFORE saving
        if self.job_aid_type == "form":
            self.is_validation = False
        super().save(*args, **kwargs)


    class Meta:
        verbose_name = "Job Aid"
        verbose_name_plural = "Job Aids"

    def __str__(self):
        return self.title
    
class JobAidQuestion(MyModel):
    QUESTION_TYPE_CHOICES = [
        ('text', 'Text'),
        ('dropdown', 'Dropdown'),
        ('boolean', 'Boolean'),
        ('editable', 'Editable')
    ]
    job_aid = models.ForeignKey(JobAid, on_delete=models.CASCADE, related_name='questions', verbose_name="Job Aid")
    question = models.CharField(max_length=255, verbose_name="Question")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='text', verbose_name="Question Type")
    section = models.CharField(max_length=255, blank=True, null=True, verbose_name="Section")
    description = models.TextField(blank=True, null=True)
    dropdowns = models.TextField(blank=True, null=True, help_text="Comma-separated values (only if type is dropdown)")
    validation_prompt = models.TextField(verbose_name="Validation Prompt", default=get_prompt("validation"))
    is_multi_select = models.BooleanField(
        default=False,
        verbose_name="Multi-select",
        help_text="Enable only for dropdown fields"
    )

    allow_custom_text = models.BooleanField(
        default=False,
        verbose_name="Allow custom input",
        help_text="Users can enter values not in predefined options"
    )

    class Meta:
        verbose_name = "Job Aid Question"
        verbose_name_plural = "Job Aid Questions"
    
    def __str__(self):
        return f"{self.job_aid.title} - {self.question}"
    
class JobAidSession(MyModel):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    job_aid = models.ForeignKey(JobAid, on_delete=models.CASCADE, related_name='sessions', verbose_name="Job Aid")
    email = models.EmailField(verbose_name="Email")
    full_name = models.CharField(max_length=255, verbose_name="Full Name", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress", verbose_name="Status")
    generated_report_data = models.JSONField(blank=True, null=True)
    generated_prompt = models.TextField(blank=True, null=True, default=None)
    report_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qna = models.JSONField(blank=True, null=True, help_text="Q&A data for the session")
    like_count = models.IntegerField(default=0)
    liked_by = models.TextField(blank=True, null=True, help_text="Comma-separated list of user emails who liked the session")
    client_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Client ID", help_text="Identifier for the client associated with this session")
    resources = models.ManyToManyField(
            'users.ClientResource',
            blank=True,
            related_name="jobaid_sessions"
        )
    
    class Meta:
        verbose_name = "Job Aid Session"
        verbose_name_plural = "Job Aid Sessions"
    
    def __str__(self):
        return f"{self.job_aid.title} - {self.email} ({self.status})"

