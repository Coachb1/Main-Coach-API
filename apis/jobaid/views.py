
import json
from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
import logging

from commons.utils import generic_completion
from commons.viewset import ApiViewSet
from email_sender.helpers import send_email_from_emailit, send_emailv2
from jobaid.helpers import extract_feedback_block, format_qna_body
from jobaid.models import JobAid, JobAidQuestion, JobAidSession


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
    queryset = JobAid.objects.filter(deleted=False)
    serializer_class = JobAidSerializer
    lookup_field = 'uid'  # Assuming you want to use 'uid' as the lookup field


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
            question_id = request.data.get('question_id') 
            if not qna or not question_id:
                return Response({'error': 'qna and question_id are required'}, status=status.HTTP_400_BAD_REQUEST)

            question = get_object_or_404(JobAidQuestion, uid=question_id)

            if not isinstance(qna, dict):
                try:
                    qna = json.loads(qna)  # Attempt to parse if it's a string
                except json.JSONDecodeError:
                    return Response({'error': 'Invalid qna format, must be a JSON object'}, status=status.HTTP_400_BAD_REQUEST)

            prompt = "\n".join([f"Q: {q}\nA: {ans}" for q, ans in qna.items()]) + "\n" + question.validation_prompt
            # Run your LLM or validation logic here
            validation_result = generic_completion(prompt)

            response_data = extract_feedback_block(validation_result)


            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in validate_job_aid: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            user_name = request.data.get('name')  # Optional, if available
            jobaid_id = request.data.get('jobaid')

            if not qna or not user_email or not jobaid_id:
                return Response({'error': 'qna, useremail, and jobaid are required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            
            if jobaid.job_aid_type =='form' or not jobaid.is_validation:
                generated_report_data = {}
            else:
                prompt = "QNA : " + str(qna) + "\n\n" + jobaid.report_generation_prompt
                # Run your LLM or report generation logic here
                generated_report_data = generic_completion(prompt)

            # Save session
            session = JobAidSession.objects.create(
                job_aid=jobaid,
                email=user_email,
                qna=qna,
                full_name=user_name,
                status="completed",
                generated_report_data=generated_report_data,
            )

            if jobaid.job_aid_type =='job_aid' or jobaid.is_validation:
                session.report_url =f"{settings.FRONTEND_BASE_URL}/actionPlannerReport?sessionid={session.uid}&backend={settings.BACKEND}"
                session.save(update_fields=['report_url'])

            # send email to admin
            send_email_from_emailit(
                receiver_email="mail@coachbots.com",
                subject=f"Job Aid - {jobaid.title}",
                body=format_qna_body(jobaid, session),
            )

            return Response({
                'session_id': session.id,
                'report_url': session.report_url
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in generate_report: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
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
    
    @action(methods=['GET'], detail=False, url_path='job-aid-sessions')
    def get_job_aid_sessions(self, request):

        try:
            jobaid_id = request.query_params.get('jobaid_id')
            if not jobaid_id:
                return Response({'error': 'JobAid ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            jobaid_sessions = JobAidSession.objects.filter(deleted=False, job_aid=jobaid)
            session_data = JobAidSessionSerializer(jobaid_sessions, many=True)
            jobaid_data = JobAidSerializer(jobaid).data

            return Response({
                'session': session_data,
                'jobaid': jobaid_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in job-aid-sessions: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['POST', "GET"], detail=False, url_path='job-aid-likes')
    def job_aid_likes(self, request):
        try:
            if request.method == 'GET':
                session_id = request.query_params.get('session_id')
                if not session_id:
                    return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)

                session = get_object_or_404(JobAidSession, deleted=False, uid=session_id)
            elif request.method == "POST":
                session_id = request.data.get('session_id')
                like = request.data.get('like_count')
                if not session_id and not like:
                    return Response({'error': 'session_id and like_count are required'}, status=status.HTTP_400_BAD_REQUEST)
                session = get_object_or_404(JobAidSession, deleted=False, uid=session_id)
                if like >0:
                    session.like_count += 1
                else:
                    if session.like_count != 0:
                        session.like_count -= 1

                session.save(update_fields=['like_count'])


            serializer = JobAidSessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in get_job_aid: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
