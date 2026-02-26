from rest_framework import serializers

from jobaid.models import JobAid, JobAidQuestion, JobAidSession
from users.models import ClientUserInfo


class JobAidQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobAidQuestion
        fields = ["id", 'uid',"question", "question_type", "description", "dropdowns", "section", "is_multi_select", "allow_custom_text"]


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

        session_qna = instance.qna.copy() if isinstance(instance.qna, dict) else {}

        # ---------- BUCKETS ----------
        normal_qna = []
        innovation_score_qna = []
        editable_qna = []
        resource_qna = []

        # ---------- CLIENT ----------
        # client = None
        # if instance.client_id:
        #     client = ClientUserInfo.objects.filter(
        #         deleted=False,
        #         uid=instance.client_id
        #     ).first()

        # client_resources = list(
        #     client.resources
        #         .filter(is_active=True)
        #         .order_by("order")
        #         .values("name", "url")
        # ) if client else []

        session_resources =  list(
            instance.resources
                .filter(is_active=True)
                .order_by("order")
                .values("label", "url")
        )
       

        # ---------- JOB QUESTIONS ----------
        for q in jobaid.questions.all().order_by("id"):

            answer = session_qna.pop(str(q.id), None)
            if answer is None:
                answer = session_qna.pop(q.question, None)

            question_data = {
                "question": q.question,
                "answer": answer,
                "question_type": q.question_type,
            }

            # bucket routing
            if q.question == "Innovation Score":
                innovation_score_qna.append(question_data)

            elif q.question_type == "editable":   # editable
                editable_qna.append(question_data)

            else:
                normal_qna.append(question_data)

        # ---------- LEFTOVER SESSION QNA ----------
        for q_text, ans_text in session_qna.items():
            que_data = {
                "question": q_text,
                "answer": ans_text,
                "question_type": "other",
            }
            if q_text == "Innovation Score":
                innovation_score_qna.append(que_data)
            else:
                normal_qna.append(que_data)

        # ---------- RESOURCES ----------
        for resource in session_resources:
            resource_qna.append({
                "question": resource["label"],
                "answer": resource["url"],
                "question_type": "resource",
            })

        # ---------- FINAL ORDER ----------
        ordered_qna = [
            *normal_qna,
            *innovation_score_qna,
            *resource_qna,
            *editable_qna,
        ]

        # ✅ assign ids safely (no mutation)
        ordered_qna = [
            {
                **item,
                "question_id": index,
            }
            for index, item in enumerate(ordered_qna, start=1)
        ]

        data["ordered_qna"] = ordered_qna
        return data
