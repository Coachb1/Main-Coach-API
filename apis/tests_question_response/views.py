from rest_framework import mixins, status
from rest_framework.response import Response

from apis.tests_question_response.serializers import TestQuestionResponseSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from tests.helpers import create_test_question_answer
from tests.models import TestQuestionResponse


class TestQuestionResponseViewSet(ApiViewSet,
                                  mixins.ListModelMixin,
                                  mixins.RetrieveModelMixin,
                                  mixins.UpdateModelMixin):
    queryset = TestQuestionResponse.objects.filter(deleted=0)
    serializer_class = TestQuestionResponseSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

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
        )

        return Response(data=TestQuestionResponseSerializer(instance=test_question_answer).data,
                        status=status.HTTP_201_CREATED)
