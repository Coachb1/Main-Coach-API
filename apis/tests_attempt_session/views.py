from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.tests_attempt_session.serializers import TestAttemptSessionSerializer
from clients.permissions import IsAuthenticatedClient
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from pdf_generator.helpers import get_report_from_test_attempt_session
from tests.helpers import create_test_question_answer_session
from tests.models import TestAttemptSession


class TestAttemptSessionViewSet(ApiViewSet,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin):
    queryset = TestAttemptSession.objects.filter(deleted=0)
    serializer_class = TestAttemptSessionSerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("test_id", "test_score", "participant_id")
    ordering_fields = ("id", "test_score")
    lookup_field = "uid"

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

    @action(methods=["GET"], detail=True, url_path="report")
    def get_test_report(self, request, *args, **kwargs):
        test_attempt_session = self.get_object()
        report_url = get_report_from_test_attempt_session(test_attempt_session)
        return Response({"report_url": report_url}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="report-frontend")
    def get_test_report_frontend(self, request, *args, **kwargs):
        test_attempt_session = self.get_object()
        data = get_report_from_test_attempt_session(
            test_attempt_session, only_data=True)
        return Response({"data": data}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="get-session-id")
    def get_session_uid(self, request, *args, **kwargs):
        participant_id = request.query_params.get("participant_id")
        test_id = request.query_params.get("test_id")

        # Filter the test_attempt_session with the given test_id and participant_id and ordered by created
        test_attempt_session = TestAttemptSession.objects.filter(
            test_id=test_id, participant_id=participant_id, deleted=0).order_by("-id").first()

        return Response({"uid": test_attempt_session.uid}, status=status.HTTP_200_OK)
