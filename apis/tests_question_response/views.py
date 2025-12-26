from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.tests_question_response.filtersets import TestQuestionResponseFilterSet
from apis.tests_question_response.serializers import TestQuestionResponseSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from tests.helpers import create_test_question_answer, submit_feedback
from tests.models import TestQuestionResponse, TestAttemptSession, TestQuestion, Test
from rest_framework.decorators import action
from commons.google_apis import text_to_speech_google
from django.http import StreamingHttpResponse
from django.http import HttpResponse
import tempfile
import os



class TestQuestionResponseViewSet(ApiViewSet,
                                  mixins.ListModelMixin,
                                  mixins.RetrieveModelMixin,
                                  mixins.UpdateModelMixin):
    queryset = TestQuestionResponse.objects.filter(deleted=0)
    serializer_class = TestQuestionResponseSerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TestQuestionResponseFilterSet
    ordering_fields = ("id", )
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        """
        Create a new test question response.

        Args:
            request (HttpRequest): The HTTP request object containing the data for creating the test question response.

        Returns:
            Response: The serialized data of the created test question response.

        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_whatsapp = False

        # Check for "x-platform" header
        if request.headers.get("x-platform") == "whatsapp":
            is_whatsapp = True

        test_attempt_session_id = serializer.validated_data["test_attempt_session_id"]
        question_id = serializer.validated_data["question_id"]
        response_file = serializer.validated_data.get("response_file")
        response_text = serializer.validated_data.get("response_text")
        context = serializer.validated_data.get('context')

        test_question_answer = create_test_question_answer(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id,
            question_id=question_id,
            response_file=response_file,
            response_text=response_text,
            is_whatsapp=is_whatsapp,
            context=context
        )

        return Response(data=TestQuestionResponseSerializer(instance=test_question_answer).data,
                        status=status.HTTP_201_CREATED)
    
    @action(methods=['POST'],detail=False,url_path="submit-feedback-response")
    def submit_feedback_response(self,request, *args, **kwargs):
        """
        Submits feedback for a test question response.

        Params:
            test_attempt_session_id,question_id,response_file

        Returns:
            Response: The generated feedback for the test question response.

        """
        tenant_id = self.request.tenant.uid
        session_id = request.query_params.get('test_attempt_session_id')
        question_id = request.query_params.get('question_id')
        response_file = request.query_params.get('response_file')
        
        feedback = submit_feedback(session_id,tenant_id,question_id,response_file)

        return Response({"feedback_text": feedback}, status=status.HTTP_201_CREATED)


    @action(methods=['GET'], detail=False, url_path="get-text-to-speech")
    def get_text_to_speech(self,request, *args, **kwargs):
        """
        Generates a text-to-speech audio file using the Google Text-to-Speech API and returns it as a response.

        Args:
            request (HttpRequest): The HTTP request object.
            text (str): The text to be converted to speech.

        Returns:
            HttpResponse: The HTTP response containing the generated audio file.
        """
        text = request.query_params.get('text')

        response = text_to_speech_google(text)

        audio_file_content = response.audio_content
        # response = StreamingHttpResponse(audio_file_content, content_type="audio/mpeg")
        # response['Content-Disposition'] = 'attachment; filename="output.mp3"'

        # Create a temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(audio_file_content)
            temp_file_path = temp_file.name

        # Open the temporary file and create an HttpResponse
        with open(temp_file_path, 'rb') as file:
            response = HttpResponse(file.read(), content_type="audio/mpeg")
            response['Content-Disposition'] = 'attachment; filename="output.mp3"'

        # Delete the temporary file after sending the response
        os.remove(temp_file_path)


        return response
        