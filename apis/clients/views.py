from rest_framework import mixins, status
from rest_framework.response import Response

from apis.clients.serializers import ClientSerializer, SetupClientSerializer
from clients.helpers import setup_client
from clients.models import Client
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedRootUser


class ClientViewSet(ApiViewSet,
                    mixins.ListModelMixin):
    queryset = Client.objects.filter(deleted=0)
    serializer_class = ClientSerializer
    lookup_field = "uid"
    permission_classes = (IsAuthenticatedRootUser,)

    def create(self, request, *args, **kwargs):
        serializer = SetupClientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant_id = serializer.validated_data["tenant_id"]
        name = serializer.validated_data["name"]
        description = serializer.validated_data["description"]

        client, secret = setup_client(tenant_id=tenant_id,
                                      name=name,
                                      description=description)

        return Response(dict(client=ClientSerializer(instance=client).data,
                             secret=secret), status=status.HTTP_201_CREATED)
