
from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
import logging

from commons.utils import generic_completion
from commons.viewset import ApiViewSet
from jobaid.models import JobAid, JobAidSession


from .serializers import JobAidSerializer, JobAidSessionSerializer
from users.models import User  # Adjust if your user model import is different

logger = logging.getLogger(__name__)

class JobAidViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin):
    """
    ViewSet for JobAid related APIs
    """
    queryset = JobAid.objects.all()
    serializer_class = JobAidSerializer
    @action(methods=['GET'], detail=False, url_path='get-job-aid')
    def get_job_aid(self, request):
        """
        Returns job aid details with questions
        """
        try:
            jobaid_id = request.query_params.get('jobaid_id')
            if not jobaid_id:
                return Response({'error': 'JobAid ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            serializer = JobAidSerializer(jobaid)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in get_job_aid: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['POST'], detail=False, url_path='validate-job-aid')
    def validate_job_aid(self, request):
        """
        POST /api/v1/job-aid/validate-job-aid/
        body: { "qna": {...}, "jobaid": 123 }
        Runs validation prompt and returns true/false
        """
        try:
            qna = request.data.get('qna')
            jobaid_id = request.data.get('jobaid')

            if not qna or not jobaid_id:
                return Response({'error': 'qna and jobaid are required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)

            prompt = "QNA : " + str(qna) + "\n\n" + jobaid.validation_prompt
            # Run your LLM or validation logic here
            validation_result = generic_completion(prompt)

            response_data = {
            "status": "hard_block",  # "acceptable" | "soft_suggestion" | "hard_block"
            "message": "",
            "suggestions": []
        }
            return Response({'is_valid': validation_result}, status=status.HTTP_200_OK) 
        except Exception as e: 
            logger.exception(f'Error in validate_job_aid: {e}') 
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        #     if "NOT ACCEPTABLE" in validation_result:
        #         response_data["status"] = "hard_block"
        #         response_data["message"] = validation_result
        #     elif "ACCEPTABLE" in validation_result and "ENHANCEMENT" in validation_result:
        #         response_data["status"] = "soft_suggestion"
        #         response_data["message"] = "Answer is acceptable but can be improved."
        #         response_data["suggestions"] = validation_result.split("ENHANCEMENT SUGGESTIONS:")[-1].strip().split("\n")
        #     else:
        #         response_data["status"] = "acceptable"
        #         response_data["message"] = "Answer accepted."

        #     return Response(response_data, status=status.HTTP_200_OK)

        # except Exception as e:
        #     logger.exception(f'Error in validate_job_aid: {e}')
        #     return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['POST'], detail=False, url_path='generate-report')
    def generate_report(self, request):
        """
        POST /api/v1/job-aid/generate-report/
        body: { "qna": {...}, "useremail": "abc@xyz.com", "jobaid": 123 }
        Runs report generation prompt, saves session & returns report URL
        """
        try:
            qna = request.data.get('qna')
            user_email = request.data.get('useremail')
            jobaid_id = request.data.get('jobaid')

            if not qna or not user_email or not jobaid_id:
                return Response({'error': 'qna, useremail, and jobaid are required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)

            prompt = "QNA : " + str(qna) + "\n\n" + jobaid.validation_prompt
            # Run your LLM or report generation logic here
            generated_report_data = generic_completion(prompt)

            # Save session
            session = JobAidSession.objects.create(
                job_aid=jobaid,
                email=user_email,
                qna=qna,
                full_name="",  # If available
                status="completed",
                generated_report_data=generated_report_data,
                report_url=f"{settings.FRONTEND_BASE_URL}/jobAidReport?sessionid={jobaid.uid}"
            )

            return Response({
                'session_id': session.id,
                'report_url': session.report_url
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in generate_report: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- Utility functions ---


    def run_report_generation_prompt(self, prompt, qna):
        """
        Placeholder: Add your LLM integration here for report generation
        Return generated report data
        """
        return {
            "summary": "Generated report summary here",
            "details": qna
        }
    @action(methods=['GET'], detail=False, url_path='get-session-report')
    def get_session_report(self, request):
        """
        Get session details along with job aid (by session_id)
        """
        try:
            session_id = request.query_params.get('session_id')
            if not session_id:
                return Response({'error': 'Session ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch session
            session = get_object_or_404(JobAidSession, uid=session_id)

            # Assuming Session model has ForeignKey to JobAid
            jobaid = session.job_aid  

            # Serialize both
            session_data = JobAidSessionSerializer(session).data
            jobaid_data = JobAidSerializer(jobaid).data if jobaid else None

            return Response({
                'session': session_data,
                'jobaid': jobaid_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error in get_session_report: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)