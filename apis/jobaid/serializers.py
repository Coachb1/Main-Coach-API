from rest_framework import serializers

from jobaid.models import JobAid, JobAidQuestion, JobAidSession


class JobAidQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAidQuestion
        fields = ["id", "question", "question_type", "description", "dropdowns", "section"]


class JobAidSerializer(serializers.ModelSerializer):
    questions = JobAidQuestionSerializer(many=True, read_only=True)  # from related_name="questions"

    class Meta:
        model = JobAid
        fields = [
            "id",
            "title",
            "description",
            "validation_prompt",
            "report_generation_prompt",
            "questions",
        ]


class JobAidSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAidSession
        fields = [
            "id",
            "job_aid",
            "email",
            "full_name",
            "status",
            "created_at",
            "report_url",
            "generated_report_data",
            "qna",
        ]
        read_only_fields = ["status", "created_at", "report_url", "generated_report_data"]
