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

        test_question_answer = create_test_question_answer(
            tenant=request.tenant,
            test_attempt_session_id=test_attempt_session_id,
            question_id=question_id,
            response_file=response_file,
            response_text=response_text,
            is_whatsapp=is_whatsapp
        )

        return Response(data=TestQuestionResponseSerializer(instance=test_question_answer).data,
                        status=status.HTTP_201_CREATED)
    
    @action(methods=['POST'],detail=False,url_path="submit-feedback-response")
    def submit_feedback_response(self,request, *args, **kwargs):
        tenant_id = self.request.tenant.uid
        session_id = request.query_params.get('test_attempt_session_id')
        question_id = request.query_params.get('question_id')
        response_file = request.query_params.get('response_file')
        
        feedback = submit_feedback(session_id,tenant_id,question_id,response_file)

        return Response({"feedback_text": feedback}, status=status.HTTP_201_CREATED)


    @action(methods=['GET'],detail=False,url_path="get-text-to-speech")
    def get_text_to_speech(self,request, *args, **kwargs):
        
        text = request.query_params.get('text')

        response = text_to_speech_google(text)

        return Response({"data": str(response.audio_content)}, status=status.HTTP_201_CREATED)

        