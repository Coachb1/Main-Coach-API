from rest_framework import mixins, status
from rest_framework.response import Response

from apis.tests_invites.serializers import TestInviteCreateSerializer
from apis.tests_invites.serializers import TestInviteSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from tests.helpers import create_test_invite
from tests.models import TestInvite


class TestInviteViewSet(ApiViewSet,
                        mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.UpdateModelMixin):
    queryset = TestInvite.objects.filter(deleted=0)
    serializer_class = TestInviteSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = TestInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_id = serializer.validated_data["test_id"]
        participant_id = serializer.validated_data["participant_id"]
        expires_at = serializer.validated_data["expires_at"]

        invite = create_test_invite(
            tenant=request.tenant,
            test_id=test_id,
            participant_id=participant_id,
            expires_at=expires_at
        )

        return Response(data=TestInviteSerializer(instance=invite).data, status=status.HTTP_201_CREATED)
