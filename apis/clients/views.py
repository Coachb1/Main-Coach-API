from rest_framework import mixins, status
from rest_framework.response import Response

from apis.clients.serializers import ClientSerializer, SetupClientSerializer
from clients.helpers import setup_client
from clients.models import Client
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedRootUser


class ClientViewSet(ApiViewSet,
                    mixins.ListModelMixin):
    """
    A viewset for listing and creating client objects.

    Inherits from:
        - ApiViewSet
        - mixins.ListModelMixin

    Example Usage:
        # Create a new client
        POST /clients/
        Request Body:
        {
          "tenant_id": "abc123",
          "name": "Client 1",
          "description": "This is a test client"
        }
        Response Body:
        {
          "client": {
            "uid": "xyz789",
            "name": "Client 1",
            "key": "123456",
            "description": "This is a test client",
            "deleted": false,
            "created": "2022-01-01T00:00:00Z",
            "updated": "2022-01-01T00:00:00Z"
          },
          "secret": "abcdef"
        }

        
    """

    queryset = Client.objects.filter(deleted=0)
    serializer_class = ClientSerializer
    lookup_field = "uid"
    permission_classes = (IsAuthenticatedRootUser,)

    def create(self, request, *args, **kwargs):
        """
        Create a new client object.

        Args:
            request: The request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            A response containing the created client object and a secret key.

        Raises:
            ValidationError: If the request data is invalid.
        """
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
