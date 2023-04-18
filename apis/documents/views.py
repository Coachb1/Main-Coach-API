from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apis.documents.serializer import DocumentViewSerializer, DocumentCreateSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from documents.helpers import create_document, get_document_url
from documents.models import Document
from rest_framework import mixins


class DocumentViewSet(ApiViewSet,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin):
    queryset = Document.objects.filter(deleted=0)
    serializer_class = DocumentViewSerializer
    permission_classes = (IsAuthenticatedClient,)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["POST"], detail=False, parser_classes=(MultiPartParser, ), url_path="upload")
    def upload_document_view(self, request, *args, **kwargs):
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test, test_questions = create_document(
            tenant=request.tenant,
            **serializer.validated_data
        )

        return Response(self.serializer_class(instance=test).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=True, url_path="url")
    def get_doc_url_view(self, request, *args, **kwargs):
        doc = self.get_object()
        url = get_document_url(doc)
        return Response({"url": url})
