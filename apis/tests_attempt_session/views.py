from rest_framework import mixins, status
from rest_framework.response import Response

from apis.tests_attempt_session.serializers import TestAttemptSessionSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from tests.helpers import create_test_question_answer_session
from tests.models import TestAttemptSession


class TestAttemptSessionViewSet(ApiViewSet,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin,
                                mixins.UpdateModelMixin):
    queryset = TestAttemptSession.objects.filter(deleted=0)
    serializer_class = TestAttemptSessionSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_id = serializer.validated_data["test_id"]
        participant_id = serializer.validated_data["participant_id"]
        test_invite_id = serializer.validated_data.get("test_invite_id")

        session = create_test_question_answer_session(
            tenant=request.tenant,
            test_id=test_id,
            test_invite_id=test_invite_id,
            participant_id=participant_id
        )

        return Response(data=TestAttemptSessionSerializer(instance=session).data, status=status.HTTP_201_CREATED)
