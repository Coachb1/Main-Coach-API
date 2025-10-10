from rest_framework import serializers

from jobaid.models import JobAid, JobAidQuestion, JobAidSession


class JobAidQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAidQuestion
        fields = ["id", 'uid',"question", "question_type", "description", "dropdowns", "section"]


class JobAidSerializer(serializers.ModelSerializer):
    questions = JobAidQuestionSerializer(many=True, read_only=True)  # from related_name="questions"

    class Meta:
        model = JobAid
        fields = [
            "id",
            "uid",
            "title",
            "description",
            "validation_prompt",
            "report_generation_prompt",
            "questions",
            "report_header",
            "report_footer",
            "job_aid_type",
            "is_validation"
            "is_report",
        ]


class JobAidSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAidSession
        fields = [
            "id",
            "uid",
            "job_aid",
            "email",
            "full_name",
            "status",
            "created_at",
            "report_url",
            "generated_report_data",
            "qna",
            "like_count",
            "liked_by"
        ]
        read_only_fields = ["status", "created_at", "report_url", "generated_report_data"]
