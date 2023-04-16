from rest_framework import mixins, status
from rest_framework.response import Response

from apis.tests.serializers import CreateTestSerializer
from apis.tests.serializers import TestDisplaySerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from tests.helpers import create_test
from tests.models import Test


class TestViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = Test.objects.filter(deleted=0)
    serializer_class = TestDisplaySerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = CreateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test, test_questions = create_test(
            tenant=request.tenant,
            **serializer.validated_data
        )

        return Response(self.serializer_class(instance=test).data, status=status.HTTP_201_CREATED)
