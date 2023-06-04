from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.tests.filtersets import TestFilterSet
from apis.tests.serializers import CreateTestSerializer
from apis.tests.serializers import TestDisplaySerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from mindmap.helpers import get_mindmap_url_from_test
from pdf_generator.helpers import get_flash_cards_from_test
from tests.helpers import create_test, get_test_report
from tests.models import Test
from users.permissions import IsAuthenticatedUser


class TestViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = Test.objects.filter(deleted=0)
    serializer_class = TestDisplaySerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TestFilterSet
    ordering_fields = ("id",)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = CreateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["creator_id"] is None:
            serializer.validated_data["creator_id"] = request.auth_user.uid

        test, test_questions = create_test(
            tenant=request.tenant,
            **serializer.validated_data
        )

        return Response(self.serializer_class(instance=test).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=True, url_path="flash-cards")
    def get_test_flash_cards(self, request, *args, **kwargs):
        test = self.get_object()
        flash_card_urls = get_flash_cards_from_test(test)
        return Response({"flash_cards": flash_card_urls}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="mindmap")
    def get_test_mindmap(self, request, *args, **kwargs):
        test = self.get_object()
        url = get_mindmap_url_from_test(test)
        return Response({"url": url}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="report")
    def get_test_report_pdf_view(self, request, *args, **kwargs):
        user = self.get_object()

        report_url = get_test_report(user)

        return Response({"report_url": report_url})
