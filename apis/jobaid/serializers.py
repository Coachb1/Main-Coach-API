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
            "is_validation",
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


    def to_representation(self, instance):
        data = super().to_representation(instance)
        jobaid = instance.job_aid
        ordered_questions = jobaid.questions.all().order_by('id')

        qna = instance.qna or {}
        ordered_qna = []
        for q in ordered_questions:
            if isinstance(qna, dict):
                # If stored as a dict
                answer = qna.get(str(q.id)) or qna.get(q.question)
            elif isinstance(qna, list):
                # If stored as list of {question, answer}
                found = next((item for item in qna if item.get("question") == q.question), None)
                answer = found.get("answer") if found else None
            else:
                answer = None
            ordered_qna.append({
                "question_id": q.id,
                "question": q.question,
                "answer": answer
            })
            qna.pop(str(q.question), None)  # Remove processed question from qna dict

        for q in qna:
            ordered_qna.append({
                "question_id": None,
                "question": q,
                "answer": qna.get(q) if isinstance(qna, dict) else None
            })
        
        data["ordered_qna"] = ordered_qna
        return data