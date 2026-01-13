from rest_framework import mixins, status
from rest_framework.response import Response

from apis.clients.serializers import ClientSerializer, SetupClientSerializer
from clients.helpers import setup_client
from clients.models import Client
from commons.viewset import ApiViewSet
from users.permissions import IsAuthenticatedRootUser

from drf_spectacular.utils import extend_schema, OpenApiResponse



@extend_schema(
    methods=["GET"],
    summary="List clients",
    description=(
        "Retrieve a list of all active (non-deleted) clients.\n\n"
        "This endpoint is restricted to root users and returns "
        "basic client metadata without secrets."
    ),
    responses={
        200: OpenApiResponse(
            description="List of clients",
            response=ClientSerializer(many=True),
        ),
    },
    tags=["Tenant-Clients"],
)
class ClientViewSet(ApiViewSet,
                    mixins.ListModelMixin):
    """
    Manage tenant clients.

    WHAT:
        Allows root users to list existing clients and create new ones.

    WHY:
        Clients represent tenant-level integrations and credentials
        used for authentication and access control.

    HOW:
        - GET: Returns all active clients.
        - POST: Creates a new client and generates a secret.

    SECURITY:
        - Restricted to root users
        - Client secret is returned only once
    """

    queryset = Client.objects.filter(deleted=0)
    serializer_class = ClientSerializer
    lookup_field = "uid"
    permission_classes = (IsAuthenticatedRootUser,)

    @extend_schema(
        methods=["POST"],
        summary="Create Authclient",
        description=(
            "Create a new client for a tenant.\n\n"
            "A unique client key and secret are generated. "
            "**The secret is returned only once and must be stored securely.**"
        ),
        request=SetupClientSerializer,
        responses={
            201: OpenApiResponse(
                description="Client created successfully",
                response={
                    "type": "object",
                    "properties": {
                        "client": {
                            "$ref": "#/components/schemas/Client"
                        },
                        "secret": {
                            "type": "string",
                            "example": "abcdef123456",
                            "description": "Client secret (returned only once)",
                        },
                    },
                },
            ),
            400: OpenApiResponse(
                description="Invalid input",
                response={"type": "object", "properties": {"error": {"type": "string"}}},
            ),
            403: OpenApiResponse(
                description="Permission denied",
            ),
        },
        tags=["Tenant-Clients"],
    )
    def create(self, request, *args, **kwargs):
        """
        Create a new client and generate credentials.

        INPUT:
            - tenant_id (str): Tenant identifier
            - name (str): Client name
            - description (str): Optional description

        OUTPUT:
            - client: Client metadata
            - secret: One-time client secret

        NOTE:
            The secret is not stored in plain text and cannot be retrieved again.
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
