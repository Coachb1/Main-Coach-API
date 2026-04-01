
import json
from string import Template
from rest_framework import status, mixins
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
import logging

from commons.cloudinary import upload_image
from commons.gcp_upload import gcp_upload
from commons.utils import generic_completion
from commons.viewset import ApiViewSet
from documents.helpers import get_url
from email_sender.helpers import send_email_from_emailit, send_emailv2
from jobaid.helpers import extract_feedback_block, format_qna_body
from jobaid.models import JobAid, JobAidQuestion, JobAidSession


from .serializers import JobAidSerializer, JobAidSessionSerializer
from users.models import ClientUserInfo, User  # Adjust if your user model import is different

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

    @action(
        methods=['POST'],
        detail=False,
        url_path='generate-report',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def generate_report(self, request):
        """
        POST /api/v1/job-aid/generate-report/
        body: { "qna": {...}, "useremail": "abc@xyz.com", "jobaid": 123 }
        Runs report generation prompt, saves session & returns report URL
        """
        try:
            qna = request.data.get('qna')
            user_email = request.data.get('useremail')
            client_id = request.data.get('client_id')  # Optional
            user_name = request.data.get('name')  # Optional
            jobaid_id = request.data.get('jobaid')

            # multipart/form-data sends JSON as string → convert
            if isinstance(qna, str):
                try:
                    qna = json.loads(qna)
                except json.JSONDecodeError:
                    return Response(
                        {"error": "Invalid qna JSON format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if not qna or not user_email or not jobaid_id:
                return Response(
                    {'error': 'qna, useremail, and jobaid are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            client = None
            if client_id:
                client = ClientUserInfo.objects.filter(uid=client_id, deleted=False).first()
                
            # ── Handle file-upload questions ─────────────────────────────────
            # Frontend sends files as:  file_upload[<question_key>] = <File>
            # We upload each to Cloudinary and replace the qna value with the URL.
            file_upload_errors = {}

            file_qna = {}

            for question_key, file_obj in request.FILES.items():
                if question_key.startswith("file_upload[") and question_key.endswith("]"):
                    clean_key = question_key[len("file_upload["):-1]
                else:
                    clean_key = question_key

                try:
                    # content_type = file_obj.content_type or ""
                    # resource_type = "image" if content_type.startswith("image/") else "auto"

                    # upload_result = upload_image(file_obj, resource_type=resource_type)  # pass resource_type
                    # file_url = upload_result.get("secure_url")

                    # using gcp upload instead of cloudinary
                    bucket_name = "publicvid"
                    destination_blob_name = f"Jobaid-doc-upload/{jobaid_id}/{file_obj.name}"
                    file_url = gcp_upload(bucket_name, file_obj, destination_blob_name)
                    file_url = get_url(region_name="", bucket=bucket_name, key=destination_blob_name, public_url=True)
                    file_url = file_url.replace("https://storage.googleapis.com/publicvid/", "https://cdn.coachbots.com/")  # Replace with your CDN URL
                    # If the key already has a URL (multiple files for same question),
                    # convert to a list so all URLs are preserved
                    if clean_key in file_qna and file_qna[clean_key]:
                        existing = file_qna[clean_key]
                        if isinstance(existing, list):
                            existing.append(file_url)
                        else:
                            file_qna[clean_key] = [existing, file_url]
                    else:
                        file_qna[clean_key] = file_url

                except Exception as upload_err:
                    logger.exception(f"Cloudinary upload failed for '{clean_key}': {upload_err}")
                    file_upload_errors[clean_key] = str(upload_err)

            if file_upload_errors:
                return Response(
                    {'error': 'File upload failed', 'details': file_upload_errors},
                    status=status.HTTP_400_BAD_REQUEST
                )


            # Initialize empty report data
            generated_report_data = {}
            generated_prompt_output = None
            output = None

            if jobaid.job_aid_type == "transformation_program":
                input_data = "\n".join([f"{q}: {ans}" for q, ans in qna.items()])
                company_name = client.company_information.get("company_name") if client and client.company_information else "Unknown Company"
                company_url = client.company_information.get("company_url") if client and client.company_information else "https://www.coachbots.com"
                input_data = f"Company Name: {company_name}\nCompany URL: {company_url}\n\n" + input_data
                prompt = f"User Input: {input_data}\n" + jobaid.custom_prompt
                output = generic_completion(prompt)
                


            # ✅ Only generate report if jobaid.is_report == True
            if jobaid.is_report and jobaid.report_generation_prompt:
                prompt = "QNA : " + str(qna) + "\n\n" + jobaid.report_generation_prompt
                generated_report_data = generic_completion(prompt)
        

            # ✅ Only generate prompt if jobaid.is_prompt_generation == True
            if jobaid.is_prompt_generation and jobaid.prompt_generation_prompt:
                prompt = "Here are the user inputs : " + str(qna) + "\n\n" + jobaid.prompt_generation_prompt
                generated_prompt_output = generic_completion(prompt)

            # ✅ If jobaid has evaluation enabled
            if jobaid.evaluate_jobaid and jobaid.evaluation_prompt:
                eva_prompt = jobaid.evaluation_prompt
                questions = [q for q, ans in qna.items()]
                jobaid_questions = jobaid.questions.filter(deleted=False, question__in=questions)

                queAns = ""
                for question in jobaid_questions:
                    queAns +=f"""
                        Q: {question.question}\n Ans: {qna.get(question.question)}\n\n
                        """
                if eva_prompt:
                    eva_prompt = queAns + eva_prompt
                    print('prompt', eva_prompt)
                    innovation_rating = generic_completion(eva_prompt)
                    if isinstance(innovation_rating, str):
                        innovation_rating = json.loads(
                            innovation_rating.replace('```', "").replace('json', "")
                        )
                    qna['Innovation Score'] = innovation_rating.get('rating')

            # ✅ Save session
            session = JobAidSession.objects.create(
                job_aid=jobaid,
                email=user_email,
                client_id=client_id,
                qna=qna,
                full_name=user_name,
                status="completed",
                generated_report_data=generated_report_data,
                generated_prompt=generated_prompt_output,
                file_qna=file_qna if file_qna else None,
                output=output
            )

            # ✅ Only set report_url if a report was generated
            if jobaid.is_report and generated_report_data:
                session.report_url = (
                    f"{settings.FRONTEND_BASE_URL}/actionPlannerReport?"
                    f"sessionid={session.uid}&backend={settings.BACKEND}"
                )
                session.save(update_fields=['report_url'])

            # ✅ Send email to admin
            send_email_from_emailit(
                receiver_email="mail@coachbots.com",
                subject=f"Job Aid - {jobaid.title}",
                body=format_qna_body(jobaid, session),
            )

            return Response(
                {
                    'session_id': session.uid,
                    'report_url': session.report_url if jobaid.is_report else None,
                    'generated_prompt': generated_prompt_output,
                    'output': output
                },
                status=status.HTTP_200_OK
            )

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
    
    # not using
    @action(methods=['GET'], detail=False, url_path='job-aid-sessions')
    def get_job_aid_sessions(self, request):

        try:
            jobaid_id = request.query_params.get('jobaid_id')
            email = request.query_params.get('email')
            client_id = request.query_params.get('client_id')
            if not jobaid_id:
                return Response({'error': 'JobAid ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            jobaid_sessions = JobAidSession.objects.filter(deleted=False, job_aid=jobaid)
            if client_id:
                jobaid_sessions = jobaid_sessions.filter(client_id=client_id)
            if email:
                jobaid_sessions = jobaid_sessions.filter(email=email)
            session_data = JobAidSessionSerializer(jobaid_sessions, many=True)
            jobaid_data = JobAidSerializer(jobaid).data

            return Response({
                'session': session_data,
                'jobaid': jobaid_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in job-aid-sessions: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['POST', "GET"], detail=False, url_path='job-aid-leaderboard/like')
    def job_aid_leaderboard_like(self, request):
        try:
            if request.method == "POST":
                session_id = request.data.get('session_id')
                email = request.data.get('email')
                like = request.data.get('like_count')
                if not session_id and not like and not email:
                    return Response({'error': 'session_id, email and like_count are required'}, status=status.HTTP_400_BAD_REQUEST)
                session = get_object_or_404(JobAidSession, deleted=False, uid=session_id)
                if like >0:
                    session.like_count += 1
                    if session.liked_by:
                        liked_by = session.liked_by.split(',')
                        if email not in liked_by:
                            liked_by.append(email)
                            session.liked_by = ','.join(set(liked_by))
                    else:
                        session.liked_by = email

                else:
                    if session.like_count > 0:
                        session.like_count -= 1
                        if session.liked_by:
                            liked_by = session.liked_by.split(',')
                            if email in liked_by:
                                liked_by.remove(email)
                                session.liked_by = ','.join(set(liked_by))
                        else:
                            session.liked_by = ''

                session.save(update_fields=['like_count', 'liked_by'])


            serializer = JobAidSessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in job_aid_likes: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(methods=['GET'], detail=False, url_path='job-aid-leaderboard')
    def job_aid_leaderboard(self, request):
        try:
            jobaid_id = request.query_params.get('jobaid_id')
            client_id = request.query_params.get('client_id')
            if not jobaid_id:
                return Response({'error': 'JobAid ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            jobaid = get_object_or_404(JobAid, uid=jobaid_id)
            jobaid_sessions = JobAidSession.objects.filter(deleted=False, job_aid=jobaid).order_by('-like_count')
            if client_id:
                jobaid_sessions = jobaid_sessions.filter(client_id=client_id)
            serializer = JobAidSessionSerializer(jobaid_sessions, many=True)

            data = {
                "session_voting_enabled": jobaid.session_voting_enabled,
                "sessions": serializer.data
            }
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f'Error in job_aid_leaderboard: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(methods=['PATCH'], detail=True, url_path='update-session')
    def update_session(self, request, pk=None, uid=None):
        session = get_object_or_404(JobAidSession, uid=uid)
        serializer = JobAidSessionSerializer(session, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)