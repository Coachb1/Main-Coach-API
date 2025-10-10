from django.db import models

from commons.db.model import MyModel
from jobaid.helpers import get_prompt

# Create your models here.

class JobAid(MyModel):
    JOB_TYPE_CHOICES = [
        ('job_aid', 'Job Aid'),
        ('form', 'Form'),
    ]
    title = models.CharField(max_length=255, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    report_header = models.TextField(verbose_name="Report Header")
    report_footer = models.TextField(verbose_name="Report Footer")
    validation_prompt = models.TextField(verbose_name="Validation Prompt", null=True, blank=True, default=get_prompt("validation"))
    report_generation_prompt = models.TextField(verbose_name="Report Generation Prompt", null=True, blank=True, default=get_prompt("report_generation"))
    job_aid_type = models.CharField(max_length=50, verbose_name="Job Aid Type", blank=True, null=True, default='job_aid', choices=JOB_TYPE_CHOICES)
    is_validation = models.BooleanField(default=True, verbose_name="Is Validation")
    is_report = models.BooleanField(default=True, verbose_name="Is Report")
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
    ]
    job_aid = models.ForeignKey(JobAid, on_delete=models.CASCADE, related_name='questions', verbose_name="Job Aid")
    question = models.CharField(max_length=255, verbose_name="Question")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default='text', verbose_name="Question Type")
    section = models.CharField(max_length=255, blank=True, null=True, verbose_name="Section")
    description = models.TextField(blank=True, null=True)
    dropdowns = models.TextField(blank=True, null=True, help_text="Comma-separated values (only if type is dropdown)")
    validation_prompt = models.TextField(verbose_name="Validation Prompt", default=get_prompt("validation"))
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
    report_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qna = models.JSONField(blank=True, null=True, help_text="Q&A data for the session")
    like_count = models.IntegerField(default=0)
    liked_by = models.TextField(blank=True, null=True, help_text="Comma-separated list of user emails who liked the session")

    class Meta:
        verbose_name = "Job Aid Session"
        verbose_name_plural = "Job Aid Sessions"
    
    def __str__(self):
        return f"{self.job_aid.title} - {self.email} ({self.status})"

